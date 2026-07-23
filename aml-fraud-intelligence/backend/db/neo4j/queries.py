"""
Batched Neo4j graph writes for the graph_sync consumer.
"""
from __future__ import annotations

from typing import Any

from neo4j import AsyncTransaction

from db.neo4j.driver import get_driver

MERGE_BATCH_CYPHER = """
UNWIND $rows AS row
MERGE (s:Account {id: row.sender_account})
  ON CREATE SET s.bank = row.bank
  ON MATCH SET s.bank = coalesce(s.bank, row.bank)
MERGE (r:Account {id: row.receiver_account})
MERGE (s)-[t:TRANSFER {transaction_id: row.transaction_id}]->(r)
SET t.amount = row.amount,
    t.timestamp = row.timestamp,
    t.bank = row.bank,
    t.pattern_label = row.pattern_label
"""


async def _write_batch(tx: AsyncTransaction, rows: list[dict[str, Any]]) -> None:
    await tx.run(MERGE_BATCH_CYPHER, rows=rows)


async def flush_transfers(rows: list[dict[str, Any]]) -> int:
    """Write a batch of transfer edges in a single Neo4j transaction."""
    if not rows:
        return 0
    driver = get_driver()
    async with driver.session() as session:
        await session.execute_write(_write_batch, rows)
    return len(rows)
