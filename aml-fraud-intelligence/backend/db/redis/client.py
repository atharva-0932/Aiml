"""
Async Redis client using redis[hiredis].
hiredis C extension gives ~3-5x faster protocol parsing vs pure-Python.
socket_timeout=0.5 ensures Redis latency never blocks the hot path.
"""
from __future__ import annotations

import redis.asyncio as aioredis
from core.config import settings
from core.logging import get_logger

log = get_logger(__name__)

redis_client: aioredis.Redis = aioredis.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=0.5,   # fail fast — never block the scoring hot path
    retry_on_timeout=True,
    health_check_interval=30,
)


async def ping() -> bool:
    try:
        return await redis_client.ping()
    except Exception as exc:
        log.error("Redis ping failed", error=str(exc))
        return False
