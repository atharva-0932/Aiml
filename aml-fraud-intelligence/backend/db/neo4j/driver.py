"""
Neo4j async driver with connection pooling.
All Cypher queries go through this module.
"""
from __future__ import annotations

from neo4j import AsyncGraphDatabase, AsyncDriver
from core.config import settings
from core.logging import get_logger

log = get_logger(__name__)

_driver: AsyncDriver | None = None


def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_pool_size=50,
            connection_timeout=5.0,
        )
        log.info("Neo4j driver initialised", uri=settings.neo4j_uri)
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver:
        await _driver.close()
        _driver = None


async def run_query(cypher: str, params: dict | None = None) -> list[dict]:
    """Execute a read query and return list of record dicts."""
    driver = get_driver()
    async with driver.session() as session:
        result = await session.run(cypher, params or {})
        records = await result.data()
        return records


async def run_write(cypher: str, params: dict | None = None) -> list[dict]:
    """Execute a write query inside an explicit write transaction."""
    driver = get_driver()
    async with driver.session() as session:
        result = await session.execute_write(
            lambda tx: tx.run(cypher, params or {}).data()
        )
        return result


async def verify_connectivity() -> bool:
    try:
        driver = get_driver()
        await driver.verify_connectivity()
        return True
    except Exception as exc:
        log.error("Neo4j connectivity check failed", error=str(exc))
        return False
