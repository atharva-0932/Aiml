"""Unit tests for Phase 1 synthetic transaction CSV quality."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from data_simulation.schema import PATTERN_LABELS

CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "transactions.csv"
REQUIRED = [
    "transaction_id",
    "timestamp",
    "sender_account",
    "receiver_account",
    "amount",
    "bank",
]


@pytest.fixture(scope="module")
def tx_df() -> pd.DataFrame:
    assert CSV_PATH.exists(), f"Missing {CSV_PATH} — run: PYTHONPATH=backend python -m data_simulation.seed"
    return pd.read_csv(CSV_PATH)


def test_pattern_labels_present(tx_df: pd.DataFrame):
    labels = set(
        tx_df["pattern_label"]
        .dropna()
        .astype(str)
        .loc[lambda s: s.str.len() > 0]
        .unique()
    )
    missing = set(PATTERN_LABELS) - labels
    assert not missing, f"Missing pattern labels: {sorted(missing)}"
    assert len(labels) >= 6


def test_flagged_rate(tx_df: pd.DataFrame):
    flagged = tx_df["pattern_label"].notna() & (
        tx_df["pattern_label"].astype(str).str.len() > 0
    )
    rate = float(flagged.mean())
    assert 0.05 <= rate <= 0.08, f"flagged rate {rate:.4%} not in 5–8%"


def test_no_null_required_fields(tx_df: pd.DataFrame):
    for col in REQUIRED:
        assert col in tx_df.columns, f"missing column {col}"
        n_null = int(tx_df[col].isna().sum())
        assert n_null == 0, f"{col} has {n_null} nulls"


def test_temporal_spread(tx_df: pd.DataFrame):
    ts = pd.to_datetime(tx_df["timestamp"], utc=True)
    span_days = (ts.max() - ts.min()).days
    assert span_days > 30, f"timestamp span {span_days} days is not > 30"
