"""Unit tests for risk scorer heuristic fallback (no trained models required)."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from ml.risk_scorer import CompositeRiskScorer


def _tx(**overrides):
    tx = {
        "id": "tx-test",
        "sender_account_id": "acct-test",
        "amount": 5000.0,
        "timestamp": "2025-06-01T10:00:00",
        "tx_count_1h": 2,
        "tx_count_24h": 5,
        "avg_amount_7d": 4500.0,
        "dormant_flag": 0,
        "device_switch_flag": 0,
        "graph_in_degree": 1,
        "graph_out_degree": 1,
        "pagerank_score": 0.01,
        "cycle_membership": 0,
        "hop_depth": 1,
    }
    tx.update(overrides)
    return tx


def test_scorer_returns_valid_score():
    scorer = CompositeRiskScorer()
    result = scorer.score(_tx())
    assert "composite_score" in result
    assert 0 <= result["composite_score"] <= 100
    assert result["risk_tier"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def test_structuring_triggers_rule():
    scorer = CompositeRiskScorer()
    result = scorer.score(_tx(amount=9_800.0))
    assert "structuring_pattern" in result["triggered_rules"]


def test_velocity_breach_triggers_rule():
    scorer = CompositeRiskScorer()
    result = scorer.score(_tx(tx_count_1h=15))
    assert "velocity_1h_breach" in result["triggered_rules"]


def test_dormant_triggers_rule():
    scorer = CompositeRiskScorer()
    result = scorer.score(_tx(dormant_flag=1))
    assert "dormant_activation" in result["triggered_rules"]


def test_cycle_triggers_rule():
    scorer = CompositeRiskScorer()
    result = scorer.score(_tx(cycle_membership=1))
    assert "circular_flow" in result["triggered_rules"]
