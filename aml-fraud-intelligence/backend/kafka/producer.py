"""
Kafka producer — streams data/transactions.csv into transactions.raw.

Run: PYTHONPATH=backend python3 -m kafka.producer [--delay 0.01]
"""
from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

from confluent_kafka import Producer

from core.config import settings
from kafka.serde import normalize_pattern_label, serialize_transaction
from kafka.topics import TX_RAW, ensure_topics

CSV_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "transactions.csv"


def _delivery_report(err, msg) -> None:
    if err is not None:
        print(f"Delivery failed for {msg.key()}: {err}")


def run(delay: float = 0.01, csv_path: Path = CSV_PATH) -> None:
    ensure_topics()
    producer = Producer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "acks": "1",
        "linger.ms": 5,
    })

    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV not found: {csv_path}. Run: PYTHONPATH=backend python -m data_simulation.seed"
        )

    print(f"Publishing from {csv_path} → {TX_RAW} (delay={delay}s)")
    sent = 0
    labeled = 0
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            payload = serialize_transaction(row)
            if normalize_pattern_label(row.get("pattern_label")):
                labeled += 1

            producer.produce(
                TX_RAW,
                key=row["transaction_id"].encode("utf-8"),
                value=payload,
                callback=_delivery_report,
            )
            producer.poll(0)
            sent += 1
            if sent % 1000 == 0:
                producer.flush()
                print(f"  published {sent:,} messages ({labeled:,} labeled)...")
            if delay > 0:
                time.sleep(delay)

    producer.flush()
    print(f"Done. Published {sent:,} messages ({labeled:,} with pattern_label) to {TX_RAW}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish transactions.csv to Kafka")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.01,
        help="Seconds between messages (default: 0.01)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=CSV_PATH,
        help="Path to transactions CSV",
    )
    args = parser.parse_args()
    run(delay=args.delay, csv_path=args.csv)
