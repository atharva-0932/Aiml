"""
LangChain copilot chains.
Supports streaming and structured output.
Falls back gracefully when LLM API keys are not configured.
"""
from __future__ import annotations

from typing import AsyncIterator

from core.config import settings
from core.logging import get_logger
from genai.prompts import (
    SYSTEM_PROMPT,
    EXPLAIN_FLAGGING_TEMPLATE,
    INVESTIGATOR_QA_TEMPLATE,
    FUND_FLOW_SUMMARY_TEMPLATE,
)
from genai.rag import retrieve

log = get_logger(__name__)


def _get_llm(streaming: bool = False):
    """Return an LLM instance based on configured provider."""
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model="gemini-1.5-pro",
                google_api_key=settings.gemini_api_key,
                streaming=streaming,
                temperature=0.1,
            )
        except Exception as exc:
            log.warning("Gemini LLM init failed", error=str(exc))

    if settings.openai_api_key:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model="gpt-4o",
                api_key=settings.openai_api_key,
                streaming=streaming,
                temperature=0.1,
            )
        except Exception as exc:
            log.warning("OpenAI LLM init failed", error=str(exc))

    log.warning("No LLM configured — copilot will return placeholder responses")
    return None


def _format_shap(shap_values: dict) -> str:
    if not shap_values:
        return "Not available"
    sorted_features = sorted(shap_values.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
    return "\n".join(f"  - {k}: {v:+.4f}" for k, v in sorted_features)


async def explain_account(account_id: str, risk_profile: dict, tx_summary: str) -> str:
    """Generate a formal AML explanation for why an account was flagged."""
    llm = _get_llm()
    if llm is None:
        return _fallback_explanation(account_id, risk_profile)

    prompt = EXPLAIN_FLAGGING_TEMPLATE.format(
        account_id=account_id,
        composite_score=risk_profile.get("composite_score", 0),
        risk_tier=risk_profile.get("risk_tier", "UNKNOWN"),
        classifier_score=risk_profile.get("classifier_score", 0),
        anomaly_score=risk_profile.get("anomaly_score", 0),
        graph_risk_score=risk_profile.get("graph_risk_score", 0),
        triggered_rules=", ".join(risk_profile.get("triggered_rules", [])) or "None",
        tx_summary=tx_summary,
        pagerank_score=risk_profile.get("pagerank_score", 0),
        graph_in_degree=risk_profile.get("graph_in_degree", 0),
        graph_out_degree=risk_profile.get("graph_out_degree", 0),
        cycle_membership=risk_profile.get("cycle_membership", 0),
        hop_depth=risk_profile.get("hop_depth", 0),
        shap_summary=_format_shap(risk_profile.get("shap_values", {})),
    )

    from langchain_core.messages import SystemMessage, HumanMessage
    response = await llm.ainvoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
    return response.content


async def chat_stream(question: str, account_id: str | None = None) -> AsyncIterator[str]:
    """Stream a response to an investigator question with RAG context."""
    llm = _get_llm(streaming=True)
    if llm is None:
        yield "LLM not configured. Please set GEMINI_API_KEY or OPENAI_API_KEY in .env"
        return

    # Retrieve relevant context
    docs = retrieve(question, account_id=account_id, k=5)
    context = "\n\n".join(d["text"] for d in docs) if docs else "No relevant transactions found."

    prompt = INVESTIGATOR_QA_TEMPLATE.format(
        system_context=SYSTEM_PROMPT,
        question=question,
        retrieved_context=context,
    )

    from langchain_core.messages import HumanMessage
    async for chunk in llm.astream([HumanMessage(content=prompt)]):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content


async def summarise_fund_flow(account_id: str, chain_data: str, graph_path: str) -> str:
    """Summarise a suspicious fund flow narrative."""
    llm = _get_llm()
    if llm is None:
        return "LLM not configured."

    prompt = FUND_FLOW_SUMMARY_TEMPLATE.format(
        account_id=account_id,
        chain_data=chain_data,
        graph_path=graph_path,
    )
    from langchain_core.messages import SystemMessage, HumanMessage
    response = await llm.ainvoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
    return response.content


def _fallback_explanation(account_id: str, risk_profile: dict) -> str:
    rules = risk_profile.get("triggered_rules", [])
    score = risk_profile.get("composite_score", 0)
    return (
        f"Account {account_id} received a composite risk score of {score:.1f}/100 "
        f"({risk_profile.get('risk_tier', 'UNKNOWN')} tier). "
        f"Triggered rules: {', '.join(rules) or 'none'}. "
        "Configure GEMINI_API_KEY or OPENAI_API_KEY for AI-generated explanations."
    )
