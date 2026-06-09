"""
Isolation Forest anomaly detection pipeline.
Returns a normalised anomaly score in [0, 1] where higher = more anomalous.
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler

from ml.feature_engineering import FEATURE_COLUMNS


class AnomalyDetector:
    def __init__(self, contamination: float = 0.02):
        self.contamination = contamination
        self.model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            max_features=0.8,
            bootstrap=True,
            random_state=42,
            n_jobs=-1,
        )
        self.scaler = MinMaxScaler()
        self._fitted = False

    def fit(self, X: np.ndarray) -> "AnomalyDetector":
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self._fitted = True
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """
        Returns anomaly scores in [0, 1].
        Isolation Forest decision_function returns negative scores for anomalies.
        We flip and normalise so that 1.0 = most anomalous.
        """
        if not self._fitted:
            raise RuntimeError("AnomalyDetector must be fitted before scoring")
        X_scaled = self.scaler.transform(X.reshape(1, -1) if X.ndim == 1 else X)
        raw_scores = self.model.decision_function(X_scaled)
        # Invert: more negative = more anomalous → map to [0,1]
        inverted = -raw_scores
        min_s, max_s = inverted.min(), inverted.max()
        if max_s == min_s:
            return np.zeros_like(inverted)
        return (inverted - min_s) / (max_s - min_s)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Returns -1 for anomalies, 1 for normal."""
        X_scaled = self.scaler.transform(X.reshape(1, -1) if X.ndim == 1 else X)
        return self.model.predict(X_scaled)
