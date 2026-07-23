"""Alert list + summary endpoints (Redis alert:* keys)."""
from __future__ import annotations

from collections import Counter
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query

from api.auth import require_api_key
from api.store import store
from db.redis.cache import get_alert, scan_keys
from ml.scorer import classify_tier

router = APIRouter(prefix="/alerts", tags=["alerts"])

Tier = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


@router.get("")
async def list_alerts(
    limit: int = Query(50, ge=1, le=1000),
    tier: Tier | None = None,
    pattern: str | None = None,
    _: str = Depends(require_api_key),
) -> list[dict[str, Any]]:
    keys = await scan_keys("alert:*")
    alerts: list[dict[str, Any]] = []

    for key in keys:
        tx_id = key.split("alert:", 1)[-1]
        payload = await get_alert(tx_id)
        if payload is None:
            continue
        score = float(payload.get("composite_score") or 0)
        if score <= 70:
            continue
        alert_tier = payload.get("tier") or classify_tier(score)
        alert_pattern = payload.get("pattern")
        tx = store.get(tx_id) or {}
        if alert_pattern is None:
            alert_pattern = tx.get("pattern_label")

        if tier and alert_tier != tier:
            continue
        if pattern and (alert_pattern or "") != pattern:
            continue

        alerts.append({
            "transaction_id": tx_id,
            "composite_score": score,
            "tier": alert_tier,
            "pattern": alert_pattern,
            "sender_account": tx.get("sender_account"),
            "receiver_account": tx.get("receiver_account"),
            "amount": tx.get("amount"),
            "timestamp": tx.get("timestamp"),
            "bank": tx.get("bank"),
        })

    alerts.sort(key=lambda a: a["composite_score"], reverse=True)
    return alerts[:limit]


@router.get("/summary")
async def alerts_summary(_: str = Depends(require_api_key)) -> dict[str, Any]:
    keys = await scan_keys("alert:*")
    by_tier: Counter[str] = Counter()
    by_pattern: Counter[str] = Counter()
    total = 0

    for key in keys:
        tx_id = key.split("alert:", 1)[-1]
        payload = await get_alert(tx_id)
        if payload is None:
            continue
        score = float(payload.get("composite_score") or 0)
        if score <= 70:
            continue
        total += 1
        alert_tier = payload.get("tier") or classify_tier(score)
        by_tier[alert_tier] += 1
        pattern = payload.get("pattern")
        if not pattern:
            tx = store.get(tx_id) or {}
            pattern = tx.get("pattern_label") or "unknown"
        by_pattern[str(pattern)] += 1

    return {
        "total_alerts": total,
        "by_tier": dict(by_tier),
        "by_pattern": dict(by_pattern),
    }
