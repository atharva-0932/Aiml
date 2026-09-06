"""
Feature extraction for XGBoost — ordered columns must match training exactly.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, OrderedDict

import pandas as pd

MODEL_DIR = Path(__file__).parent / "models"
FEATURE_COLUMNS_PATH = MODEL_DIR / "feature_columns.json"

# Canonical training / inference order (9 features)
FEATURE_COLUMNS = [
    "amount",
    "amount_to_mean_ratio",
    "is_round_amount",
    "hour_of_day",
    "is_weekend",
    "tx_count_1h",
    "tx_volume_1h",
    "unique_receivers_24h",
    "time_since_last_tx",
]

# Filled at training time and persisted; default for cold start / tests
DEFAULT_AMOUNT_MEAN = 2500.0


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if value is None or value == "":
        return datetime.utcnow()
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def load_amount_mean() -> float:
    if FEATURE_COLUMNS_PATH.exists():
        meta = json.loads(FEATURE_COLUMNS_PATH.read_text())
        if isinstance(meta, dict) and "amount_mean" in meta:
            return float(meta["amount_mean"])
        # Older format: bare list of columns
    return DEFAULT_AMOUNT_MEAN


def save_feature_metadata(amount_mean: float, columns: list[str] | None = None) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "columns": columns or FEATURE_COLUMNS,
        "amount_mean": float(amount_mean),
    }
    FEATURE_COLUMNS_PATH.write_text(json.dumps(payload, indent=2))


def extract_features(
    tx: dict[str, Any],
    velocity: dict[str, float] | None = None,
    amount_mean: float | None = None,
) -> OrderedDict[str, float]:
    """
    Build the ordered feature vector for one transaction.

    velocity keys (optional, default 0 at train time):
      tx_count_1h, tx_volume_1h, unique_receivers_24h, time_since_last_tx
    """
    velocity = velocity or {}
    mean = float(amount_mean if amount_mean is not None else load_amount_mean())
    if mean <= 0:
        mean = DEFAULT_AMOUNT_MEAN

    amount = float(tx["amount"])
    ts = _parse_timestamp(tx.get("timestamp"))

    features: OrderedDict[str, float] = OrderedDict()
    features["amount"] = amount
    features["amount_to_mean_ratio"] = amount / mean
    features["is_round_amount"] = 1.0 if amount % 100 == 0 else 0.0
    features["hour_of_day"] = float(ts.hour)
    features["is_weekend"] = 1.0 if ts.weekday() >= 5 else 0.0
    features["tx_count_1h"] = float(velocity.get("tx_count_1h", 0.0))
    features["tx_volume_1h"] = float(velocity.get("tx_volume_1h", 0.0))
    features["unique_receivers_24h"] = float(velocity.get("unique_receivers_24h", 0.0))
    features["time_since_last_tx"] = float(velocity.get("time_since_last_tx", 0.0))
    return features


def features_to_list(features: OrderedDict[str, float]) -> list[float]:
    return [float(features[col]) for col in FEATURE_COLUMNS]


def extract_features_dataframe(df: pd.DataFrame, amount_mean: float | None = None) -> pd.DataFrame:
    """Vectorized-ish batch extraction for training (Redis counters = 0)."""
    mean = float(amount_mean if amount_mean is not None else df["amount"].mean())
    ts = pd.to_datetime(df["timestamp"], utc=True)
    out = pd.DataFrame({
        "amount": df["amount"].astype(float),
        "amount_to_mean_ratio": df["amount"].astype(float) / mean,
        "is_round_amount": (df["amount"].astype(float) % 100 == 0).astype(float),
        "hour_of_day": ts.dt.hour.astype(float),
        "is_weekend": (ts.dt.weekday >= 5).astype(float),
        "tx_count_1h": 0.0,
        "tx_volume_1h": 0.0,
        "unique_receivers_24h": 0.0,
        "time_since_last_tx": 0.0,
    })
    return out[FEATURE_COLUMNS]
