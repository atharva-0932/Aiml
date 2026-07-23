"""
GraphRiskScorer — combines Neo4j analytics into a 0–100 graph_risk score.

Composite (Phase 5+): 0.60 × XGBoost + 0.40 × Graph Risk
"""
from __future__ import annotations

from typing import Any

from db.neo4j.driver import get_driver
from graph.queries import detect_cycles, detect_layering, detect_mule, get_pagerank


class GraphRiskScorer:
    async def score(self, account_id: str, *, fast: bool = False) -> dict[str, Any]:
        """
        Full score uses cycles + mule + layering + PageRank.
        fast=True skips expensive variable-length path queries (streaming path).
        """
        driver = get_driver()
        async with driver.session() as session:
            mule = await detect_mule(session, account_id)
            pagerank = await get_pagerank(session, account_id)
            if fast:
                # Streaming: cycles are bounded (LIMIT); skip layering (path explosion).
                cycles = await detect_cycles(session, account_id)
                layering = []
            else:
                cycles = await detect_cycles(session, account_id)
                layering = await detect_layering(session, account_id)

        cycle_count = len(cycles)
        is_mule = bool(mule.get("is_mule"))
        layering_depth = max((c["chain_length"] for c in layering), default=0)

        graph_risk = 0.0
        flags: list[str] = []

        if cycle_count > 0:
            graph_risk += 40
            flags.append("CYCLE_DETECTED")
        if is_mule:
            graph_risk += 35
            flags.append("MULE_PATTERN")
        if layering_depth >= 4:
            graph_risk += 15
            flags.append("LAYERING_CHAIN")
        if pagerank > 0.5:
            graph_risk += 10
            flags.append("HIGH_PAGERANK")

        graph_risk = min(graph_risk, 100.0)

        return {
            "account_id": account_id,
            "graph_risk": float(graph_risk),
            "cycle_count": cycle_count,
            "is_mule": is_mule,
            "layering_depth": int(layering_depth),
            "pagerank": float(pagerank),
            "flags": flags,
        }
