"""
Alert Dispatcher Consumer.
Subscribes to transactions.flagged and publishes real-time alerts to the
Redis Pub/Sub channel consumed by the live dashboard SSE endpoint.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from confluent_kafka import Consumer, KafkaError
from core.config import settings
from core.logging import get_logger
from db.redis.cache import publish_alert
from kafka import topics as T

log = get_logger(__name__)


def _build_consumer() -> Consumer:
    return Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": "aml-alert-dispatcher",
        "auto.offset.reset": "latest",   # only new alerts, not historical replay
        "enable.auto.commit": False,
    })


async def run() -> None:
    consumer = _build_consumer()
    consumer.subscribe([T.TX_FLAGGED])
    log.info("Alert dispatcher consumer started")

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
                data = json.loads(msg.value())
                risk = data.get("risk_score", {})
                alert = {
                    "account_id": data.get("sender_account_id"),
                    "tx_id": data.get("id"),
                    "composite_score": risk.get("composite_score", 0),
                    "risk_tier": risk.get("risk_tier", "HIGH"),
                    "triggered_rules": risk.get("triggered_rules", []),
                    "amount": data.get("amount"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await publish_alert(alert)
                consumer.commit(asynchronous=False)
            except Exception as exc:
                log.error("Alert dispatch error", error=str(exc))
    finally:
        consumer.close()
