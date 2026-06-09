"""
Cache helpers: velocity tracking, risk score caching, graph neighbor caching.
"""
from __future__ import annotations

import json
from typing import Any

from db.redis.client import redis_client
from db.redis import keys as K


async def track_velocity(account_id: str) -> tuple[int, int]:
    """
    Atomically increment 1h and 24h velocity counters.
    Uses a pipeline for a single round-trip.
    Returns (count_1h, count_24h).
    """
    pipe = redis_client.pipeline()
    pipe.incr(K.vel_1h(account_id))
    pipe.expire(K.vel_1h(account_id), K.TTL_VELOCITY_1H)
    pipe.incr(K.vel_24h(account_id))
    pipe.expire(K.vel_24h(account_id), K.TTL_VELOCITY_24H)
    results = await pipe.execute()
    return int(results[0]), int(results[2])


async def get_velocity(account_id: str) -> dict[str, int]:
    """Fetch current velocity counters. Returns 0 on cache miss."""
    pipe = redis_client.pipeline()
    pipe.get(K.vel_1h(account_id))
    pipe.get(K.vel_24h(account_id))
    v1h, v24h = await pipe.execute()
    return {
        "tx_count_1h": int(v1h or 0),
        "tx_count_24h": int(v24h or 0),
    }


async def cache_risk_score(account_id: str, tx_id: str, score: dict) -> None:
    """Write-through: cache risk score for both account and transaction."""
    pipe = redis_client.pipeline()
    pipe.setex(K.risk_tx(tx_id), K.TTL_RISK_SCORE, score["composite_score"])
    pipe.setex(K.risk_acct(account_id), K.TTL_RISK_SCORE, json.dumps(score))
    # Update flagged leaderboard (sorted set)
    pipe.zadd(K.flagged_sorted(), {account_id: float(score["composite_score"])})
    await pipe.execute()


async def get_risk_profile(account_id: str) -> dict | None:
    """Cache-aside: return cached risk profile or None on miss."""
    raw = await redis_client.get(K.risk_acct(account_id))
    if raw:
        return json.loads(raw)
    return None


async def cache_graph_neighbors(account_id: str, data: Any) -> None:
    await redis_client.setex(
        K.graph_neighbors(account_id), K.TTL_GRAPH_NEIGHBORS, json.dumps(data)
    )


async def get_graph_neighbors(account_id: str) -> Any | None:
    raw = await redis_client.get(K.graph_neighbors(account_id))
    if raw:
        return json.loads(raw)
    return None


async def get_top_flagged(n: int = 20) -> list[tuple[str, float]]:
    """Return top-N flagged accounts from sorted set (highest score first)."""
    results = await redis_client.zrevrange(K.flagged_sorted(), 0, n - 1, withscores=True)
    return [(account_id, score) for account_id, score in results]


async def publish_alert(alert: dict) -> None:
    """Publish a real-time alert to the live dashboard channel."""
    await redis_client.publish(K.ALERTS_CHANNEL, json.dumps(alert))
