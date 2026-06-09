"""
Kafka producer wrapper.
linger.ms=5 enables micro-batching for throughput without hurting latency.
partition by sender_account_id guarantees ordering per account.
"""
from __future__ import annotations

import json
from typing import Any

from confluent_kafka import Producer, KafkaException
from core.config import settings
from core.logging import get_logger
from kafka import topics as T

log = get_logger(__name__)

_producer: Producer | None = None


def get_producer() -> Producer:
    global _producer
    if _producer is None:
        _producer = Producer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "linger.ms": 5,
            "compression.type": "lz4",
            "acks": "all",
            "retries": 3,
            "enable.idempotence": True,
        })
    return _producer


def _delivery_report(err, msg):
    if err:
        log.error("Kafka delivery failed", topic=msg.topic(), error=str(err))


def publish(topic: str, key: str, payload: dict[str, Any]) -> None:
    producer = get_producer()
    producer.produce(
        topic=topic,
        key=key.encode("utf-8"),
        value=json.dumps(payload, default=str).encode("utf-8"),
        on_delivery=_delivery_report,
    )
    producer.poll(0)  # non-blocking flush trigger


async def publish_transaction(tx: dict) -> None:
    """Publish raw transaction to transactions.raw, keyed by sender_account_id."""
    publish(T.TX_RAW, tx["sender_account_id"], tx)


async def publish_sar_request(account_id: str, context: dict) -> None:
    publish(T.SAR_REQUESTS, account_id, {"account_id": account_id, **context})


def flush() -> None:
    get_producer().flush(timeout=5.0)
