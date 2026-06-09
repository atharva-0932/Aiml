"""Unit tests for feature engineering pipeline."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from ml.feature_engineering import extract_features, features_to_array, FEATURE_COLUMNS


def _sample_tx(**overrides):
    tx = {
        "id": "tx-001",
        "sender_account_id": "acct-001",
        "receiver_account_id": "acct-002",
        "amount": 5000.0,
        "timestamp": "2025-01-15T14:30:00",
        "tx_count_1h": 3,
        "tx_count_24h": 8,
        "avg_amount_7d": 4500.0,
        "stddev_amount_7d": 1200.0,
        "dormant_flag": 0,
        "device_switch_flag": 0,
        "graph_in_degree": 2,
        "graph_out_degree": 3,
        "pagerank_score": 0.05,
        "cycle_membership": 0,
        "hop_depth": 1,
    }
    tx.update(overrides)
    return tx


def test_extract_features_returns_all_columns():
    tx = _sample_tx()
    features = extract_features(tx)
    for col in FEATURE_COLUMNS:
        assert col in features, f"Missing feature: {col}"


def test_structuring_flag():
    tx = _sample_tx(amount=9_500.0)
    features = extract_features(tx)
    assert features["is_near_threshold"] == 1.0


def test_high_value_flag():
    tx = _sample_tx(amount=100_000.0)
    features = extract_features(tx)
    assert features["is_high_value"] == 1.0


def test_features_to_array_shape():
    tx = _sample_tx()
    features = extract_features(tx)
    arr = features_to_array(features)
    assert arr.shape == (len(FEATURE_COLUMNS),)
    assert arr.dtype.name == "float32"


def test_dormant_flag_propagated():
    tx = _sample_tx(dormant_flag=1)
    features = extract_features(tx)
    assert features["dormant_flag"] == 1.0
