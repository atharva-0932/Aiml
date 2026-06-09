"""
RAG pipeline — embeds transaction narratives and stores in ChromaDB.
Retrieves top-k relevant context chunks before each LLM query.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.config import settings
from core.logging import get_logger

log = get_logger(__name__)

CHROMA_DIR = Path(__file__).parent.parent.parent / "data" / "chroma"
COLLECTION_NAME = "aml_transactions"


def _get_embedding_function():
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        try:
            from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction
            return GoogleGenerativeAiEmbeddingFunction(
                api_key=settings.gemini_api_key,
                model_name="models/text-embedding-004",
            )
        except Exception as exc:
            log.warning("Gemini embedding unavailable, falling back", error=str(exc))

    try:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    except Exception:
        return None


def get_collection():
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    ef = _get_embedding_function()
    kwargs = {"name": COLLECTION_NAME}
    if ef:
        kwargs["embedding_function"] = ef
    return client.get_or_create_collection(**kwargs)


def _make_document(tx: dict, risk: dict | None = None) -> str:
    """Convert a transaction + risk score into a text narrative for embedding."""
    amount = tx.get("amount", 0)
    label = tx.get("aml_label") or "normal"
    rules = (risk or {}).get("triggered_rules", [])
    return (
        f"Transaction {tx['id']}: {tx.get('sender_account_id')} sent "
        f"${amount:,.2f} to {tx.get('receiver_account_id')} via "
        f"{tx.get('transaction_type', 'unknown')} on {tx.get('timestamp', '')}. "
        f"Pattern: {label}. Rules triggered: {', '.join(rules) or 'none'}. "
        f"Risk score: {(risk or {}).get('composite_score', 0):.1f}/100."
    )


def index_transactions(transactions: list[dict], risk_scores: dict[str, dict] | None = None) -> int:
    """Index a batch of transactions into ChromaDB."""
    collection = get_collection()
    docs, ids, metas = [], [], []

    for tx in transactions:
        risk = (risk_scores or {}).get(tx["id"])
        doc = _make_document(tx, risk)
        docs.append(doc)
        ids.append(tx["id"])
        metas.append({
            "account_id": tx.get("sender_account_id", ""),
            "aml_label": tx.get("aml_label") or "normal",
            "amount": float(tx.get("amount", 0)),
            "is_flagged": bool(tx.get("is_flagged", False)),
        })

    if docs:
        collection.upsert(documents=docs, ids=ids, metadatas=metas)
    return len(docs)


def retrieve(query: str, account_id: str | None = None, k: int = 5) -> list[dict]:
    """Retrieve top-k relevant transaction documents for RAG context."""
    collection = get_collection()
    where = {"account_id": account_id} if account_id else None
    try:
        results = collection.query(
            query_texts=[query],
            n_results=k,
            where=where,
        )
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        return [{"text": d, "metadata": m} for d, m in zip(docs, metas)]
    except Exception as exc:
        log.error("RAG retrieval failed", error=str(exc))
        return []
