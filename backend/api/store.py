"""In-memory transaction CSV store loaded at API startup."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from kafka.serde import normalize_pattern_label
from ml.scorer import classify_tier

CSV_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "transactions.csv"


class TransactionStore:
    def __init__(self) -> None:
        self._by_id: dict[str, dict[str, Any]] = {}
        self._rows: list[dict[str, Any]] = []

    def load(self, path: Path | None = None) -> int:
        csv_path = path or CSV_PATH
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")
        df = pd.read_csv(csv_path)
        rows: list[dict[str, Any]] = []
        by_id: dict[str, dict[str, Any]] = {}
        for record in df.to_dict(orient="records"):
            tx = {
                "transaction_id": str(record["transaction_id"]),
                "timestamp": str(record["timestamp"]),
                "sender_account": str(record["sender_account"]),
                "receiver_account": str(record["receiver_account"]),
                "amount": float(record["amount"]),
                "bank": str(record.get("bank") or ""),
                "pattern_label": normalize_pattern_label(record.get("pattern_label")),
            }
            rows.append(tx)
            by_id[tx["transaction_id"]] = tx
        self._rows = rows
        self._by_id = by_id
        return len(rows)

    def get(self, transaction_id: str) -> dict[str, Any] | None:
        return self._by_id.get(transaction_id)

    def all(self) -> list[dict[str, Any]]:
        return self._rows

    def enrich(self, tx: dict[str, Any], score: float | None) -> dict[str, Any]:
        out = dict(tx)
        if score is None:
            out["composite_score"] = None
            out["tier"] = None
        else:
            out["composite_score"] = float(score)
            out["tier"] = classify_tier(float(score))
        return out


store = TransactionStore()
