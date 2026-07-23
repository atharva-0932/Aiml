"""
graph_sync consumer — MERGE Account nodes + TRANSFER edges into Neo4j.
Batches 50 messages per Neo4j transaction.

Run: PYTHONPATH=backend python3 -m kafka.consumers.graph_sync
"""
from __future__ import annotations

import asyncio
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException

from core.config import settings
from db.neo4j.driver import close_driver
from db.neo4j.queries import flush_transfers
from kafka.serde import deserialize_transaction
from kafka.topics import TX_RAW, ensure_topics

BATCH_SIZE = 50


def _build_consumer() -> Consumer:
    return Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": "graph_sync",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })


def _row_from_tx(tx: dict[str, Any]) -> dict[str, Any]:
    return {
        "transaction_id": tx["transaction_id"],
        "sender_account": tx["sender_account"],
        "receiver_account": tx["receiver_account"],
        "amount": float(tx["amount"]),
        "timestamp": tx.get("timestamp"),
        "bank": tx.get("bank"),
        "pattern_label": tx.get("pattern_label"),
    }


async def run() -> None:
    ensure_topics()
    consumer = _build_consumer()
    consumer.subscribe([TX_RAW])
    print(f"graph_sync listening on {TX_RAW} (group=graph_sync, batch={BATCH_SIZE})")

    batch: list[dict[str, Any]] = []
    pending_msgs: list = []
    total_written = 0

    async def flush() -> None:
        nonlocal batch, pending_msgs, total_written
        if not batch:
            return
        n = await flush_transfers(batch)
        consumer.commit(asynchronous=False)
        total_written += n
        print(f"Neo4j flush: wrote {n} transfers (total={total_written:,})")
        batch = []
        pending_msgs = []

    try:
        while True:
            msg = consumer.poll(timeout=0.1)
            if msg is None:
                if batch:
                    await flush()
                await asyncio.sleep(0)
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(msg.error())

            try:
                tx = deserialize_transaction(msg.value())
                batch.append(_row_from_tx(tx))
                pending_msgs.append(msg)
                if len(batch) >= BATCH_SIZE:
                    await flush()
            except Exception as exc:
                print(f"ERROR buffering/writing message: {exc}")
                batch = []
                pending_msgs = []
    finally:
        try:
            await flush()
        except Exception as exc:
            print(f"Final flush error: {exc}")
        consumer.close()
        await close_driver()


if __name__ == "__main__":
    asyncio.run(run())
