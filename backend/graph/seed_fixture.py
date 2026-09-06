"""
Deterministic Neo4j fixture graph for unit tests.

Accounts:
  A–C circular flow
  D mule (10 inbound sources → 95% to Z)
  E–I layering chain across 4+ banks
  Extra sources G2 style: for mule use A,B,C,E,F,G,H,I,J,K

Run: PYTHONPATH=backend python3 -m graph.seed_fixture
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from db.neo4j.driver import close_driver, get_driver

# Stable string ids used by tests
A, B, C, D, E, F, G, H, I, J, K, Z = (
    "acct-A", "acct-B", "acct-C", "acct-D", "acct-E", "acct-F",
    "acct-G", "acct-H", "acct-I", "acct-J", "acct-K", "acct-Z",
)

BANKS = {
    A: "BOFA", B: "JPMC", C: "CITI", D: "HSBC",
    E: "BOFA", F: "JPMC", G: "CITI", H: "HSBC", I: "BARC",
    J: "DEUT", K: "SGBK", Z: "ANON",
}


async def clear_fixture(session) -> None:
    await session.run(
        """
        MATCH (n:Account)
        WHERE n.id STARTS WITH 'acct-'
        DETACH DELETE n
        """
    )


async def seed(session) -> None:
    """Load the deterministic AML fixture subgraph."""
    await clear_fixture(session)

    accounts = [A, B, C, D, E, F, G, H, I, J, K, Z]
    await session.run(
        """
        UNWIND $rows AS row
        MERGE (a:Account {id: row.id})
        SET a.bank = row.bank
        """,
        rows=[{"id": aid, "bank": BANKS[aid]} for aid in accounts],
    )

    now = datetime.now(timezone.utc).isoformat()
    transfers: list[dict] = []

    def add(sender: str, receiver: str, amount: float, label: str, tx_id: str) -> None:
        transfers.append({
            "transaction_id": tx_id,
            "sender_account": sender,
            "receiver_account": receiver,
            "amount": amount,
            "timestamp": now,
            "bank": BANKS[sender],
            "pattern_label": label,
        })

    # Circular flow A→B→C→A
    add(A, B, 10000.0, "circular_flow", "fix-cycle-1")
    add(B, C, 9900.0, "circular_flow", "fix-cycle-2")
    add(C, A, 9800.0, "circular_flow", "fix-cycle-3")

    # Mule D: 10 inbound from A,B,C,E,F,G,H,I,J,K then 95% to Z
    sources = [A, B, C, E, F, G, H, I, J, K]
    inbound_amounts = [1000.0] * 10
    total_in = sum(inbound_amounts)
    for i, src in enumerate(sources):
        add(src, D, inbound_amounts[i], "mule", f"fix-mule-in-{i}")
    add(D, Z, round(total_in * 0.95, 2), "mule", "fix-mule-out")

    # Layering E→F→G→H→I across distinct banks (4 hops)
    add(E, F, 50000.0, "layering", "fix-layer-1")
    add(F, G, 45000.0, "layering", "fix-layer-2")
    add(G, H, 40000.0, "layering", "fix-layer-3")
    add(H, I, 35000.0, "layering", "fix-layer-4")

    await session.run(
        """
        UNWIND $rows AS row
        MATCH (s:Account {id: row.sender_account})
        MATCH (r:Account {id: row.receiver_account})
        MERGE (s)-[t:TRANSFER {transaction_id: row.transaction_id}]->(r)
        SET t.amount = row.amount,
            t.timestamp = row.timestamp,
            t.bank = row.bank,
            t.pattern_label = row.pattern_label
        """,
        rows=transfers,
    )


async def main() -> None:
    driver = get_driver()
    async with driver.session() as session:
        await seed(session)
    print(
        "Fixture seeded: cycle A→B→C→A, mule D (10 inbound → Z), "
        "layering E→F→G→H→I"
    )
    await close_driver()


if __name__ == "__main__":
    asyncio.run(main())
