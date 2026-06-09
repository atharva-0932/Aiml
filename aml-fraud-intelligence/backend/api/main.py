"""
FastAPI application entrypoint.
Run: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from api.routers import transactions, graph, risk, copilot, reports
from core.config import settings
from core.logging import configure_logging, get_logger
from db.neo4j.driver import close_driver, verify_connectivity
from db.redis.client import ping as redis_ping

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("AML platform starting up", env=settings.app_env)

    neo4j_ok = await verify_connectivity()
    redis_ok = await redis_ping()
    log.info("Infrastructure check", neo4j=neo4j_ok, redis=redis_ok)

    yield

    await close_driver()
    log.info("AML platform shut down")


app = FastAPI(
    title="AML Fraud Intelligence Platform",
    description=(
        "Production-grade Anti-Money Laundering platform with graph analytics, "
        "ML risk scoring, and GenAI investigator copilot."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
PREFIX = "/api/v1"
app.include_router(transactions.router, prefix=PREFIX)
app.include_router(graph.router, prefix=PREFIX)
app.include_router(risk.router, prefix=PREFIX)
app.include_router(copilot.router, prefix=PREFIX)
app.include_router(reports.router, prefix=PREFIX)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "neo4j": await verify_connectivity(),
        "redis": await redis_ping(),
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    return {
        "service": "AML Fraud Intelligence Platform",
        "docs": "/docs",
        "health": "/health",
    }
