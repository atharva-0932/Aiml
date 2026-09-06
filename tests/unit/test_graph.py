"""
Unit tests for Neo4j graph AML analytics (Phase 4).

Requires running Neo4j with GDS (docker compose neo4j service).
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from db.neo4j.driver import close_driver, get_driver
from graph.queries import detect_cycles, detect_layering, detect_mule
from graph.scorer import GraphRiskScorer
from graph.seed_fixture import A, D, E, seed


@pytest_asyncio.fixture
async def neo4j_fixture():
    driver = get_driver()
    async with driver.session() as session:
        await seed(session)
    yield
    await close_driver()


@pytest.mark.asyncio
async def test_cycle_detection(neo4j_fixture):
    driver = get_driver()
    async with driver.session() as session:
        cycles = await detect_cycles(session, A)
    assert len(cycles) >= 1
    assert any(c["hop_count"] >= 3 for c in cycles)


@pytest.mark.asyncio
async def test_mule_detection(neo4j_fixture):
    driver = get_driver()
    async with driver.session() as session:
        mule = await detect_mule(session, D)
    assert mule["inbound_count"] >= 10
    assert mule["is_mule"] is True
    assert mule["top_destination_ratio"] >= 0.90


@pytest.mark.asyncio
async def test_layering_detection(neo4j_fixture):
    driver = get_driver()
    async with driver.session() as session:
        chains = await detect_layering(session, E)
    assert len(chains) >= 1
    assert max(c["chain_length"] for c in chains) >= 4
    assert any(len(c["banks"]) >= 2 for c in chains)


@pytest.mark.asyncio
async def test_graph_risk_scorer(neo4j_fixture):
    scorer = GraphRiskScorer()
    result = await scorer.score(A)
    assert result["account_id"] == A
    assert result["cycle_count"] >= 1
    assert "CYCLE_DETECTED" in result["flags"]
    assert result["graph_risk"] >= 40
