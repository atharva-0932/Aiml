"""Unit tests for Phase 5 ML feature extraction, training split, and scorers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from ml.features import FEATURE_COLUMNS, extract_features
from ml.scorer import CompositeRiskScorer, XGBoostScorer, classify_tier
from ml.train import temporal_split

MODEL_DIR = Path(__file__).resolve().parents[2] / "backend" / "ml" / "models"


def test_feature_extraction():
    tx = {
        "amount": 9500.0,
        "timestamp": "2026-07-23T14:30:00+00:00",
        "sender_account": "a1",
        "receiver_account": "a2",
    }
    velocity = {
        "tx_count_1h": 3.0,
        "tx_volume_1h": 12000.0,
        "unique_receivers_24h": 2.0,
        "time_since_last_tx": 45.0,
    }
    feats = extract_features(tx, velocity=velocity, amount_mean=2500.0)
    assert list(feats.keys()) == FEATURE_COLUMNS
    assert len(feats) == 9
    assert isinstance(feats["amount"], float)
    assert feats["amount"] == 9500.0
    assert feats["is_round_amount"] == 1.0  # 9500 % 100 == 0
    assert feats["hour_of_day"] == 14.0
    assert feats["is_weekend"] == 0.0  # Thursday
    assert feats["tx_count_1h"] == 3.0
    assert feats["time_since_last_tx"] == 45.0


def test_composite_scorer():
    scorer = CompositeRiskScorer()

    # Boundary tiers via classify_tier on composite-like scores
    assert classify_tier(29) == "LOW"
    assert classify_tier(30) == "MEDIUM"
    assert classify_tier(70) == "MEDIUM"
    assert classify_tier(90) == "HIGH"
    assert classify_tier(90.1) == "CRITICAL"

    # Explicit composite math + tiers at boundaries of the weighted score
    low = scorer.composite(xgb_score=0.0, graph_risk=0.0)
    assert low["composite_score"] == 0.0
    assert low["tier"] == "LOW"

    # 0.60*50 + 0.40*0 = 30 → MEDIUM
    med = scorer.composite(xgb_score=50.0, graph_risk=0.0)
    assert med["composite_score"] == 30.0
    assert med["tier"] == "MEDIUM"

    # 0.60*100 + 0.40*25 = 70 → MEDIUM (not HIGH until >70)
    edge_high = scorer.composite(xgb_score=100.0, graph_risk=25.0)
    assert edge_high["composite_score"] == 70.0
    assert edge_high["tier"] == "MEDIUM"

    # 0.60*100 + 0.40*100 = 100 → CRITICAL
    crit = scorer.composite(xgb_score=100.0, graph_risk=100.0)
    assert crit["composite_score"] == 100.0
    assert crit["tier"] == "CRITICAL"

    # >70 HIGH
    high = scorer.composite(xgb_score=100.0, graph_risk=30.0)  # 72
    assert high["composite_score"] == 72.0
    assert high["tier"] == "HIGH"

    # Exactly 90 is HIGH; >90 CRITICAL — check via classify_tier(90)
    assert classify_tier(90) == "HIGH"


def test_xgboost_scorer_loads():
    model_path = MODEL_DIR / "model.json"
    if not model_path.exists():
        pytest.skip("model.json missing — run ml.train first")
    scorer = XGBoostScorer(model_dir=MODEL_DIR)
    feats = extract_features(
        {"amount": 9999.0, "timestamp": "2026-07-23T03:00:00+00:00"},
        velocity={"tx_count_1h": 12, "tx_volume_1h": 80000, "unique_receivers_24h": 8, "time_since_last_tx": 10},
        amount_mean=scorer.amount_mean,
    )
    score = scorer.score(feats)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_temporal_split():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(100):
        rows.append({
            "timestamp": base + timedelta(hours=i),
            "amount": float(i),
            "pattern_label": None,
        })
    df = pd.DataFrame(rows)
    train_df, test_df = temporal_split(df, test_ratio=0.2)
    assert len(train_df) == 80
    assert len(test_df) == 20
    assert train_df["timestamp"].max() <= test_df["timestamp"].min()
