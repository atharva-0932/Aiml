"""
Velocity counters + risk score cache for the ml_scorer consumer.
"""
from __future__ import annotations

from db.redis import keys as K
from db.redis.client import get_redis


async def get_velocity_features(account_id: str) -> dict[str, float]:
    """Fetch current velocity features for an account (0 on miss)."""
    r = get_redis()
    pipe = r.pipeline()
    pipe.get(K.tx_count_1h(account_id))
    pipe.get(K.tx_volume_1h(account_id))
    pipe.scard(K.unique_receivers_24h(account_id))
    count, volume, unique = await pipe.execute()
    return {
        "tx_count_1h": float(count or 0),
        "tx_volume_1h": float(volume or 0),
        "unique_receivers_24h": float(unique or 0),
    }


async def update_velocity(sender_account: str, receiver_account: str, amount: float) -> None:
    """
    Update sliding-window velocity after scoring:
      INCR tx_count:{sender}:1h → EXPIRE 3600
      INCRBYFLOAT tx_volume:{sender}:1h → EXPIRE 3600
      SADD unique_receivers:{sender}:24h {receiver} → EXPIRE 86400
    """
    r = get_redis()
    pipe = r.pipeline()
    pipe.incr(K.tx_count_1h(sender_account))
    pipe.expire(K.tx_count_1h(sender_account), K.TTL_1H)
    pipe.incrbyfloat(K.tx_volume_1h(sender_account), float(amount))
    pipe.expire(K.tx_volume_1h(sender_account), K.TTL_1H)
    pipe.sadd(K.unique_receivers_24h(sender_account), receiver_account)
    pipe.expire(K.unique_receivers_24h(sender_account), K.TTL_24H)
    await pipe.execute()


async def cache_risk_score(transaction_id: str, score: float) -> None:
    """Write risk_score:{transaction_id} with 24h TTL."""
    r = get_redis()
    await r.setex(K.risk_score(transaction_id), K.TTL_24H, str(score))
