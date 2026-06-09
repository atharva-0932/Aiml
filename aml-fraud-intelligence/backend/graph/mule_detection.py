"""Mule account detection — fan-in / fan-out centrality analysis."""
from __future__ import annotations

from db.neo4j.driver import run_query
from db.neo4j import queries as Q


async def detect_mules(min_in_degree: int = 8, max_out_degree: int = 3) -> list[dict]:
    """
    Identify mule accounts: many senders → account → few destinations.
    High in-degree + low out-degree + high concentration_ratio = mule signal.
    """
    return await run_query(Q.MULE_DETECTION, {})


async def get_mule_profile(account_id: str) -> dict:
    """Full mule profile for a specific account."""
    cypher = """
    MATCH (a:Account {id: $account_id})
    WITH a,
         [(a)<-[:TRANSFERRED_TO]-(s) | s.id] AS senders,
         [(a)-[:TRANSFERRED_TO]->(d) | d.id] AS destinations
    RETURN a.id                           AS account_id,
           size(senders)                  AS in_degree,
           size(destinations)             AS out_degree,
           senders[..10]                  AS top_senders,
           destinations                   AS destinations,
           toFloat(size(destinations)) / size(senders) AS concentration_ratio
    """
    result = await run_query(cypher, {"account_id": account_id})
    return result[0] if result else {}


async def compute_pagerank() -> list[dict]:
    """Run PageRank via Neo4j GDS to score account centrality."""
    cypher = """
    CALL gds.pageRank.stream('transactionGraph', {
        dampingFactor: 0.85,
        maxIterations: 20
    })
    YIELD nodeId, score
    RETURN gds.util.asNode(nodeId).id AS account_id, score
    ORDER BY score DESC
    LIMIT 200
    """
    return await run_query(cypher)
