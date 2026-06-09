"""
Snowflake Writer Consumer — cold path async bulk writer.
Accumulates scored transactions in a buffer, then bulk-writes via
COPY INTO every FLUSH_INTERVAL seconds or when BUFFER_SIZE is reached.
Row-by-row INSERTs are never used — they are 100x slower than COPY INTO.
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import tempfile
import time
from typing import Any

from confluent_kafka import Consumer, KafkaError
from core.config import settings
from core.logging import get_logger

log = get_logger(__name__)

BUFFER_SIZE = 500
FLUSH_INTERVAL = 30  # seconds

TX_COLUMNS = [
    "id", "sender_account_id", "receiver_account_id", "amount", "currency",
    "transaction_type", "channel", "device_id", "merchant_id", "ip_address",
    "geo_lat", "geo_lon", "timestamp", "is_flagged", "aml_label",
]
RISK_COLUMNS = [
    "id", "account_id", "transaction_id", "risk_score", "anomaly_score",
    "classifier_score", "graph_risk_score", "composite_score", "risk_tier",
    "triggered_rules", "shap_values", "created_at",
]


def _build_consumer() -> Consumer:
    return Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": "aml-snowflake-writer",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "max.poll.interval.ms": 120000,  # allow time for bulk writes
    })


def _flush_buffer(buffer: list[dict]) -> None:
    """Bulk write buffer to Snowflake via staged CSV + COPY INTO."""
    if not buffer:
        return

    from db.snowflake.session import get_engine
    engine = get_engine()
    if engine is None:
        log.warning("Snowflake unavailable — skipping cold path write", count=len(buffer))
        return

    tx_rows = []
    risk_rows = []

    for item in buffer:
        tx = {k: item.get(k, "") for k in TX_COLUMNS}
        tx["is_flagged"] = True
        tx_rows.append(tx)

        risk = item.get("risk_score", {})
        import uuid
        from datetime import datetime, timezone
        risk_rows.append({
            "id": str(uuid.uuid4()),
            "account_id": item.get("sender_account_id", ""),
            "transaction_id": item.get("id", ""),
            "risk_score": risk.get("composite_score", 0),
            "anomaly_score": risk.get("anomaly_score", 0),
            "classifier_score": risk.get("classifier_score", 0),
            "graph_risk_score": risk.get("graph_risk_score", 0),
            "composite_score": risk.get("composite_score", 0),
            "risk_tier": risk.get("risk_tier", "HIGH"),
            "triggered_rules": json.dumps(risk.get("triggered_rules", [])),
            "shap_values": json.dumps(risk.get("shap_values", {})),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    with engine.connect() as conn:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=TX_COLUMNS)
            writer.writeheader()
            writer.writerows(tx_rows)
            tmp_tx = f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=RISK_COLUMNS)
            writer.writeheader()
            writer.writerows(risk_rows)
            tmp_risk = f.name

        try:
            conn.execute(f"PUT file://{tmp_tx} @aml_stage AUTO_COMPRESS=TRUE OVERWRITE=TRUE")
            conn.execute("COPY INTO transactions FROM @aml_stage "
                         "FILE_FORMAT=(TYPE=CSV FIELD_OPTIONALLY_ENCLOSED_BY='\"' SKIP_HEADER=1) "
                         "ON_ERROR=CONTINUE PURGE=TRUE")

            conn.execute(f"PUT file://{tmp_risk} @aml_stage AUTO_COMPRESS=TRUE OVERWRITE=TRUE")
            conn.execute("COPY INTO risk_events FROM @aml_stage "
                         "FILE_FORMAT=(TYPE=CSV FIELD_OPTIONALLY_ENCLOSED_BY='\"' SKIP_HEADER=1) "
                         "ON_ERROR=CONTINUE PURGE=TRUE")

            log.info("Flushed buffer to Snowflake", tx_count=len(tx_rows))
        finally:
            os.unlink(tmp_tx)
            os.unlink(tmp_risk)


async def run() -> None:
    consumer = _build_consumer()
    consumer.subscribe([settings.kafka_topic_tx_scored, settings.kafka_topic_tx_flagged])
    log.info("Snowflake writer consumer started")

    buffer: list[dict] = []
    last_flush = time.monotonic()

    try:
        while True:
            msg = consumer.poll(timeout=0.1)
            if msg is not None and not msg.error():
                try:
                    buffer.append(json.loads(msg.value()))
                except Exception as exc:
                    log.error("Parse error", error=str(exc))

            should_flush = (
                len(buffer) >= BUFFER_SIZE
                or (time.monotonic() - last_flush) >= FLUSH_INTERVAL
            )
            if should_flush and buffer:
                try:
                    _flush_buffer(buffer)
                    consumer.commit(asynchronous=False)
                except Exception as exc:
                    log.error("Snowflake flush error", error=str(exc))
                finally:
                    buffer.clear()
                    last_flush = time.monotonic()

            await asyncio.sleep(0)
    finally:
        if buffer:
            _flush_buffer(buffer)
        consumer.close()
