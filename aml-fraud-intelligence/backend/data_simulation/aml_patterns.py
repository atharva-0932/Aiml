"""
AML pattern generators with ground-truth pattern_label values.

Each function returns a cluster of transactions implementing one typology
(FATF / FinCEN style). Labels match the Phase 1 CSV schema.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from data_simulation.schema import make_transaction


def _offset(base: datetime, minutes: int) -> datetime:
    return base + timedelta(minutes=minutes)


# ── 1. Structuring ────────────────────────────────────────────────────────────

def generate_structuring(
    sender: dict[str, Any],
    receivers: list[dict[str, Any]],
    base_time: datetime | None = None,
    n_transactions: int = 8,
) -> list[dict[str, Any]]:
    """Multiple payments just below the $10,000 CTR threshold within 24–48h."""
    base = base_time or datetime.now(timezone.utc)
    txns: list[dict[str, Any]] = []
    for _ in range(n_transactions):
        amount = round(random.uniform(8_500, 9_999), 2)
        receiver = random.choice(receivers)
        ts = _offset(base, random.randint(0, 2_880))
        txns.append(make_transaction(sender, receiver, amount, ts, "structuring"))
    return txns


# ── 2. Layering ───────────────────────────────────────────────────────────────

def generate_layering(
    accounts: list[dict[str, Any]],
    base_time: datetime | None = None,
    n_hops: int = 6,
) -> list[dict[str, Any]]:
    """4–8 hop chain; amounts decay ~15%/hop; prefer cross-bank hops."""
    base = base_time or datetime.now(timezone.utc)
    n_hops = max(4, min(n_hops, 8))
    chain = random.sample(accounts, min(n_hops + 1, len(accounts)))

    # Prefer distinct banks along the chain when possible
    banks = {a["bank"] for a in chain}
    if len(banks) < 2 and len(accounts) >= n_hops + 1:
        by_bank: dict[str, list] = {}
        for a in accounts:
            by_bank.setdefault(a["bank"], []).append(a)
        if len(by_bank) >= 2:
            picks: list[dict] = []
            bank_cycle = list(by_bank.keys())
            for i in range(n_hops + 1):
                pool = by_bank[bank_cycle[i % len(bank_cycle)]]
                picks.append(random.choice(pool))
            chain = picks

    txns: list[dict[str, Any]] = []
    amount = round(random.uniform(50_000, 500_000), 2)
    for i in range(len(chain) - 1):
        amount = round(amount * random.uniform(0.83, 0.94), 2)
        ts = _offset(base, i * random.randint(60, 360))
        txns.append(make_transaction(chain[i], chain[i + 1], amount, ts, "layering"))
    return txns


# ── 3. Circular fund flow ─────────────────────────────────────────────────────

def generate_circular(
    accounts: list[dict[str, Any]],
    base_time: datetime | None = None,
) -> list[dict[str, Any]]:
    """A → B → C → A within 72 hours."""
    base = base_time or datetime.now(timezone.utc)
    ring = random.sample(accounts, min(3, len(accounts)))
    if len(ring) < 3:
        return []
    ring = ring + [ring[0]]
    amount = round(random.uniform(10_000, 200_000), 2)
    txns: list[dict[str, Any]] = []
    # Spread hops across < 72h (4320 minutes)
    for i in range(len(ring) - 1):
        hop_amount = round(amount * random.uniform(0.97, 1.03), 2)
        ts = _offset(base, i * random.randint(120, 1_200))
        txns.append(make_transaction(ring[i], ring[i + 1], hop_amount, ts, "circular_flow"))
    return txns


# ── 4. Mule accounts ──────────────────────────────────────────────────────────

def generate_mule(
    mule_account: dict[str, Any],
    senders: list[dict[str, Any]],
    final_destination: dict[str, Any],
    base_time: datetime | None = None,
) -> list[dict[str, Any]]:
    """Fan-in from 10+ sources, then ~92% forwarded to one destination."""
    base = base_time or datetime.now(timezone.utc)
    sources = senders[:12] if len(senders) >= 10 else senders
    if len(sources) < 10:
        return []

    txns: list[dict[str, Any]] = []
    total_in = 0.0
    for i, sender in enumerate(sources):
        amount = round(random.uniform(1_000, 8_000), 2)
        total_in += amount
        ts = _offset(base, i * 60)
        txns.append(make_transaction(sender, mule_account, amount, ts, "mule"))

    out_amount = round(total_in * 0.92, 2)
    ts_out = _offset(base, len(sources) * 60 + 30)
    txns.append(make_transaction(mule_account, final_destination, out_amount, ts_out, "mule"))
    return txns


# ── 5. Dormant activation ─────────────────────────────────────────────────────

def generate_dormant_activation(
    dormant_account: dict[str, Any],
    receivers: list[dict[str, Any]],
    base_time: datetime | None = None,
) -> list[dict[str, Any]]:
    """Account silent 180+ days, then sudden high-value activity."""
    base = base_time or datetime.now(timezone.utc)
    # Anchor: last "activity" was 180+ days ago (metadata only; burst is current)
    dormant_since = dormant_account.get("dormant_since") or (base - timedelta(days=200))
    if isinstance(dormant_since, str):
        dormant_since = datetime.fromisoformat(dormant_since)
    if dormant_since.tzinfo is None:
        dormant_since = dormant_since.replace(tzinfo=timezone.utc)

    silence_days = (base - dormant_since).days
    if silence_days < 180:
        base = dormant_since + timedelta(days=185)

    txns: list[dict[str, Any]] = []
    for i, receiver in enumerate(receivers[:5]):
        amount = round(random.uniform(20_000, 150_000), 2)
        ts = _offset(base, i * 30)
        txns.append(
            make_transaction(dormant_account, receiver, amount, ts, "dormant_activation")
        )
    return txns


# ── 6. Rapid multi-hop ────────────────────────────────────────────────────────

def generate_rapid_multihop(
    accounts: list[dict[str, Any]],
    base_time: datetime | None = None,
) -> list[dict[str, Any]]:
    """5+ transfers across 5+ accounts within 2 hours."""
    base = base_time or datetime.now(timezone.utc)
    chain = random.sample(accounts, min(7, len(accounts)))
    if len(chain) < 6:
        return []

    amount = round(random.uniform(5_000, 100_000), 2)
    txns: list[dict[str, Any]] = []
    # Total span: at most 120 minutes
    for i in range(len(chain) - 1):
        hop_amount = round(amount * random.uniform(0.95, 1.02), 2)
        ts = _offset(base, i * random.randint(5, 18))
        txns.append(
            make_transaction(chain[i], chain[i + 1], hop_amount, ts, "rapid_multihop")
        )
    return txns
