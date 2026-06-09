"""
AML pattern simulation.
Each function generates a cluster of transactions implementing a specific
money laundering typology as understood by FATF and FinCEN guidance.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from data_simulation.schema import new_id, CHANNELS, CURRENCIES


def _ts(base: datetime, offset_minutes: int) -> str:
    return (base + timedelta(minutes=offset_minutes)).isoformat()


# ── 1. Structuring (smurfing) ──────────────────────────────────────────────────

def generate_structuring(
    sender: dict,
    receivers: list[dict],
    base_time: datetime | None = None,
    n_transactions: int = 8,
) -> list[dict]:
    """
    Multiple transactions just below the $10,000 CTR threshold
    from the same sender within 24–48 hours.
    """
    base = base_time or datetime.now(timezone.utc)
    txns = []
    for i in range(n_transactions):
        amount = round(random.uniform(8_500, 9_999), 2)
        receiver = random.choice(receivers)
        txns.append({
            "id": new_id(),
            "sender_account_id": sender["id"],
            "receiver_account_id": receiver["id"],
            "amount": amount,
            "currency": "USD",
            "transaction_type": "cash_deposit",
            "channel": random.choice(["branch", "ATM"]),
            "device_id": None,
            "merchant_id": None,
            "ip_address": None,
            "geo_lat": round(random.uniform(30, 45), 5),
            "geo_lon": round(random.uniform(-100, -70), 5),
            "timestamp": _ts(base, random.randint(0, 2880)),
            "is_flagged": True,
            "aml_label": "structuring",
            "bank_code": sender.get("bank_code", ""),
            "country": "US",
            "dormant_flag": 0,
            "device_switch_flag": 0,
            "pagerank_score": 0.1,
            "graph_in_degree": 1,
            "graph_out_degree": n_transactions,
            "cycle_membership": 0,
            "hop_depth": 1,
        })
    return txns


# ── 2. Layering ────────────────────────────────────────────────────────────────

def generate_layering(
    accounts: list[dict],
    base_time: datetime | None = None,
    n_hops: int = 6,
) -> list[dict]:
    """
    Chain A→B→C→D→E→F over 3–7 hops. Amounts reduce by ~15% per hop
    to simulate fee extraction and obfuscation.
    """
    base = base_time or datetime.now(timezone.utc)
    chain = random.sample(accounts, min(n_hops + 1, len(accounts)))
    txns = []
    amount = round(random.uniform(50_000, 500_000), 2)

    for i in range(len(chain) - 1):
        amount = round(amount * random.uniform(0.83, 0.94), 2)
        txns.append({
            "id": new_id(),
            "sender_account_id": chain[i]["id"],
            "receiver_account_id": chain[i + 1]["id"],
            "amount": amount,
            "currency": random.choice(CURRENCIES),
            "transaction_type": random.choice(["wire", "SWIFT"]),
            "channel": "online",
            "device_id": None,
            "merchant_id": None,
            "ip_address": None,
            "geo_lat": round(random.uniform(-70, 70), 5),
            "geo_lon": round(random.uniform(-170, 170), 5),
            "timestamp": _ts(base, i * random.randint(60, 360)),
            "is_flagged": True,
            "aml_label": "layering",
            "bank_code": chain[i].get("bank_code", "ANON"),
            "country": chain[i].get("country", "US"),
            "dormant_flag": 0,
            "device_switch_flag": 0,
            "pagerank_score": 0.05 * (i + 1),
            "graph_in_degree": i,
            "graph_out_degree": 1,
            "cycle_membership": 0,
            "hop_depth": i + 1,
        })
    return txns


# ── 3. Circular fund transfer ──────────────────────────────────────────────────

def generate_circular(
    accounts: list[dict],
    base_time: datetime | None = None,
) -> list[dict]:
    """A→B→C→A within 72 hours. Classic integration typology."""
    base = base_time or datetime.now(timezone.utc)
    ring = random.sample(accounts, min(4, len(accounts)))
    ring.append(ring[0])  # close the cycle
    amount = round(random.uniform(10_000, 200_000), 2)
    txns = []

    for i in range(len(ring) - 1):
        txns.append({
            "id": new_id(),
            "sender_account_id": ring[i]["id"],
            "receiver_account_id": ring[i + 1]["id"],
            "amount": round(amount * random.uniform(0.97, 1.03), 2),
            "currency": "USD",
            "transaction_type": "wire",
            "channel": "online",
            "device_id": None,
            "merchant_id": None,
            "ip_address": None,
            "geo_lat": round(random.uniform(-70, 70), 5),
            "geo_lon": round(random.uniform(-170, 170), 5),
            "timestamp": _ts(base, i * random.randint(120, 720)),
            "is_flagged": True,
            "aml_label": "circular_flow",
            "bank_code": ring[i].get("bank_code", ""),
            "country": ring[i].get("country", "US"),
            "dormant_flag": 0,
            "device_switch_flag": 0,
            "pagerank_score": 0.3,
            "graph_in_degree": 1,
            "graph_out_degree": 1,
            "cycle_membership": 1,
            "hop_depth": i + 1,
        })
    return txns


# ── 4. Mule account ────────────────────────────────────────────────────────────

def generate_mule(
    mule_account: dict,
    senders: list[dict],
    final_destination: dict,
    base_time: datetime | None = None,
) -> list[dict]:
    """
    Mule receives many small deposits, then forwards 90%+ to single destination.
    """
    base = base_time or datetime.now(timezone.utc)
    txns = []
    total_in = 0.0

    for i, sender in enumerate(senders[:12]):
        amount = round(random.uniform(1_000, 8_000), 2)
        total_in += amount
        txns.append({
            "id": new_id(),
            "sender_account_id": sender["id"],
            "receiver_account_id": mule_account["id"],
            "amount": amount,
            "currency": "USD",
            "transaction_type": "ACH",
            "channel": "mobile",
            "device_id": None,
            "merchant_id": None,
            "ip_address": None,
            "geo_lat": round(random.uniform(30, 45), 5),
            "geo_lon": round(random.uniform(-100, -70), 5),
            "timestamp": _ts(base, i * 60),
            "is_flagged": True,
            "aml_label": "mule",
            "bank_code": mule_account.get("bank_code", ""),
            "country": "US",
            "dormant_flag": 0,
            "device_switch_flag": 0,
            "pagerank_score": 0.5,
            "graph_in_degree": i + 1,
            "graph_out_degree": 1,
            "cycle_membership": 0,
            "hop_depth": 1,
        })

    # Consolidation transfer — 92% of total collected
    txns.append({
        "id": new_id(),
        "sender_account_id": mule_account["id"],
        "receiver_account_id": final_destination["id"],
        "amount": round(total_in * 0.92, 2),
        "currency": "USD",
        "transaction_type": "wire",
        "channel": "online",
        "device_id": None,
        "merchant_id": None,
        "ip_address": None,
        "geo_lat": round(random.uniform(-70, 70), 5),
        "geo_lon": round(random.uniform(-170, 170), 5),
        "timestamp": _ts(base, len(senders) * 60 + 30),
        "is_flagged": True,
        "aml_label": "mule",
        "bank_code": mule_account.get("bank_code", ""),
        "country": "US",
        "dormant_flag": 0,
        "device_switch_flag": 0,
        "pagerank_score": 0.6,
        "graph_in_degree": len(senders),
        "graph_out_degree": 1,
        "cycle_membership": 0,
        "hop_depth": 2,
    })
    return txns


# ── 5. Dormant activation ──────────────────────────────────────────────────────

def generate_dormant_activation(
    dormant_account: dict,
    receivers: list[dict],
    base_time: datetime | None = None,
) -> list[dict]:
    """Account silent >180 days, then sudden high-value activity."""
    base = base_time or datetime.now(timezone.utc)
    txns = []
    for i, receiver in enumerate(receivers[:5]):
        txns.append({
            "id": new_id(),
            "sender_account_id": dormant_account["id"],
            "receiver_account_id": receiver["id"],
            "amount": round(random.uniform(20_000, 150_000), 2),
            "currency": random.choice(CURRENCIES),
            "transaction_type": "wire",
            "channel": "online",
            "device_id": None,
            "merchant_id": None,
            "ip_address": None,
            "geo_lat": round(random.uniform(-70, 70), 5),
            "geo_lon": round(random.uniform(-170, 170), 5),
            "timestamp": _ts(base, i * 30),
            "is_flagged": True,
            "aml_label": "dormant_activation",
            "bank_code": dormant_account.get("bank_code", ""),
            "country": dormant_account.get("country", "US"),
            "dormant_flag": 1,
            "device_switch_flag": 1,
            "pagerank_score": 0.15,
            "graph_in_degree": 0,
            "graph_out_degree": i + 1,
            "cycle_membership": 0,
            "hop_depth": 1,
        })
    return txns


# ── 6. Rapid multi-hop ─────────────────────────────────────────────────────────

def generate_rapid_multihop(
    accounts: list[dict],
    base_time: datetime | None = None,
) -> list[dict]:
    """5+ transfers across 5+ accounts within 2 hours."""
    base = base_time or datetime.now(timezone.utc)
    chain = random.sample(accounts, min(7, len(accounts)))
    amount = round(random.uniform(5_000, 100_000), 2)
    txns = []

    for i in range(len(chain) - 1):
        txns.append({
            "id": new_id(),
            "sender_account_id": chain[i]["id"],
            "receiver_account_id": chain[i + 1]["id"],
            "amount": round(amount * random.uniform(0.95, 1.02), 2),
            "currency": "USD",
            "transaction_type": "wire",
            "channel": "API",
            "device_id": None,
            "merchant_id": None,
            "ip_address": None,
            "geo_lat": round(random.uniform(-70, 70), 5),
            "geo_lon": round(random.uniform(-170, 170), 5),
            "timestamp": _ts(base, i * random.randint(5, 20)),
            "is_flagged": True,
            "aml_label": "rapid_multihop",
            "bank_code": chain[i].get("bank_code", ""),
            "country": chain[i].get("country", "US"),
            "dormant_flag": 0,
            "device_switch_flag": 0,
            "pagerank_score": 0.2,
            "graph_in_degree": i,
            "graph_out_degree": 1,
            "cycle_membership": 0,
            "hop_depth": i + 1,
        })
    return txns
