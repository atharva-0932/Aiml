"""
Supabase / Postgres cold-path writes via asyncpg (pgBouncer pooler URL).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg

from core.config import settings

_pool: asyncpg.Pool | None = None
_supabase_disabled: bool = False
_warned_missing: bool = False

UPSERT_TRANSACTION = """
INSERT INTO transactions (
  transaction_id, timestamp, sender_account, receiver_account,
  amount, bank, pattern_label, risk_score, scored_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
ON CONFLICT (transaction_id) DO UPDATE SET
  risk_score = EXCLUDED.risk_score,
  scored_at = NOW()
"""


def _is_configured() -> bool:
    url = settings.supabase_db_url or ""
    return bool(url) and "xxxx" not in url


async def get_pool() -> asyncpg.Pool | None:
    global _pool, _supabase_disabled, _warned_missing
    if _supabase_disabled:
        return None
    if not _is_configured():
        if not _warned_missing:
            print(
                "WARNING: SUPABASE_DB_URL not configured — skipping Postgres writes. "
                "Set a real pooler URL in .env and apply 001_initial.sql."
            )
            _warned_missing = True
        _supabase_disabled = True
        return None
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.supabase_db_url,
            min_size=1,
            max_size=5,
            statement_cache_size=0,  # required for pgBouncer transaction pooling
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _parse_ts(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text)


async def upsert_transaction(tx: dict[str, Any], risk_score: float) -> None:
    """Write scored transaction to Supabase transactions table (no-op if unconfigured)."""
    pool = await get_pool()
    if pool is None:
        return
    pattern = tx.get("pattern_label")
    if pattern == "" or pattern is None:
        pattern = None
    async with pool.acquire() as conn:
        await conn.execute(
            UPSERT_TRANSACTION,
            tx["transaction_id"],
            _parse_ts(tx.get("timestamp")),
            tx["sender_account"],
            tx["receiver_account"],
            float(tx["amount"]),
            tx.get("bank"),
            pattern,
            float(risk_score),
        )
