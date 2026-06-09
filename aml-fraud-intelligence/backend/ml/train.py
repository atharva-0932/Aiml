"""
Model training entrypoint.
Run: python -m ml.train

Fetches feature-engineered data from Snowpark (or local CSV fallback),
trains Isolation Forest + XGBoost, evaluates, saves artifacts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, roc_auc_score, average_precision_score,
    confusion_matrix,
)

from ml.feature_engineering import FEATURE_COLUMNS, enrich_dataframe
from ml.anomaly_detection import AnomalyDetector
from ml.risk_classifier import FraudClassifier
from core.logging import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)

MODEL_DIR = Path(__file__).parent / "models"


def load_data(csv_path: str | None = None) -> pd.DataFrame:
    if csv_path:
        log.info("Loading data from CSV", path=csv_path)
        return pd.read_csv(csv_path)

    log.info("Fetching training data via Snowpark")
    from db.snowflake.snowpark import fetch_training_features
    return fetch_training_features()


def train(csv_path: str | None = None) -> None:
    df = load_data(csv_path)
    df = enrich_dataframe(df)

    log.info("Dataset loaded", shape=str(df.shape),
             fraud_count=int((df.get("aml_label", pd.Series()) != "").sum()))

    # Label encoding: any non-null aml_label = fraud
    y = (df["aml_label"].notna() & (df["aml_label"] != "")).astype(int).values
    X = df[FEATURE_COLUMNS].fillna(0).values

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    # ── Isolation Forest ──────────────────────────────────────────────────────
    log.info("Training Isolation Forest...")
    detector = AnomalyDetector(contamination=max(0.005, y.mean()))
    detector.fit(X_train)
    iso_scores_val = detector.score(X_val)
    log.info("Isolation Forest trained", val_mean_score=float(iso_scores_val.mean()))

    # ── XGBoost Classifier ────────────────────────────────────────────────────
    log.info("Training XGBoost classifier...")
    classifier = FraudClassifier()
    classifier.fit(X_train, y_train, X_val, y_val)
    proba = classifier.predict_proba(X_val)
    preds = (proba >= 0.5).astype(int)

    roc = roc_auc_score(y_val, proba)
    pr_auc = average_precision_score(y_val, proba)
    log.info("XGBoost evaluation",
             roc_auc=round(roc, 4),
             pr_auc=round(pr_auc, 4))
    print("\nClassification Report:\n", classification_report(y_val, preds,
          target_names=["Normal", "Fraud"]))
    print("Confusion Matrix:\n", confusion_matrix(y_val, preds))

    # ── Save ──────────────────────────────────────────────────────────────────
    import joblib
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(detector, MODEL_DIR / "isolation_forest.joblib")
    joblib.dump(classifier, MODEL_DIR / "xgboost_classifier.joblib")

    metrics = {"roc_auc": round(roc, 4), "pr_auc": round(pr_auc, 4),
               "fraud_rate": round(float(y.mean()), 4)}
    (MODEL_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))

    log.info("Training complete", metrics=metrics, output_dir=str(MODEL_DIR))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train AML fraud detection models")
    parser.add_argument("--csv", type=str, default=None,
                        help="Path to CSV training data (skips Snowpark)")
    args = parser.parse_args()
    train(csv_path=args.csv)
