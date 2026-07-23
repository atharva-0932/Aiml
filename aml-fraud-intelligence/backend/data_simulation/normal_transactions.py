"""
Normal (non-suspicious) transaction generation.
Log-normal amounts, random account pairs, no pattern_label.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

import numpy as np

from data_simulation.schema import make_transaction, random_timestamp


def make_normal_transaction(
    sender: dict[str, Any],
    receiver: dict[str, Any],
    ts: datetime | None = None,
) -> dict[str, Any]:
    """Generate one plausible clean transaction."""
    amount = round(float(np.random.lognormal(mean=6.2, sigma=1.2)), 2)
    amount = max(1.0, min(amount, 50_000.0))

    if ts is None:
        now = datetime.now(timezone.utc)
        ts = random_timestamp(now.replace(year=now.year - 1), now)

    return make_transaction(sender, receiver, amount, ts, pattern_label=None)


def generate_normal_batch(accounts: list[dict], n: int = 47_000) -> list[dict[str, Any]]:
    """Generate n clean transactions between random distinct accounts."""
    active = [a for a in accounts if not a.get("is_dormant")]
    pool = active if len(active) >= 2 else accounts
    txns: list[dict[str, Any]] = []
    for _ in range(n):
        sender, receiver = random.sample(pool, 2)
        txns.append(make_normal_transaction(sender, receiver))
    return txns
