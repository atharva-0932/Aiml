"""Layering detection — identifies multi-hop fund movement chains."""
from __future__ import annotations

from db.neo4j.driver import run_query


async def detect_layering(min_hops: int = 4, max_hops: int = 8, lookback_days: int = 7) -> list[dict]:
    """
    Find deep multi-hop transfer chains crossing bank boundaries.
    Cross-bank transfers are a strong layering signal.
    """
    cypher = """
    MATCH path = (src:Account)-[:TRANSFERRED_TO*$min_hops..$max_hops]->(dst:Account)
    WHERE src <> dst
      AND ALL(r IN relationships(path) WHERE r.timestamp > datetime() - duration({days: $days}))
      AND src.bank_code <> dst.bank_code
    WITH src, dst, path,
         [r IN relationships(path) | r.amount] AS amounts
    RETURN src.id                                                           AS source_account,
           dst.id                                                           AS dest_account,
           length(path)                                                     AS depth,
           reduce(total=0.0, r IN relationships(path) | total + r.amount)  AS total_moved,
           amounts,
           src.bank_code                                                    AS src_bank,
           dst.bank_code                                                    AS dst_bank
    ORDER BY depth DESC, total_moved DESC
    LIMIT 50
    """
    return await run_query(cypher, {
        "min_hops": min_hops,
        "max_hops": max_hops,
        "days": lookback_days,
    })


async def get_layering_path(source_id: str, dest_id: str) -> list[dict]:
    """Get shortest layering path between two accounts."""
    cypher = """
    MATCH path = shortestPath(
        (src:Account {id: $source_id})-[:TRANSFERRED_TO*..10]->(dst:Account {id: $dest_id})
    )
    RETURN [n IN nodes(path) | n.id]     AS account_chain,
           [r IN relationships(path) | r.amount] AS amounts,
           length(path)                  AS depth
    """
    return await run_query(cypher, {"source_id": source_id, "dest_id": dest_id})
