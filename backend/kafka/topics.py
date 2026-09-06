"""Kafka topic helpers — ensure transactions.raw exists on startup."""
from __future__ import annotations

from confluent_kafka.admin import AdminClient, NewTopic

from core.config import settings

TX_RAW = settings.kafka_topic_tx_raw


def ensure_topics(
    bootstrap_servers: str | None = None,
    partitions: int = 4,
    replication_factor: int = 1,
) -> None:
    """Create transactions.raw if missing (4 partitions, RF=1)."""
    servers = bootstrap_servers or settings.kafka_bootstrap_servers
    admin = AdminClient({"bootstrap.servers": servers})
    topic = NewTopic(
        TX_RAW,
        num_partitions=partitions,
        replication_factor=replication_factor,
    )
    futures = admin.create_topics([topic])
    for name, future in futures.items():
        try:
            future.result()
            print(f"Created topic: {name} (partitions={partitions}, rf={replication_factor})")
        except Exception as exc:
            # TopicAlreadyExistsError is fine
            if "already exists" in str(exc).lower() or "TOPIC_ALREADY_EXISTS" in str(exc):
                print(f"Topic already exists: {name}")
            else:
                raise
