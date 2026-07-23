"""
Entity generation for synthetic AML datasets.
Produces accounts and shared constants used by normal + pattern generators.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

BANK_CODES = ["BOFA", "JPMC", "CITI", "HSBC", "BARC", "DEUT", "SGBK", "ANON"]
COUNTRIES = ["US", "GB", "DE", "SG", "AE", "NG", "CN", "RU", "MX", "BR"]

PATTERN_LABELS = (
    "structuring",
    "layering",
    "circular_flow",
    "mule",
    "dormant_activation",
    "rapid_multihop",
)

TX_COLUMNS = [
    "transaction_id",
    "timestamp",
    "sender_account",
    "receiver_account",
    "amount",
    "bank",
    "pattern_label",
]


def new_id() -> str:
    return str(uuid.uuid4())


def random_timestamp(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, max(int(delta.total_seconds()), 0)))


def make_account(is_dormant: bool = False) -> dict[str, Any]:
    """Create a synthetic account used as sender/receiver in transactions."""
    created = fake.date_time_between(start_date="-5y", end_date="-6m", tzinfo=timezone.utc)
    dormant_since = None
    if is_dormant:
        dormant_since = fake.date_time_between(
            start_date=created, end_date="-7m", tzinfo=timezone.utc
        )
    return {
        "id": new_id(),
        "bank": random.choice(BANK_CODES),
        "country": random.choice(COUNTRIES),
        "created_at": created,
        "is_dormant": is_dormant,
        "dormant_since": dormant_since,
    }


def make_transaction(
    sender: dict[str, Any],
    receiver: dict[str, Any],
    amount: float,
    timestamp: datetime,
    pattern_label: str | None = None,
) -> dict[str, Any]:
    """Build a single transaction row matching the Phase 1 CSV schema."""
    return {
        "transaction_id": new_id(),
        "timestamp": timestamp.isoformat(),
        "sender_account": sender["id"],
        "receiver_account": receiver["id"],
        "amount": round(float(amount), 2),
        "bank": sender["bank"],
        "pattern_label": pattern_label,
    }
