"""
XGBoost binary fraud classifier.
scale_pos_weight handles severe class imbalance (fraud ~1-2% of transactions).
SHAP integration provides per-prediction feature importance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from ml.feature_engineering import FEATURE_COLUMNS


class FraudClassifier:
    def __init__(self):
        self.model = None
        self.label_encoder = LabelEncoder()
        self._fitted = False

    def _build_model(self, scale_pos_weight: float = 50.0):
        import xgboost as xgb
        return xgb.XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,  # critical for imbalanced AML data
            use_label_encoder=False,
            eval_metric="aucpr",                # PR-AUC better than ROC-AUC for imbalanced
            early_stopping_rounds=30,
            random_state=42,
            n_jobs=-1,
            tree_method="hist",
        )

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
    ) -> "FraudClassifier":
        fraud_count = y_train.sum()
        normal_count = len(y_train) - fraud_count
        scale_pos_weight = normal_count / max(fraud_count, 1)

        self.model = self._build_model(scale_pos_weight=scale_pos_weight)
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=50,
        )
        self._fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Returns fraud probability for each sample."""
        if not self._fitted:
            raise RuntimeError("FraudClassifier must be fitted before scoring")
        X2d = X.reshape(1, -1) if X.ndim == 1 else X
        return self.model.predict_proba(X2d)[:, 1]

    def explain(self, X: np.ndarray) -> dict[str, float]:
        """Returns SHAP feature contributions for a single sample."""
        try:
            import shap
            if not hasattr(self, "_explainer") or self._explainer is None:
                self._explainer = shap.TreeExplainer(self.model)
            X2d = X.reshape(1, -1) if X.ndim == 1 else X
            shap_vals = self._explainer.shap_values(X2d)
            vals = shap_vals[0] if isinstance(shap_vals, list) else shap_vals[0]
            return dict(zip(FEATURE_COLUMNS, [round(float(v), 4) for v in vals]))
        except Exception:
            return {}
