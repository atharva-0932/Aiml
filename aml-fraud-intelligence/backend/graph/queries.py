"""
Neo4j Cypher / GDS graph analytics for AML pattern detection.
All functions are async and accept a neo4j AsyncSession.
"""
from __future__ import annotations

from typing import Any

from neo4j import AsyncSession


async def detect_cycles(session: AsyncSession, account_id: str) -> list[dict[str, Any]]:
    """
    Find circular fund flows (3–6 hop paths returning to origin).
    Deduplicate cycles by sorted node-id set.
    """
    result = await session.run(
        """
        MATCH path = (a:Account {id: $account_id})-[:TRANSFER*3..6]->(a)
        WITH path, length(path) AS hop_count,
             [n IN nodes(path) | n.id] AS account_ids
        RETURN hop_count, account_ids
        LIMIT 50
        """,
        account_id=account_id,
    )
    seen: set[tuple[str, ...]] = set()
    cycles: list[dict[str, Any]] = []
    async for record in result:
        ids = list(record["account_ids"])
        key_ids = ids[:-1] if ids and ids[0] == ids[-1] else ids
        key = tuple(sorted(set(key_ids)))
        if key in seen:
            continue
        seen.add(key)
        cycles.append({
            "hop_count": int(record["hop_count"]),
            "account_ids": ids,
        })
    return cycles


async def detect_mule(session: AsyncSession, account_id: str) -> dict[str, Any]:
    """
    Mule heuristic: 10+ inbound TRANSFER edges and >=90% of outbound
    volume going to a single destination.
    """
    result = await session.run(
        """
        MATCH (m:Account {id: $account_id})
        OPTIONAL MATCH ()-[in_rel:TRANSFER]->(m)
        WITH m, count(in_rel) AS inbound_count
        OPTIONAL MATCH (m)-[out_rel:TRANSFER]->(dest:Account)
        WITH inbound_count, dest.id AS dest_id, sum(coalesce(out_rel.amount, 0.0)) AS dest_volume
        WITH inbound_count,
             collect({dest: dest_id, vol: dest_volume}) AS outs
        WITH inbound_count,
             reduce(s = 0.0, o IN outs | s + CASE WHEN o.dest IS NULL THEN 0.0 ELSE coalesce(o.vol, 0.0) END) AS total_out,
             reduce(mx = 0.0, o IN outs |
               CASE
                 WHEN o.dest IS NULL THEN mx
                 WHEN coalesce(o.vol, 0.0) > mx THEN o.vol
                 ELSE mx
               END
             ) AS max_dest_volume
        RETURN inbound_count,
               CASE WHEN total_out = 0 THEN 0.0 ELSE max_dest_volume / total_out END AS top_destination_ratio
        """,
        account_id=account_id,
    )
    record = await result.single()
    if record is None:
        return {"is_mule": False, "inbound_count": 0, "top_destination_ratio": 0.0}

    inbound = int(record["inbound_count"] or 0)
    ratio = float(record["top_destination_ratio"] or 0.0)
    return {
        "is_mule": inbound >= 10 and ratio >= 0.90,
        "inbound_count": inbound,
        "top_destination_ratio": round(ratio, 4),
    }


async def detect_layering(session: AsyncSession, account_id: str) -> list[dict[str, Any]]:
    """
    Chains of 4+ sequential hops from this account crossing >= 2 banks.
    Bank is taken from TRANSFER relationship properties.
    """
    result = await session.run(
        """
        MATCH path = (a:Account {id: $account_id})-[rels:TRANSFER*4..6]->(end:Account)
        WITH length(path) AS chain_length,
             [r IN relationships(path) | coalesce(r.bank, '')] AS banks
        WITH chain_length, banks,
             reduce(
               s = [],
               b IN banks |
                 CASE WHEN b = '' OR b IN s THEN s ELSE s + b END
             ) AS unique_banks
        WHERE size(unique_banks) >= 2
        RETURN DISTINCT chain_length, unique_banks AS banks
        ORDER BY chain_length DESC
        LIMIT 25
        """,
        account_id=account_id,
    )
    chains: list[dict[str, Any]] = []
    async for record in result:
        chains.append({
            "chain_length": int(record["chain_length"]),
            "banks": list(record["banks"]),
        })
    return chains


async def get_pagerank(session: AsyncSession, account_id: str) -> float:
    """
    PageRank via GDS native projection (Account / TRANSFER), then stream.
    Returns 0.0 if account missing or GDS unavailable.
    """
    graph_name = f"aml_pr_{abs(hash(account_id)) % 10_000_000}"
    try:
        create = await session.run(
            """
            CALL gds.graph.project(
              $graph_name,
              'Account',
              'TRANSFER'
            )
            YIELD graphName
            RETURN graphName
            """,
            graph_name=graph_name,
        )
        await create.consume()

        result = await session.run(
            """
            CALL gds.pageRank.stream($graph_name)
            YIELD nodeId, score
            WITH gds.util.asNode(nodeId) AS n, score
            WHERE n.id = $account_id
            RETURN score
            LIMIT 1
            """,
            graph_name=graph_name,
            account_id=account_id,
        )
        record = await result.single()
        return float(record["score"]) if record is not None else 0.0
    except Exception:
        return 0.0
    finally:
        try:
            drop = await session.run(
                "CALL gds.graph.drop($graph_name, false) YIELD graphName RETURN graphName",
                graph_name=graph_name,
            )
            await drop.consume()
        except Exception:
            pass
