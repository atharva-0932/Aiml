"""
Feature engineering pipeline.
Produces a feature vector from a raw transaction dict.
On the hot path, velocity comes from Redis counters.
On the cold path (training), window functions run in Snowpark.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "amount",
    "tx_count_1h",
    "tx_count_24h",
    "avg_amount_7d",
    "amount_zscore",
    "dormant_flag",
    "geo_distance_km",
    "device_switch_flag",
    "graph_in_degree",
    "graph_out_degree",
    "pagerank_score",
    "cycle_membership",
    "hop_depth",
    "is_high_value",
    "is_near_threshold",
    "hour_of_day",
    "day_of_week",
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two geo points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def extract_features(tx: dict[str, Any], prev_tx: dict[str, Any] | None = None) -> dict[str, float]:
    """
    Extract feature vector from a single transaction dict.
    tx must contain velocity fields (tx_count_1h, tx_count_24h) pre-populated
    from Redis by the calling consumer.
    """
    amount = float(tx.get("amount", 0))
    avg_7d = float(tx.get("avg_amount_7d", amount))
    std_7d = float(tx.get("stddev_amount_7d", 1)) or 1.0
    hour = 0
    dow = 0
    try:
        import datetime
        ts = tx.get("timestamp", "")
        if isinstance(ts, str):
            dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = ts
        hour = dt.hour
        dow = dt.weekday()
    except Exception:
        pass

    # Geo distance from previous transaction
    geo_dist = 0.0
    if prev_tx and tx.get("geo_lat") and prev_tx.get("geo_lat"):
        try:
            geo_dist = _haversine_km(
                float(prev_tx["geo_lat"]), float(prev_tx["geo_lon"]),
                float(tx["geo_lat"]), float(tx["geo_lon"]),
            )
        except Exception:
            pass

    return {
        "amount": amount,
        "tx_count_1h": float(tx.get("tx_count_1h", 0)),
        "tx_count_24h": float(tx.get("tx_count_24h", 0)),
        "avg_amount_7d": avg_7d,
        "amount_zscore": (amount - avg_7d) / std_7d,
        "dormant_flag": float(tx.get("dormant_flag", 0)),
        "geo_distance_km": geo_dist,
        "device_switch_flag": float(tx.get("device_switch_flag", 0)),
        "graph_in_degree": float(tx.get("graph_in_degree", 0)),
        "graph_out_degree": float(tx.get("graph_out_degree", 0)),
        "pagerank_score": float(tx.get("pagerank_score", 0)),
        "cycle_membership": float(tx.get("cycle_membership", 0)),
        "hop_depth": float(tx.get("hop_depth", 0)),
        "is_high_value": 1.0 if amount > 50_000 else 0.0,
        "is_near_threshold": 1.0 if 9_000 <= amount <= 9_999 else 0.0,  # structuring indicator
        "hour_of_day": float(hour),
        "day_of_week": float(dow),
    }


def features_to_array(features: dict[str, float]) -> np.ndarray:
    return np.array([features[col] for col in FEATURE_COLUMNS], dtype=np.float32)


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich a pandas DataFrame (from Snowpark.to_pandas()) with derived features.
    Used during model training on the cold path.
    """
    df = df.copy()
    df["amount_zscore"] = (df["amount"] - df.get("avg_amount_7d", df["amount"])) / (
        df.get("stddev_amount_7d", 1).replace(0, 1)
    )
    df["is_high_value"] = (df["amount"] > 50_000).astype(float)
    df["is_near_threshold"] = ((df["amount"] >= 9_000) & (df["amount"] <= 9_999)).astype(float)

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["hour_of_day"] = df["timestamp"].dt.hour.astype(float)
        df["day_of_week"] = df["timestamp"].dt.dayofweek.astype(float)

    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0

    return df[FEATURE_COLUMNS + ["aml_label"] if "aml_label" in df.columns else FEATURE_COLUMNS]
