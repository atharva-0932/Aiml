"""
FastAPI application — AML Fraud Intelligence API.

Run:
  uvicorn api.main:app --reload --port 8000 --app-dir backend
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import require_api_key
from api.routes import alerts, graph, transactions
from api.store import store
from core.config import settings
from db.neo4j.driver import close_driver, get_driver
from db.redis.client import close_redis, get_redis


async def _check_redis() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception:
        return False


async def _check_neo4j() -> bool:
    try:
        driver = get_driver()
        await driver.verify_connectivity()
        return True
    except Exception:
        return False


def _check_kafka() -> bool:
    try:
        from confluent_kafka.admin import AdminClient

        admin = AdminClient({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "socket.timeout.ms": 2000,
        })
        md = admin.list_topics(timeout=2)
        return md is not None
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    n = store.load()
    get_redis()
    get_driver()
    print(f"API startup: loaded {n:,} transactions from CSV")
    yield
    await close_redis()
    await close_driver()
    print("API shutdown complete")


app = FastAPI(
    title="AML Fraud Intelligence API",
    version="0.6.0",
    description="Transactions, alerts, and graph investigation endpoints.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions.router)
app.include_router(alerts.router)
app.include_router(graph.router)


@app.get("/health")
async def health(_: str = Depends(require_api_key)):
    redis_ok = await _check_redis()
    neo4j_ok = await _check_neo4j()
    kafka_ok = _check_kafka()
    status = "ok" if (redis_ok and neo4j_ok) else "degraded"
    return {
        "status": status,
        "kafka": "connected" if kafka_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
        "neo4j": "connected" if neo4j_ok else "disconnected",
        "transactions_loaded": len(store.all()),
    }


@app.get("/")
async def root():
    return {
        "service": "AML Fraud Intelligence API",
        "docs": "/docs",
        "health": "/health",
    }
