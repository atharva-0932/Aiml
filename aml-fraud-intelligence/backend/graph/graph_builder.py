"""
Graph builder — bulk-loads the seeded transaction CSV into Neo4j.
Used once after seeding to populate the graph from existing data.
Real-time writes happen via the graph_sync Kafka consumer.
"""
from __future__ import annotations

import csv
from pathlib import Path

from db.neo4j.driver import run_write, run_query
from db.neo4j import queries as Q
from core.logging import get_logger

log = get_logger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"


async def setup_schema() -> None:
    """Create Neo4j constraints and indexes."""
    constraints = [
        "CREATE CONSTRAINT account_id_unique IF NOT EXISTS FOR (a:Account) REQUIRE a.id IS UNIQUE",
        "CREATE CONSTRAINT customer_id_unique IF NOT EXISTS FOR (c:Customer) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT device_id_unique IF NOT EXISTS FOR (d:Device) REQUIRE d.id IS UNIQUE",
    ]
    for stmt in constraints:
        await run_write(stmt)
    log.info("Neo4j schema constraints created")


async def load_accounts_from_csv(path: Path | None = None) -> int:
    path = path or DATA_DIR / "accounts.csv"
    count = 0
    with open(path) as f:
        for row in csv.DictReader(f):
            await run_write(Q.UPSERT_ACCOUNT, {
                "id": row["id"],
                "type": row.get("account_type", "unknown"),
                "bank_code": row.get("bank_code", ""),
                "country": row.get("country", ""),
                "is_dormant": row.get("is_dormant", "false").lower() == "true",
                "risk_score": None,
            })
            count += 1
    log.info("Accounts loaded into Neo4j", count=count)
    return count


async def load_transactions_from_csv(path: Path | None = None, batch_size: int = 500) -> int:
    path = path or DATA_DIR / "transactions.csv"
    count = 0
    batch = []

    with open(path) as f:
        for row in csv.DictReader(f):
            batch.append(row)
            if len(batch) >= batch_size:
                await _write_batch(batch)
                count += len(batch)
                batch = []
                if count % 5000 == 0:
                    log.info("Graph load progress", transactions=count)

    if batch:
        await _write_batch(batch)
        count += len(batch)

    log.info("Transactions loaded into Neo4j", count=count)
    return count


async def _write_batch(rows: list[dict]) -> None:
    for row in rows:
        if not row.get("sender_account_id") or not row.get("receiver_account_id"):
            continue
        try:
            await run_write(Q.CREATE_TRANSFER, {
                "sender_id": row["sender_account_id"],
                "receiver_id": row["receiver_account_id"],
                "tx_id": row["id"],
                "amount": float(row.get("amount", 0)),
                "timestamp": row.get("timestamp", ""),
                "channel": row.get("channel", "unknown"),
            })
        except Exception as exc:
            log.warning("Failed to write transaction edge", tx_id=row.get("id"), error=str(exc))


async def project_gds_graph() -> None:
    """Project in-memory GDS graph for PageRank and other algorithms."""
    try:
        # Drop existing projection if any
        await run_write("CALL gds.graph.drop('transactionGraph', false) YIELD graphName")
    except Exception:
        pass
    await run_write(Q.GDS_GRAPH_PROJECT)
    log.info("GDS graph projected")


async def build_full_graph() -> None:
    await setup_schema()
    await load_accounts_from_csv()
    await load_transactions_from_csv()
    await project_gds_graph()
    log.info("Full graph build complete")
