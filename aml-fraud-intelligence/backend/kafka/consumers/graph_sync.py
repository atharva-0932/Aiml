"""
Graph Sync Consumer.
Subscribes to transactions.raw and writes Account nodes + TRANSFERRED_TO
relationships to Neo4j asynchronously — no blocking of the scoring hot path.
"""
from __future__ import annotations

import asyncio
import json

from confluent_kafka import Consumer, KafkaError
from core.config import settings
from core.logging import get_logger
from db.neo4j.driver import run_write
from db.neo4j import queries as Q

log = get_logger(__name__)


def _build_consumer() -> Consumer:
    return Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": "aml-graph-sync",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })


async def _sync_transaction(tx: dict) -> None:
    """Upsert accounts + create TRANSFERRED_TO relationship in Neo4j."""
    sender_id = tx.get("sender_account_id")
    receiver_id = tx.get("receiver_account_id")

    if not sender_id or not receiver_id:
        return

    await run_write(Q.UPSERT_ACCOUNT, {
        "id": sender_id,
        "type": tx.get("transaction_type", "unknown"),
        "bank_code": tx.get("bank_code", ""),
        "country": tx.get("country", ""),
        "is_dormant": False,
        "risk_score": None,
    })
    await run_write(Q.UPSERT_ACCOUNT, {
        "id": receiver_id,
        "type": "unknown",
        "bank_code": "",
        "country": "",
        "is_dormant": False,
        "risk_score": None,
    })
    await run_write(Q.CREATE_TRANSFER, {
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "tx_id": tx["id"],
        "amount": float(tx.get("amount", 0)),
        "timestamp": tx.get("timestamp", ""),
        "channel": tx.get("channel", "unknown"),
    })

    if tx.get("device_id"):
        await run_write(Q.UPSERT_DEVICE, {
            "device_id": tx["device_id"],
            "ip_hash": tx.get("ip_address", "")[:8] if tx.get("ip_address") else "",
            "account_id": sender_id,
            "timestamp": tx.get("timestamp", ""),
        })


async def run() -> None:
    consumer = _build_consumer()
    consumer.subscribe([settings.kafka_topic_tx_raw])
    log.info("Graph sync consumer started")

    try:
        while True:
            msg = consumer.poll(timeout=0.1)
            if msg is None:
                await asyncio.sleep(0)
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    log.error("Kafka error", error=str(msg.error()))
                continue
            try:
                tx = json.loads(msg.value())
                await _sync_transaction(tx)
                consumer.commit(asynchronous=False)
            except Exception as exc:
                log.error("Graph sync error", error=str(exc))
    finally:
        consumer.close()
