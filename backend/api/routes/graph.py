"""Graph risk + neighbor visualization endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.auth import require_api_key
from db.neo4j.driver import get_driver
from db.redis.cache import cache_graph_risk, get_cached_graph_risk, get_risk_score
from graph.scorer import GraphRiskScorer

router = APIRouter(prefix="/graph", tags=["graph"])

_graph_scorer: GraphRiskScorer | None = None


def _scorer() -> GraphRiskScorer:
    global _graph_scorer
    if _graph_scorer is None:
        _graph_scorer = GraphRiskScorer()
    return _graph_scorer


async def _account_exists(account_id: str) -> bool:
    driver = get_driver()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (a:Account {id: $id}) RETURN a.id AS id LIMIT 1",
            id=account_id,
        )
        record = await result.single()
        return record is not None


@router.get("/account/{account_id}")
async def graph_account_risk(
    account_id: str,
    _: str = Depends(require_api_key),
) -> dict[str, Any]:
    if not await _account_exists(account_id):
        raise HTTPException(status_code=404, detail="account not found")

    cached = await get_cached_graph_risk(account_id)
    if cached is not None:
        return cached

    # Prefer full analytics; fall back to fast (no layering) if path queries stall.
    import asyncio

    try:
        result = await asyncio.wait_for(_scorer().score(account_id), timeout=12.0)
    except asyncio.TimeoutError:
        result = await _scorer().score(account_id, fast=True)
    await cache_graph_risk(account_id, result)
    return result


@router.get("/neighbors/{account_id}")
async def graph_neighbors(
    account_id: str,
    _: str = Depends(require_api_key),
) -> dict[str, Any]:
    if not await _account_exists(account_id):
        raise HTTPException(status_code=404, detail="account not found")

    driver = get_driver()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (center:Account {id: $account_id})
            OPTIONAL MATCH (center)-[r1:TRANSFER]-(n1:Account)
            OPTIONAL MATCH (n1)-[r2:TRANSFER]-(n2:Account)
            WHERE n2.id IS NULL OR n2.id <> center.id
            WITH center,
                 collect(DISTINCT n1) + collect(DISTINCT n2) AS neighbors,
                 collect(DISTINCT r1) + collect(DISTINCT r2) AS rels
            RETURN center.id AS center_id,
                   [n IN neighbors WHERE n IS NOT NULL | n.id] AS neighbor_ids,
                   [r IN rels WHERE r IS NOT NULL | {
                       source: startNode(r).id,
                       target: endNode(r).id,
                       amount: r.amount,
                       timestamp: r.timestamp,
                       transaction_id: r.transaction_id
                   }] AS edges
            """,
            account_id=account_id,
        )
        record = await result.single()

    if record is None:
        raise HTTPException(status_code=404, detail="account not found")

    node_ids = {account_id}
    for nid in record["neighbor_ids"] or []:
        if nid:
            node_ids.add(nid)

    nodes: list[dict[str, Any]] = []
    for nid in node_ids:
        # Prefer Redis composite if this id was a scored transaction's account —
        # account-level risk isn't stored; leave null unless graph cache exists.
        cached = await get_cached_graph_risk(nid)
        nodes.append({
            "id": nid,
            "risk_score": cached.get("graph_risk") if cached else None,
        })

    edges = []
    seen = set()
    for edge in record["edges"] or []:
        if not edge or not edge.get("source") or not edge.get("target"):
            continue
        key = (edge["source"], edge["target"], edge.get("transaction_id"))
        if key in seen:
            continue
        seen.add(key)
        edges.append({
            "source": edge["source"],
            "target": edge["target"],
            "amount": edge.get("amount"),
            "timestamp": edge.get("timestamp"),
        })

    return {"nodes": nodes, "edges": edges}
