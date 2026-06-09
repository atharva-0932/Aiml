"""
Normal (non-suspicious) transaction generation.
Simulates realistic banking behaviour with temporal clustering,
merchant variability, and plausible amount distributions.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

import numpy as np

from data_simulation.schema import (
    new_id, random_timestamp, TRANSACTION_TYPES, CHANNELS, CURRENCIES
)


def make_normal_transaction(
    sender_account: dict,
    receiver_account: dict,
    device: dict | None = None,
    ts: datetime | None = None,
) -> dict[str, Any]:
    """Generate a single plausible normal transaction."""
    # Amount: log-normal distribution centred around $500, tail up to ~$50k
    amount = round(float(np.random.lognormal(mean=6.2, sigma=1.2)), 2)
    amount = max(1.0, min(amount, 50_000.0))

    if ts is None:
        now = datetime.now(timezone.utc)
        ts = random_timestamp(
            now.replace(year=now.year - 1),
            now,
        )

    return {
        "id": new_id(),
        "sender_account_id": sender_account["id"],
        "receiver_account_id": receiver_account["id"],
        "amount": amount,
        "currency": random.choice(CURRENCIES),
        "transaction_type": random.choices(
            TRANSACTION_TYPES, weights=[20, 30, 10, 30, 5, 5]
        )[0],
        "channel": random.choices(CHANNELS, weights=[40, 10, 10, 35, 5])[0],
        "device_id": device["id"] if device else None,
        "merchant_id": None,
        "ip_address": None,
        "geo_lat": sender_account.get("geo_lat", round(random.uniform(-70, 70), 5)),
        "geo_lon": sender_account.get("geo_lon", round(random.uniform(-170, 170), 5)),
        "timestamp": ts.isoformat(),
        "is_flagged": False,
        "aml_label": None,
        "bank_code": sender_account.get("bank_code", ""),
        "country": sender_account.get("country", "US"),
        "dormant_flag": 0,
        "device_switch_flag": 0,
        "pagerank_score": 0.0,
        "graph_in_degree": 0,
        "graph_out_degree": 0,
        "cycle_membership": 0,
        "hop_depth": 0,
    }


def generate_normal_batch(
    accounts: list[dict],
    n: int = 40_000,
) -> list[dict[str, Any]]:
    txns = []
    for _ in range(n):
        sender, receiver = random.sample(accounts, 2)
        txns.append(make_normal_transaction(sender, receiver))
    return txns
