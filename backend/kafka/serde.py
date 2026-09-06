"""Shared transaction payload normalize/serialize helpers for Kafka."""
from __future__ import annotations

import json
from typing import Any


_NULLISH = {"", "nan", "none", "null", "na", "<na>"}


def normalize_pattern_label(value: Any) -> str | None:
    """Preserve real AML labels; map empty / nullish values to None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in _NULLISH:
        return None
    return text


def normalize_transaction(row: dict[str, Any]) -> dict[str, Any]:
    """Return a Kafka-safe transaction dict with typed fields."""
    tx = dict(row)
    tx["pattern_label"] = normalize_pattern_label(tx.get("pattern_label"))
    if tx.get("amount") is not None and tx.get("amount") != "":
        tx["amount"] = float(tx["amount"])
    return tx


def serialize_transaction(row: dict[str, Any]) -> bytes:
    """JSON-encode a transaction. pattern_label is a string or JSON null."""
    tx = normalize_transaction(row)
    return json.dumps(tx, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def deserialize_transaction(payload: bytes | str) -> dict[str, Any]:
    """Decode Kafka message value and normalize pattern_label."""
    raw = payload.decode("utf-8") if isinstance(payload, (bytes, bytearray)) else payload
    tx = json.loads(raw)
    return normalize_transaction(tx)
