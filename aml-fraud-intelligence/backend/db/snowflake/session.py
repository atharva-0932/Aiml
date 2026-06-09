import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from snowflake.sqlalchemy import URL

from core.config import settings
from core.logging import get_logger

log = get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="snowflake")


def _build_engine():
    url = URL(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        password=settings.snowflake_password,
        database=settings.snowflake_database,
        schema=settings.snowflake_schema,
        warehouse=settings.snowflake_warehouse,
        role=settings.snowflake_role,
    )
    return create_engine(
        url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


# Lazy engine — only built when Snowflake credentials are present
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        if not settings.snowflake_account:
            log.warning("Snowflake credentials not configured — cold path disabled")
            return None
        _engine = _build_engine()
    return _engine


def get_session() -> Session | None:
    engine = get_engine()
    if engine is None:
        return None
    factory = sessionmaker(bind=engine)
    return factory()


async def run_sync(fn: Callable, *args: Any) -> Any:
    """Wrap synchronous Snowflake calls for use in async FastAPI handlers."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, fn, *args)


def execute_query(sql: str, params: dict | None = None) -> list[dict]:
    """Execute a raw SQL query and return list of row dicts."""
    engine = get_engine()
    if engine is None:
        return []
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]
