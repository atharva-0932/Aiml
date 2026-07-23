"""Transaction list / detail / live-score endpoints."""
from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import require_api_key
from api.store import store
from db.redis.cache import (
    cache_graph_risk,
    get_cached_graph_risk,
    get_risk_score,
    get_shap,
    get_velocity_features,
    scan_keys,
)
from graph.scorer import GraphRiskScorer
from ml.features import extract_features
from ml.scorer import CompositeRiskScorer, XGBoostScorer

router = APIRouter(prefix="/transactions", tags=["transactions"])

Tier = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

_xgb: XGBoostScorer | None = None
_graph: GraphRiskScorer | None = None
_composite = CompositeRiskScorer()


def _get_xgb() -> XGBoostScorer:
    global _xgb
    if _xgb is None:
        _xgb = XGBoostScorer()
    return _xgb


def _get_graph() -> GraphRiskScorer:
    global _graph
    if _graph is None:
        _graph = GraphRiskScorer()
    return _graph


class ScoreRequest(BaseModel):
    sender_account: str
    receiver_account: str
    amount: float = Field(gt=0)
    bank: str = "UNKNOWN"
    timestamp: str | None = None


@router.get("")
async def list_transactions(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    tier: Tier | None = None,
    pattern: str | None = None,
    _: str = Depends(require_api_key),
) -> list[dict[str, Any]]:
    """List scored transactions from Redis risk_score:* joined with CSV."""
    keys = await scan_keys("risk_score:*")
    results: list[dict[str, Any]] = []

    for key in keys:
        tx_id = key.split("risk_score:", 1)[-1]
        score = await get_risk_score(tx_id)
        if score is None:
            continue
        tx = store.get(tx_id)
        if tx is None:
            # Scored live via POST but not in CSV — minimal shell
            tx = {
                "transaction_id": tx_id,
                "timestamp": None,
                "sender_account": None,
                "receiver_account": None,
                "amount": None,
                "bank": None,
                "pattern_label": None,
            }
        row = store.enrich(tx, score)
        if tier and row.get("tier") != tier:
            continue
        if pattern and (row.get("pattern_label") or "") != pattern:
            continue
        results.append(row)

    results.sort(key=lambda r: float(r.get("composite_score") or 0), reverse=True)
    return results[offset : offset + limit]


@router.get("/{transaction_id}")
async def get_transaction(
    transaction_id: str,
    _: str = Depends(require_api_key),
) -> dict[str, Any]:
    tx = store.get(transaction_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    score = await get_risk_score(transaction_id)
    if score is None:
        raise HTTPException(status_code=404, detail="score not found for transaction")
    shap = await get_shap(transaction_id)
    out = store.enrich(tx, score)
    out["shap"] = shap
    return out


@router.post("/score")
async def score_transaction(
    body: ScoreRequest,
    _: str = Depends(require_api_key),
) -> dict[str, Any]:
    """Live score a transaction through XGBoost + GraphRisk."""
    from datetime import datetime, timezone

    tx = {
        "transaction_id": str(uuid4()),
        "sender_account": body.sender_account,
        "receiver_account": body.receiver_account,
        "amount": float(body.amount),
        "bank": body.bank,
        "timestamp": body.timestamp or datetime.now(timezone.utc).isoformat(),
        "pattern_label": None,
    }

    xgb = _get_xgb()
    graph_scorer = _get_graph()
    velocity = await get_velocity_features(tx["sender_account"])
    features = extract_features(tx, velocity=velocity, amount_mean=xgb.amount_mean)
    xgb_score = xgb.score(features)

    cached = await get_cached_graph_risk(tx["sender_account"])
    if cached is None:
        graph = await graph_scorer.score(tx["sender_account"])
        await cache_graph_risk(tx["sender_account"], graph)
    else:
        graph = cached

    combined = _composite.composite(xgb_score, float(graph.get("graph_risk", 0.0)))
    shap_top = xgb.shap_top_features(features, top_k=5)

    return {
        **combined,
        "transaction_id": tx["transaction_id"],
        "flags": graph.get("flags", []),
        "shap": [{"feature": n, "value": v} for n, v in shap_top],
        "graph": {
            "cycle_count": graph.get("cycle_count"),
            "is_mule": graph.get("is_mule"),
            "layering_depth": graph.get("layering_depth"),
            "pagerank": graph.get("pagerank"),
        },
    }
