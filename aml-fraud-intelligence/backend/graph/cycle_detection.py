"""Cycle detection — identifies circular fund flows in the Neo4j graph."""
from __future__ import annotations

from db.neo4j.driver import run_query
from db.neo4j import queries as Q


async def detect_cycles(lookback_days: int = 3) -> list[dict]:
    """
    Find accounts involved in circular fund transfers.
    Uses Cypher variable-length path matching within a time window.
    """
    cypher = """
    MATCH path = (a:Account)-[:TRANSFERRED_TO*3..6]->(a)
    WHERE ALL(r IN relationships(path)
          WHERE r.timestamp > datetime() - duration({days: $days}))
    WITH a, path,
         [r IN relationships(path) | r.amount]    AS amounts,
         [r IN relationships(path) | r.timestamp] AS timestamps
    RETURN a.id              AS account_id,
           length(path)      AS hops,
           amounts,
           timestamps,
           reduce(s=0.0, x IN amounts | s + x) AS total_amount
    ORDER BY total_amount DESC
    LIMIT 100
    """
    return await run_query(cypher, {"days": lookback_days})


async def get_cycle_participants(account_id: str) -> list[dict]:
    """Get all accounts in the same cycle as a given account."""
    cypher = """
    MATCH path = (a:Account {id: $account_id})-[:TRANSFERRED_TO*2..6]->(a)
    UNWIND nodes(path) AS n
    WITH DISTINCT n
    RETURN n.id AS account_id, n.bank_code AS bank_code, n.risk_score AS risk_score
    """
    return await run_query(cypher, {"account_id": account_id})
