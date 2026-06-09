"""
ML Scorer Consumer — the hot-path core.
Subscribes to transactions.raw, scores each transaction using pre-loaded
models + Redis velocity features, writes to Redis cache, routes to
transactions.scored or transactions.flagged.

Models are loaded ONCE at startup — never per message.
"""
from __future__ import annotations

import asyncio
import json

from confluent_kafka import Consumer, Producer, KafkaError
from core.config import settings
from core.logging import get_logger
from db.redis import cache as redis_cache
from kafka import topics as T

log = get_logger(__name__)

_scorer = None  # Loaded lazily at startup


def _load_scorer():
    global _scorer
    if _scorer is None:
        from ml.risk_scorer import CompositeRiskScorer
        _scorer = CompositeRiskScorer()
        log.info("CompositeRiskScorer loaded into memory")
    return _scorer


def _build_consumer() -> Consumer:
    return Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": "aml-ml-scorer",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "max.poll.interval.ms": 30000,
    })


def _build_producer() -> Producer:
    return Producer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "linger.ms": 5,
        "compression.type": "lz4",
    })


async def run() -> None:
    scorer = _load_scorer()
    consumer = _build_consumer()
    producer = _build_producer()
    consumer.subscribe([T.TX_RAW])
    log.info("ML scorer consumer started", topic=T.TX_RAW)

    try:
        while True:
            msg = consumer.poll(timeout=0.1)
            if msg is None:
                await asyncio.sleep(0)
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    log.error("Kafka consumer error", error=str(msg.error()))
                continue

            try:
                tx = json.loads(msg.value())
                account_id = tx.get("sender_account_id", "")

                # Pull velocity features from Redis (<1ms)
                velocity = await redis_cache.get_velocity(account_id)
                tx.update(velocity)

                # Score in-memory
                score = scorer.score(tx)

                # Cache in Redis (write-through)
                await redis_cache.cache_risk_score(account_id, tx["id"], score)

                # Route to downstream topic
                dest_topic = T.TX_FLAGGED if score["composite_score"] >= T.THRESHOLD_HIGH else T.TX_SCORED
                payload = json.dumps({**tx, "risk_score": score}, default=str).encode()
                producer.produce(dest_topic, key=tx["id"].encode(), value=payload)
                producer.poll(0)

                # Manual commit only after successful processing
                consumer.commit(asynchronous=False)

            except Exception as exc:
                log.error("Error processing transaction", error=str(exc))

    finally:
        consumer.close()
        log.info("ML scorer consumer stopped")
