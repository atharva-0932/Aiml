"""
Velocity counters + risk / graph / SHAP / alert cache for ml_scorer + API.
"""
from __future__ import annotations

import json
import time
from typing import Any

from db.redis import keys as K
from db.redis.client import get_redis


async def get_velocity_features(account_id: str) -> dict[str, float]:
    """Fetch current velocity features for an account (0 on miss)."""
    r = get_redis()
    pipe = r.pipeline()
    pipe.get(K.tx_count_1h(account_id))
    pipe.get(K.tx_volume_1h(account_id))
    pipe.scard(K.unique_receivers_24h(account_id))
    pipe.get(K.last_tx_ts(account_id))
    count, volume, unique, last_ts = await pipe.execute()

    time_since = 0.0
    if last_ts is not None:
        try:
            time_since = max(0.0, time.time() - float(last_ts))
        except (TypeError, ValueError):
            time_since = 0.0

    return {
        "tx_count_1h": float(count or 0),
        "tx_volume_1h": float(volume or 0),
        "unique_receivers_24h": float(unique or 0),
        "time_since_last_tx": float(time_since),
    }


async def update_velocity(sender_account: str, receiver_account: str, amount: float) -> None:
    r = get_redis()
    pipe = r.pipeline()
    pipe.incr(K.tx_count_1h(sender_account))
    pipe.expire(K.tx_count_1h(sender_account), K.TTL_1H)
    pipe.incrbyfloat(K.tx_volume_1h(sender_account), float(amount))
    pipe.expire(K.tx_volume_1h(sender_account), K.TTL_1H)
    pipe.sadd(K.unique_receivers_24h(sender_account), receiver_account)
    pipe.expire(K.unique_receivers_24h(sender_account), K.TTL_24H)
    pipe.set(K.last_tx_ts(sender_account), str(time.time()))
    await pipe.execute()


async def cache_risk_score(transaction_id: str, score: float) -> None:
    r = get_redis()
    await r.setex(K.risk_score(transaction_id), K.TTL_24H, str(score))


async def get_risk_score(transaction_id: str) -> float | None:
    r = get_redis()
    raw = await r.get(K.risk_score(transaction_id))
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


async def get_cached_graph_risk(account_id: str) -> dict[str, Any] | None:
    r = get_redis()
    raw = await r.get(K.graph_risk(account_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def cache_graph_risk(account_id: str, payload: dict[str, Any]) -> None:
    r = get_redis()
    await r.setex(K.graph_risk(account_id), K.TTL_1H, json.dumps(payload))


async def cache_shap(transaction_id: str, shap_top: list[tuple[str, float]]) -> None:
    """Store top SHAP features as JSON list of {feature, value}."""
    r = get_redis()
    payload = [{"feature": name, "value": float(val)} for name, val in shap_top]
    await r.setex(K.shap(transaction_id), K.TTL_24H, json.dumps(payload))


async def get_shap(transaction_id: str) -> list[dict[str, Any]]:
    r = get_redis()
    raw = await r.get(K.shap(transaction_id))
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


async def cache_alert(
    transaction_id: str,
    composite_score: float,
    tier: str,
    pattern: str | None,
) -> None:
    """Write alert:{tx_id} when composite_score > 70 (TTL 24h)."""
    r = get_redis()
    payload = {
        "composite_score": float(composite_score),
        "tier": tier,
        "pattern": pattern,
    }
    await r.setex(K.alert(transaction_id), K.TTL_24H, json.dumps(payload))


async def scan_keys(pattern: str) -> list[str]:
    """SCAN all keys matching pattern."""
    r = get_redis()
    keys: list[str] = []
    cursor = 0
    while True:
        cursor, batch = await r.scan(cursor=cursor, match=pattern, count=500)
        keys.extend(batch)
        if cursor == 0:
            break
    return keys


async def get_alert(transaction_id: str) -> dict[str, Any] | None:
    r = get_redis()
    raw = await r.get(K.alert(transaction_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
        # Back-compat: plain float string
        if not isinstance(data, dict):
            return {"composite_score": float(data), "tier": None, "pattern": None}
        return data
    except (json.JSONDecodeError, TypeError, ValueError):
        try:
            return {"composite_score": float(raw), "tier": None, "pattern": None}
        except (TypeError, ValueError):
            return None
