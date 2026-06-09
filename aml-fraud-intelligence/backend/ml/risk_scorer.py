"""
CompositeRiskScorer — combines Isolation Forest, XGBoost, and graph metrics
into a single 0–100 risk score.

Composite = 0.40 × XGBoost + 0.35 × IsolationForest + 0.25 × GraphRisk
"""
from __future__ import annotations

import os
import joblib
from pathlib import Path
from typing import Any

import numpy as np

from ml.feature_engineering import extract_features, features_to_array, FEATURE_COLUMNS
from ml.anomaly_detection import AnomalyDetector
from ml.risk_classifier import FraudClassifier
from kafka.topics import classify_risk_tier
from core.logging import get_logger

log = get_logger(__name__)

MODEL_DIR = Path(__file__).parent / "models"

WEIGHT_XGB = 0.40
WEIGHT_ISO = 0.35
WEIGHT_GRAPH = 0.25


def _detect_rules(tx: dict, features: dict) -> list[str]:
    rules = []
    if features["tx_count_1h"] > 10:
        rules.append("velocity_1h_breach")
    if features["tx_count_24h"] > 30:
        rules.append("velocity_24h_breach")
    if features["dormant_flag"]:
        rules.append("dormant_activation")
    if features["is_near_threshold"]:
        rules.append("structuring_pattern")
    if features["cycle_membership"]:
        rules.append("circular_flow")
    if features["geo_distance_km"] > 1000:
        rules.append("geo_anomaly")
    if features["device_switch_flag"]:
        rules.append("device_switch")
    if features["hop_depth"] >= 4:
        rules.append("deep_layering")
    if features["graph_in_degree"] > 8 and features["graph_out_degree"] <= 3:
        rules.append("mule_pattern")
    return rules


class CompositeRiskScorer:
    def __init__(self):
        self.detector = AnomalyDetector()
        self.classifier = FraudClassifier()
        self._loaded = False
        self._load_models()

    def _load_models(self) -> None:
        iso_path = MODEL_DIR / "isolation_forest.joblib"
        xgb_path = MODEL_DIR / "xgboost_classifier.joblib"

        if iso_path.exists() and xgb_path.exists():
            try:
                self.detector = joblib.load(iso_path)
                self.classifier = joblib.load(xgb_path)
                self._loaded = True
                log.info("ML models loaded from disk")
            except Exception as exc:
                log.warning("Model load failed — using heuristic fallback", error=str(exc))
        else:
            log.warning("No trained models found — using heuristic scoring")

    def score(self, tx: dict[str, Any]) -> dict[str, Any]:
        """
        Score a transaction dict and return a full risk profile.
        Falls back to rule-based heuristics if models are not trained yet.
        """
        features = extract_features(tx)
        feat_array = features_to_array(features)

        if self._loaded:
            iso_score = float(self.detector.score(feat_array)[0])
            xgb_score = float(self.classifier.predict_proba(feat_array)[0])
            shap_vals = self.classifier.explain(feat_array)
        else:
            # Heuristic fallback for development (before model training)
            iso_score = min(1.0, features["amount_zscore"] / 10) if features["amount_zscore"] > 0 else 0.1
            xgb_score = min(1.0, (features["tx_count_1h"] / 20) + (features["is_near_threshold"] * 0.4))
            shap_vals = {}

        # Graph risk: normalise pagerank + cycle membership + hop depth
        graph_raw = (
            min(features["pagerank_score"], 1.0) * 0.4
            + features["cycle_membership"] * 0.4
            + min(features["hop_depth"] / 8.0, 1.0) * 0.2
        )
        graph_risk = float(graph_raw)

        composite = (WEIGHT_XGB * xgb_score + WEIGHT_ISO * iso_score + WEIGHT_GRAPH * graph_risk) * 100
        composite = round(min(composite, 100.0), 2)

        triggered_rules = _detect_rules(tx, features)
        risk_tier = classify_risk_tier(composite)

        return {
            "composite_score": composite,
            "anomaly_score": round(iso_score, 4),
            "classifier_score": round(xgb_score, 4),
            "graph_risk_score": round(graph_risk, 4),
            "risk_tier": risk_tier,
            "triggered_rules": triggered_rules,
            "shap_values": shap_vals,
            "features": features,
        }

    def save(self) -> None:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.detector, MODEL_DIR / "isolation_forest.joblib")
        joblib.dump(self.classifier, MODEL_DIR / "xgboost_classifier.joblib")
        log.info("Models saved", path=str(MODEL_DIR))
