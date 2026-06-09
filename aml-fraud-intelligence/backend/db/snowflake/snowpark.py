"""
Snowpark session + feature engineering pushed into Snowflake.
Window functions run inside the warehouse — no pandas memory pressure.
"""
from __future__ import annotations

from core.config import settings
from core.logging import get_logger

log = get_logger(__name__)

_snowpark_session = None


def get_snowpark_session():
    global _snowpark_session
    if _snowpark_session is not None:
        return _snowpark_session

    if not settings.snowflake_account:
        log.warning("Snowflake not configured — Snowpark unavailable")
        return None

    try:
        from snowflake.snowpark import Session

        _snowpark_session = Session.builder.configs({
            "account": settings.snowflake_account,
            "user": settings.snowflake_user,
            "password": settings.snowflake_password,
            "database": settings.snowflake_database,
            "schema": settings.snowflake_schema,
            "warehouse": settings.snowflake_warehouse,
            "role": settings.snowflake_role,
        }).create()
        log.info("Snowpark session established")
        return _snowpark_session
    except Exception as exc:
        log.error("Failed to create Snowpark session", error=str(exc))
        return None


def compute_velocity_features(session=None):
    """
    Compute per-account velocity and behavioural features using Snowflake
    window functions. Returns a Snowpark DataFrame.
    All computation happens inside the warehouse.
    """
    from snowflake.snowpark import functions as F
    from snowflake.snowpark.window import Window

    session = session or get_snowpark_session()
    if session is None:
        raise RuntimeError("Snowpark session unavailable")

    df = session.table("transactions")

    w_1h = (
        Window.partition_by("sender_account_id")
        .order_by(F.col("timestamp").cast("timestamp").cast("bigint"))
        .range_between(-3600, 0)
    )
    w_24h = (
        Window.partition_by("sender_account_id")
        .order_by(F.col("timestamp").cast("timestamp").cast("bigint"))
        .range_between(-86400, 0)
    )
    w_7d = (
        Window.partition_by("sender_account_id")
        .order_by(F.col("timestamp").cast("timestamp").cast("bigint"))
        .range_between(-604800, 0)
    )
    w_30d = (
        Window.partition_by("sender_account_id")
        .order_by(F.col("timestamp").cast("timestamp").cast("bigint"))
        .range_between(-2592000, 0)
    )

    return df.with_columns(
        [
            "tx_count_1h",
            "tx_count_24h",
            "avg_amount_7d",
            "avg_amount_30d",
            "stddev_amount_30d",
        ],
        [
            F.count("id").over(w_1h),
            F.count("id").over(w_24h),
            F.avg("amount").over(w_7d),
            F.avg("amount").over(w_30d),
            F.stddev("amount").over(w_30d),
        ],
    )


def fetch_training_features(session=None) -> "pd.DataFrame":
    """Fetch feature-engineered dataset as a pandas DataFrame for model training."""
    session = session or get_snowpark_session()
    if session is None:
        raise RuntimeError("Snowpark session unavailable")

    df = compute_velocity_features(session)
    return df.to_pandas()
