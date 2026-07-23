"""
XGBoostScorer + CompositeRiskScorer + SHAP explanations.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, OrderedDict

import numpy as np
import xgboost as xgb

from ml.features import FEATURE_COLUMNS, MODEL_DIR, features_to_list, load_amount_mean

MODEL_PATH = MODEL_DIR / "model.json"
FEATURE_COLUMNS_PATH = MODEL_DIR / "feature_columns.json"


def classify_tier(score: float) -> str:
    if score > 90:
        return "CRITICAL"
    if score > 70:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"


class XGBoostScorer:
    def __init__(self, model_dir: Path | None = None):
        root = model_dir or MODEL_DIR
        model_path = root / "model.json"
        cols_path = root / "feature_columns.json"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Missing {model_path}. Run: PYTHONPATH=backend python3 -m ml.train --csv data/transactions.csv"
            )

        self.booster = xgb.Booster()
        self.booster.load_model(str(model_path))

        if cols_path.exists():
            meta = json.loads(cols_path.read_text())
            self.columns = meta["columns"] if isinstance(meta, dict) else list(meta)
            self.amount_mean = float(meta.get("amount_mean", load_amount_mean())) if isinstance(meta, dict) else load_amount_mean()
        else:
            self.columns = list(FEATURE_COLUMNS)
            self.amount_mean = load_amount_mean()

        self._explainer = None

    def score(self, features: OrderedDict[str, float] | dict[str, float]) -> float:
        """Return XGBoost fraud probability scaled to 0–100."""
        row = [float(features[c]) for c in self.columns]
        dmat = xgb.DMatrix(np.array([row], dtype=np.float32), feature_names=self.columns)
        proba = float(self.booster.predict(dmat)[0])
        return round(min(max(proba * 100.0, 0.0), 100.0), 2)

    def _get_explainer(self):
        if self._explainer is None:
            import shap

            self._explainer = shap.TreeExplainer(self.booster)
        return self._explainer

    def shap_top_features(
        self, features: OrderedDict[str, float] | dict[str, float], top_k: int = 5
    ) -> list[tuple[str, float]]:
        """Return top-k (feature_name, shap_value) by absolute contribution."""
        try:
            row = np.array([[float(features[c]) for c in self.columns]], dtype=np.float32)
            explainer = self._get_explainer()
            values = explainer.shap_values(row)
            if isinstance(values, list):
                values = values[1] if len(values) > 1 else values[0]
            flat = np.array(values).reshape(-1)
            pairs = list(zip(self.columns, [float(v) for v in flat]))
            pairs.sort(key=lambda x: abs(x[1]), reverse=True)
            return pairs[:top_k]
        except Exception as exc:
            print(f"SHAP explanation failed: {exc}")
            return []


class CompositeRiskScorer:
    """Composite = 0.60 × XGBoost + 0.40 × Graph Risk."""

    WEIGHT_XGB = 0.60
    WEIGHT_GRAPH = 0.40

    def composite(self, xgb_score: float, graph_risk: float) -> dict[str, Any]:
        composite_score = round(
            min(self.WEIGHT_XGB * float(xgb_score) + self.WEIGHT_GRAPH * float(graph_risk), 100.0),
            2,
        )
        return {
            "composite_score": composite_score,
            "tier": classify_tier(composite_score),
            "xgb_score": round(float(xgb_score), 2),
            "graph_risk": round(float(graph_risk), 2),
        }
