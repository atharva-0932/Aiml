"""
Graph API router.
GET /graph/cycles         — all detected circular flows
GET /graph/layering       — multi-hop layering chains
GET /graph/mules          — mule account candidates
GET /accounts/{id}/graph-neighbors — 2-hop neighbors
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from core.security import verify_api_key
from graph.cycle_detection import detect_cycles
from graph.layering_detection import detect_layering
from graph.mule_detection import detect_mules, compute_pagerank
from graph.graph_features import get_neighbors

router = APIRouter(tags=["graph"])


@router.get("/graph/cycles")
async def get_cycles(lookback_days: int = 3, _: str = Depends(verify_api_key)):
    """Circular fund flow detection via Neo4j variable-length path matching."""
    return await detect_cycles(lookback_days=lookback_days)


@router.get("/graph/layering")
async def get_layering(
    min_hops: int = 4,
    max_hops: int = 8,
    lookback_days: int = 7,
    _: str = Depends(verify_api_key),
):
    """Multi-hop cross-bank layering chains."""
    return await detect_layering(
        min_hops=min_hops, max_hops=max_hops, lookback_days=lookback_days
    )


@router.get("/graph/mules")
async def get_mules(_: str = Depends(verify_api_key)):
    """Mule account candidates: high fan-in, low fan-out."""
    return await detect_mules()


@router.get("/graph/pagerank")
async def get_pagerank(_: str = Depends(verify_api_key)):
    """PageRank scores for all accounts (requires GDS projection)."""
    return await compute_pagerank()


@router.get("/accounts/{account_id}/graph-neighbors")
async def get_graph_neighbors(account_id: str, _: str = Depends(verify_api_key)):
    """
    2-hop neighbors of an account.
    Redis TTL=60s cache-aside applied automatically.
    """
    return await get_neighbors(account_id)
