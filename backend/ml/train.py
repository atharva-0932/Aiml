"""
XGBoost training entrypoint.

Run: PYTHONPATH=backend python3 -m ml.train --csv data/transactions.csv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from ml.features import FEATURE_COLUMNS, MODEL_DIR, extract_features_dataframe, save_feature_metadata


def temporal_split(df: pd.DataFrame, test_ratio: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sort by timestamp; train = first 80%, test = last 20%. Never shuffle."""
    ordered = df.sort_values("timestamp").reset_index(drop=True)
    cut = int(len(ordered) * (1.0 - test_ratio))
    return ordered.iloc[:cut].copy(), ordered.iloc[cut:].copy()


def build_labels(df: pd.DataFrame) -> np.ndarray:
    labels = df["pattern_label"]
    flagged = labels.notna() & (labels.astype(str).str.len() > 0) & (labels.astype(str).str.lower() != "nan")
    return flagged.astype(int).values


def train(csv_path: Path) -> dict:
    print(f"Loading {csv_path}...")
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["amount"] = df["amount"].astype(float)

    amount_mean = float(df["amount"].mean())
    save_feature_metadata(amount_mean, FEATURE_COLUMNS)
    print(f"amount_mean={amount_mean:.2f}")

    train_df, test_df = temporal_split(df)
    print(f"Temporal split: train={len(train_df):,}  test={len(test_df):,}")

    y_train = build_labels(train_df)
    y_test = build_labels(test_df)
    X_train = extract_features_dataframe(train_df, amount_mean=amount_mean).values
    X_test = extract_features_dataframe(test_df, amount_mean=amount_mean).values

    pos = int(y_train.sum())
    neg = int(len(y_train) - pos)
    scale_pos_weight = neg / max(pos, 1)
    print(f"Class balance train: pos={pos:,} neg={neg:,} scale_pos_weight={scale_pos_weight:.2f}")

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="auc",
        early_stopping_rounds=20,
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )
    print("Training XGBoost...")
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        verbose=50,
    )

    proba = model.predict_proba(X_test)[:, 1]
    preds = (proba >= 0.5).astype(int)

    auc = float(roc_auc_score(y_test, proba))
    precision = float(precision_score(y_test, preds, zero_division=0))
    recall = float(recall_score(y_test, preds, zero_division=0))
    f1 = float(f1_score(y_test, preds, zero_division=0))

    print("\nClassification Report:")
    print(classification_report(y_test, preds, target_names=["clean", "flagged"], zero_division=0))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, preds))
    print(f"AUC-ROC: {auc:.4f}")

    # Per-pattern recall on test flagged rows (where label known)
    test_labeled = test_df.copy()
    test_labeled["_pred"] = preds
    test_labeled["_y"] = y_test
    print("\nPer-pattern recall (flagged patterns in test set):")
    for pattern, group in test_labeled[test_labeled["_y"] == 1].groupby("pattern_label"):
        hit = int((group["_pred"] == 1).sum())
        total = len(group)
        print(f"  {pattern:20s} {hit}/{total} ({100 * hit / max(total, 1):.1f}%)")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "model.json"
    model.save_model(model_path)

    metrics = {
        "auc_roc": round(auc, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "train_size": int(len(train_df)),
        "test_size": int(len(test_df)),
        "positives_train": pos,
        "scale_pos_weight": round(scale_pos_weight, 4),
        "amount_mean": round(amount_mean, 4),
        "best_iteration": int(getattr(model, "best_iteration", model.n_estimators) or 0),
    }
    (MODEL_DIR / "training_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"\nSaved model → {model_path}")
    print(f"Metrics → {MODEL_DIR / 'training_metrics.json'}")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train AML XGBoost classifier")
    parser.add_argument("--csv", type=Path, required=True, help="Path to transactions.csv")
    args = parser.parse_args()
    train(args.csv)
