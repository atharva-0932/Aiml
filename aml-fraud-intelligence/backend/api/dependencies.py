"""Shared FastAPI dependencies."""
from db.redis.client import redis_client
from db.neo4j.driver import get_driver


async def get_redis():
    return redis_client


async def get_neo4j():
    return get_driver()
