"""
Velocity counters + risk / graph score cache for the ml_scorer consumer.
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
    """
    Update sliding-window velocity after scoring:
      INCR tx_count:{sender}:1h → EXPIRE 3600
      INCRBYFLOAT tx_volume:{sender}:1h → EXPIRE 3600
      SADD unique_receivers:{sender}:24h {receiver} → EXPIRE 86400
      SET last_tx_ts:{sender} = now
    """
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
    """Write risk_score:{transaction_id} with 24h TTL."""
    r = get_redis()
    await r.setex(K.risk_score(transaction_id), K.TTL_24H, str(score))


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
    """Cache graph risk profile for 1 hour to avoid hammering Neo4j."""
    r = get_redis()
    await r.setex(K.graph_risk(account_id), K.TTL_1H, json.dumps(payload))
