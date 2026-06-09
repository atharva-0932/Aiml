"""
Risk scoring API.
POST /score         — score a single transaction synchronously (hot path)
GET  /accounts/{id}/risk-profile — account risk profile (Redis-first)
GET  /top-flagged   — top-N flagged accounts from Redis sorted set
GET  /alerts/stream — SSE stream of real-time alerts via Redis Pub/Sub
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.models.risk_event import RiskScoreRequest, RiskScoreResponse, AlertEvent
from api.models.account import AccountRiskProfile
from core.security import verify_api_key
from db.redis import cache as redis_cache, keys as K
from db.redis.client import redis_client
from db.snowflake.session import run_sync, execute_query
from graph.graph_features import get_account_graph_features
from ml.risk_scorer import CompositeRiskScorer

router = APIRouter(tags=["risk"])

_scorer: CompositeRiskScorer | None = None


def _get_scorer() -> CompositeRiskScorer:
    global _scorer
    if _scorer is None:
        _scorer = CompositeRiskScorer()
    return _scorer


@router.post("/risk/score", response_model=RiskScoreResponse)
async def score_transaction(
    req: RiskScoreRequest,
    _: str = Depends(verify_api_key),
):
    """
    Synchronously score a transaction on the hot path.
    Velocity features pulled from Redis (<1ms), model inference in-memory.
    """
    tx = req.transaction
    account_id = tx.get("sender_account_id", "")

    velocity = await redis_cache.get_velocity(account_id)
    tx.update(velocity)

    graph_features = await get_account_graph_features(account_id)
    tx.update(graph_features)

    scorer = _get_scorer()
    score = scorer.score(tx)

    await redis_cache.cache_risk_score(account_id, tx.get("id", "unknown"), score)

    return RiskScoreResponse(
        transaction_id=tx.get("id", ""),
        account_id=account_id,
        composite_score=score["composite_score"],
        risk_tier=score["risk_tier"],
        anomaly_score=score["anomaly_score"],
        classifier_score=score["classifier_score"],
        graph_risk_score=score["graph_risk_score"],
        triggered_rules=score["triggered_rules"],
        shap_values=score.get("shap_values", {}),
    )


@router.get("/accounts/{account_id}/risk-profile", response_model=AccountRiskProfile)
async def get_risk_profile(account_id: str, _: str = Depends(verify_api_key)):
    """
    Cache-aside: Redis hit (<5ms) or Snowflake fallback (~1-2s).
    """
    cached = await redis_cache.get_risk_profile(account_id)
    if cached:
        return AccountRiskProfile(account_id=account_id, cached=True, **cached)

    # Cold path — query Snowflake
    sql = """
    SELECT composite_score, anomaly_score, classifier_score,
           graph_risk_score, risk_tier, triggered_rules, shap_values
    FROM risk_events
    WHERE account_id = :account_id
    ORDER BY created_at DESC
    LIMIT 1
    """
    rows = await run_sync(execute_query, sql, {"account_id": account_id})
    if not rows:
        return AccountRiskProfile(
            account_id=account_id, composite_score=0, anomaly_score=0,
            classifier_score=0, graph_risk_score=0, risk_tier="LOW",
            triggered_rules=[], cached=False,
        )

    row = rows[0]
    profile = {
        "composite_score": float(row.get("composite_score") or 0),
        "anomaly_score": float(row.get("anomaly_score") or 0),
        "classifier_score": float(row.get("classifier_score") or 0),
        "graph_risk_score": float(row.get("graph_risk_score") or 0),
        "risk_tier": row.get("risk_tier", "LOW"),
        "triggered_rules": json.loads(row.get("triggered_rules") or "[]"),
        "shap_values": json.loads(row.get("shap_values") or "{}"),
    }
    await redis_cache.cache_risk_score(account_id, "latest", profile)
    return AccountRiskProfile(account_id=account_id, cached=False, **profile)


@router.get("/risk/top-flagged")
async def get_top_flagged(n: int = 20, _: str = Depends(verify_api_key)):
    """Top-N flagged accounts from Redis sorted set (real-time leaderboard)."""
    results = await redis_cache.get_top_flagged(n)
    return [{"account_id": aid, "composite_score": score} for aid, score in results]


@router.get("/alerts/stream")
async def stream_alerts(_: str = Depends(verify_api_key)):
    """
    SSE endpoint — streams live risk alerts to the dashboard.
    Subscribes to Redis Pub/Sub channel 'alerts:live'.
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(K.ALERTS_CHANNEL)
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    data = message["data"]
                    yield f"data: {data}\n\n"
                else:
                    yield ": keepalive\n\n"
                    await asyncio.sleep(1)
        finally:
            await pubsub.unsubscribe(K.ALERTS_CHANNEL)
            await pubsub.aclose()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
