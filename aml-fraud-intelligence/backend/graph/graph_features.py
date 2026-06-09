"""
Extract graph-derived features for a given account.
These features are merged into the ML feature vector.
"""
from __future__ import annotations

from db.neo4j.driver import run_query
from db.neo4j import queries as Q
from db.redis.cache import get_graph_neighbors, cache_graph_neighbors


async def get_account_graph_features(account_id: str) -> dict:
    """
    Returns graph metrics for a single account.
    Cache-aside: Redis TTL=60s, Neo4j fallback.
    """
    cached = await get_graph_neighbors(account_id)
    if cached and "in_degree" in cached:
        return cached

    result = await run_query(Q.GET_ACCOUNT_GRAPH_METRICS, {"account_id": account_id})
    if not result:
        return {
            "graph_in_degree": 0,
            "graph_out_degree": 0,
            "cycle_membership": 0,
            "pagerank_score": 0.0,
            "hop_depth": 0,
        }

    row = result[0]
    features = {
        "graph_in_degree": row.get("in_degree", 0),
        "graph_out_degree": row.get("out_degree", 0),
        "cycle_membership": 1 if (row.get("cycle_count", 0) or 0) > 0 else 0,
        "pagerank_score": 0.0,  # filled in separately via batch PageRank
        "hop_depth": 0,
    }

    await cache_graph_neighbors(account_id, features)
    return features


async def get_neighbors(account_id: str) -> list[dict]:
    """2-hop neighbor list for graph visualisation."""
    cached = await get_graph_neighbors(f"nbr:{account_id}")
    if cached:
        return cached

    result = await run_query(Q.GET_NEIGHBORS_2HOP, {"account_id": account_id})
    await cache_graph_neighbors(f"nbr:{account_id}", result)
    return result
