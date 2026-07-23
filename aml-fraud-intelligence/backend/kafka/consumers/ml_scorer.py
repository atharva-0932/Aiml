"""
ml_scorer consumer — velocity features from Redis, stub risk score,
cache score in Redis, upsert to Supabase.

Run: PYTHONPATH=backend python3 -m kafka.consumers.ml_scorer
"""
from __future__ import annotations

import asyncio
import random

from confluent_kafka import Consumer, KafkaError, KafkaException

from core.config import settings
from db.redis.cache import cache_risk_score, get_velocity_features, update_velocity
from db.redis.client import close_redis
from db.supabase.client import close_pool, upsert_transaction
from kafka.serde import deserialize_transaction
from kafka.topics import TX_RAW, ensure_topics


def _build_consumer() -> Consumer:
    return Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": "ml_scorer",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })


def _stub_risk_score(velocity: dict[str, float], tx: dict) -> float:
    """Placeholder until Phase 5 XGBoost. Returns 0–100."""
    base = random.uniform(0, 100)
    if velocity["tx_count_1h"] > 10:
        base = min(100.0, base + 15)
    if tx.get("pattern_label"):
        base = min(100.0, max(base, 70.0))
    return round(base, 2)


async def process_message(tx: dict) -> float:
    sender = tx["sender_account"]
    receiver = tx["receiver_account"]
    amount = float(tx["amount"])

    velocity = await get_velocity_features(sender)
    score = _stub_risk_score(velocity, tx)

    await cache_risk_score(tx["transaction_id"], score)
    await update_velocity(sender, receiver, amount)
    await upsert_transaction(tx, score)
    return score


async def run() -> None:
    ensure_topics()
    consumer = _build_consumer()
    consumer.subscribe([TX_RAW])
    print(f"ml_scorer listening on {TX_RAW} (group=ml_scorer)")
    processed = 0
    labeled_seen = 0

    try:
        while True:
            msg = consumer.poll(timeout=0.1)
            if msg is None:
                await asyncio.sleep(0)
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(msg.error())

            try:
                tx = deserialize_transaction(msg.value())
                score = await process_message(tx)
                consumer.commit(asynchronous=False)
                processed += 1
                label = tx.get("pattern_label")
                if label:
                    labeled_seen += 1
                # Log first few, every 100th, and every labeled AML pattern
                if processed % 100 == 0 or processed <= 5 or label:
                    print(
                        f"[{processed}] tx={tx['transaction_id'][:8]}… "
                        f"score={score:.2f} label={label!r} "
                        f"(labeled_total={labeled_seen})"
                    )
            except Exception as exc:
                print(f"ERROR processing message: {exc}")
    finally:
        consumer.close()
        await close_redis()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(run())
