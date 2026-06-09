"""
Transaction API router.
POST /ingest — publish to Kafka + track velocity in Redis
GET  /flagged — paginated flagged transactions
GET  /{id}   — single transaction detail
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Depends

from api.models.transaction import TransactionIn, TransactionOut, TransactionBatch
from core.security import verify_api_key
from db.redis import cache as redis_cache
from db.snowflake.session import run_sync, execute_query
from kafka.producer import publish_transaction

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/ingest", status_code=202)
async def ingest_transactions(
    batch: TransactionBatch,
    _: str = Depends(verify_api_key),
):
    """
    Ingest a batch of transactions.
    Each transaction is published to Kafka transactions.raw and velocity
    counters are incremented in Redis atomically. Returns immediately (202).
    """
    count = 0
    for tx_in in batch.transactions:
        tx = tx_in.model_dump()
        if not tx.get("id"):
            tx["id"] = str(uuid.uuid4())
        if not tx.get("timestamp"):
            tx["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Track velocity in Redis (hot path)
        await redis_cache.track_velocity(tx["sender_account_id"])

        # Publish to Kafka (fire-and-forget; API returns 202 immediately)
        await publish_transaction(tx)
        count += 1

    return {"accepted": count, "status": "queued"}


@router.get("/flagged")
async def get_flagged_transactions(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: str = Depends(verify_api_key),
):
    """Paginated list of flagged transactions from Snowflake."""
    sql = """
    SELECT t.id, t.sender_account_id, t.receiver_account_id,
           t.amount, t.currency, t.transaction_type, t.channel,
           t.timestamp, t.aml_label,
           r.composite_score, r.risk_tier, r.triggered_rules
    FROM transactions t
    LEFT JOIN risk_events r ON r.transaction_id = t.id
    WHERE t.is_flagged = TRUE
    ORDER BY t.timestamp DESC
    LIMIT :limit OFFSET :offset
    """
    rows = await run_sync(execute_query, sql, {"limit": limit, "offset": offset})
    return {"data": rows, "count": len(rows), "offset": offset}


@router.get("/{tx_id}")
async def get_transaction(tx_id: str, _: str = Depends(verify_api_key)):
    """Single transaction detail with risk score."""
    sql = """
    SELECT t.*, r.composite_score, r.risk_tier, r.triggered_rules, r.shap_values
    FROM transactions t
    LEFT JOIN risk_events r ON r.transaction_id = t.id
    WHERE t.id = :tx_id
    LIMIT 1
    """
    rows = await run_sync(execute_query, sql, {"tx_id": tx_id})
    if not rows:
        raise HTTPException(status_code=404, detail=f"Transaction {tx_id} not found")
    return rows[0]
