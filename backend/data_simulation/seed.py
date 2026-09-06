"""
Full dataset seeder — Phase 1.

Generates ~50,000 transactions (normal + all AML patterns) and writes:
  data/transactions.csv

Columns: transaction_id, timestamp, sender_account, receiver_account,
         amount, bank, pattern_label

Run: PYTHONPATH=backend python -m data_simulation.seed
"""
from __future__ import annotations

import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from data_simulation.aml_patterns import (
    generate_circular,
    generate_dormant_activation,
    generate_layering,
    generate_mule,
    generate_rapid_multihop,
    generate_structuring,
)
from data_simulation.normal_transactions import generate_normal_batch
from data_simulation.schema import PATTERN_LABELS, TX_COLUMNS, make_account, random_timestamp

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _episode_base_time() -> datetime:
    """Spread AML episodes across the same ~1y window as normal traffic (temporal split)."""
    now = datetime.now(timezone.utc)
    return random_timestamp(now.replace(year=now.year - 1), now)


def generate_dataset(n_normal: int = 47_000) -> tuple[list[dict], list[dict]]:
    """Build accounts + mixed transaction list targeting ~50k rows, 5–8% labeled."""
    print("Generating accounts...")
    accounts = [make_account(is_dormant=random.random() < 0.08) for _ in range(1_200)]
    dormant = [a for a in accounts if a["is_dormant"]]
    active = [a for a in accounts if not a["is_dormant"]]
    print(f"  {len(accounts)} accounts ({len(dormant)} dormant, {len(active)} active)")

    print(f"Generating {n_normal:,} normal transactions...")
    transactions = generate_normal_batch(active, n=n_normal)

    print("Generating AML pattern episodes (timestamps spread across past year)...")

    # Structuring: 60 × 8 ≈ 480
    for _ in range(60):
        sender = random.choice(active)
        receivers = random.sample(active, min(5, len(active)))
        transactions.extend(
            generate_structuring(sender, receivers, base_time=_episode_base_time())
        )

    # Layering: 120 × ~6 ≈ 720
    for _ in range(120):
        chain = random.sample(active, min(9, len(active)))
        transactions.extend(
            generate_layering(
                chain, base_time=_episode_base_time(), n_hops=random.randint(4, 8)
            )
        )

    # Circular: 100 × 3 ≈ 300
    for _ in range(100):
        ring = random.sample(active, min(4, len(active)))
        transactions.extend(generate_circular(ring, base_time=_episode_base_time()))

    # Mule: 55 × ~13 ≈ 715
    for _ in range(55):
        mule = random.choice(active)
        senders = random.sample([a for a in active if a["id"] != mule["id"]], 12)
        dest = random.choice([a for a in active if a["id"] != mule["id"]])
        transactions.extend(
            generate_mule(mule, senders, dest, base_time=_episode_base_time())
        )

    # Dormant activation: up to 45 × 5 ≈ 225
    if dormant:
        for _ in range(min(45, len(dormant))):
            d = random.choice(dormant)
            receivers = random.sample(active, min(5, len(active)))
            transactions.extend(
                generate_dormant_activation(d, receivers, base_time=_episode_base_time())
            )

    # Rapid multi-hop: 90 × ~6 ≈ 540
    for _ in range(90):
        chain = random.sample(active, min(7, len(active)))
        transactions.extend(
            generate_rapid_multihop(chain, base_time=_episode_base_time())
        )

    return accounts, transactions


def _print_distribution(df: pd.DataFrame) -> None:
    total = len(df)
    labeled = df["pattern_label"].notna() & (df["pattern_label"].astype(str).str.len() > 0)
    flagged = int(labeled.sum())
    rate = 100.0 * flagged / total if total else 0.0

    print("\n── Dataset summary ──────────────────────────────────────")
    print(f"  Total transactions : {total:,}")
    print(f"  Flagged (labeled)  : {flagged:,} ({rate:.2f}%)")
    print(f"  Clean              : {total - flagged:,}")
    print("\n  Pattern distribution:")
    counts = Counter(df.loc[labeled, "pattern_label"].tolist())
    for label in PATTERN_LABELS:
        print(f"    {label:20s} {counts.get(label, 0):>6,}")
    missing = [lab for lab in PATTERN_LABELS if counts.get(lab, 0) == 0]
    if missing:
        print(f"\n  WARNING: missing labels: {missing}")
    if not (5.0 <= rate <= 8.0):
        print(f"\n  WARNING: flagged rate {rate:.2f}% outside target band 5–8%")
    else:
        print(f"\n  Flagged rate within target band (5–8%).")
    print("────────────────────────────────────────────────────────\n")


def seed() -> Path:
    _, transactions = generate_dataset()
    df = pd.DataFrame(transactions)[TX_COLUMNS]
    # Normalize empty labels to pandas NA for clean CSV nulls
    df["pattern_label"] = df["pattern_label"].where(
        df["pattern_label"].notna() & (df["pattern_label"].astype(str).str.len() > 0),
        other=pd.NA,
    )
    df = df.sort_values("timestamp").reset_index(drop=True)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "transactions.csv"
    df.to_csv(out, index=False)

    _print_distribution(df)
    print(f"Wrote {len(df):,} rows → {out}")
    return out


if __name__ == "__main__":
    seed()
