"""
Full dataset seeding script.
Generates ~50,000 transactions (normal + all AML patterns) and outputs:
  - data/accounts.csv
  - data/transactions.csv
  - data/customers.csv

Then optionally loads to Snowflake via COPY INTO.

Run: python -m data_simulation.seed [--no-snowflake]
"""
from __future__ import annotations

import argparse
import csv
import os
import random
from datetime import datetime, timezone
from pathlib import Path

from data_simulation.schema import make_customer, make_account, make_device
from data_simulation.normal_transactions import generate_normal_batch
from data_simulation.aml_patterns import (
    generate_structuring,
    generate_layering,
    generate_circular,
    generate_mule,
    generate_dormant_activation,
    generate_rapid_multihop,
)
from core.logging import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"

ACCOUNT_COLUMNS = [
    "id", "customer_id", "account_type", "bank_code", "country",
    "risk_tier", "created_at", "is_dormant", "dormant_since",
]
TX_COLUMNS = [
    "id", "sender_account_id", "receiver_account_id", "amount", "currency",
    "transaction_type", "channel", "device_id", "merchant_id", "ip_address",
    "geo_lat", "geo_lon", "timestamp", "is_flagged", "aml_label",
]


def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info("CSV written", path=str(path), rows=len(rows))


def generate_dataset(n_normal: int = 40_000) -> tuple[list, list, list]:
    log.info("Generating entities...")

    # Generate 500 customers and 800 accounts
    customers = [make_customer(risk_tier=random.choices([1, 2, 3], weights=[70, 20, 10])[0])
                 for _ in range(500)]
    accounts = []
    for cust in customers:
        n_accts = random.randint(1, 3)
        for _ in range(n_accts):
            accts = make_account(cust["id"], is_dormant=random.random() < 0.08)
            accounts.append(accts)

    # Separate dormant accounts for AML patterns
    dormant_accounts = [a for a in accounts if a["is_dormant"]]
    active_accounts = [a for a in accounts if not a["is_dormant"]]

    log.info("Entities created", accounts=len(accounts), dormant=len(dormant_accounts))

    # ── Normal transactions ────────────────────────────────────────────────────
    log.info(f"Generating {n_normal:,} normal transactions...")
    transactions = generate_normal_batch(active_accounts, n=n_normal)

    # ── AML patterns ──────────────────────────────────────────────────────────
    log.info("Generating AML patterns...")
    base = datetime.now(timezone.utc)

    # Structuring: 50 episodes × 8 txns each = 400
    for _ in range(50):
        sender = random.choice(active_accounts)
        receivers = random.sample(active_accounts, 5)
        transactions.extend(generate_structuring(sender, receivers))

    # Layering: 80 episodes × ~6 txns each = 480
    for _ in range(80):
        chain_accounts = random.sample(active_accounts, 7)
        transactions.extend(generate_layering(chain_accounts, n_hops=random.randint(4, 7)))

    # Circular flows: 60 episodes × ~4 txns each = 240
    for _ in range(60):
        ring = random.sample(active_accounts, 4)
        transactions.extend(generate_circular(ring))

    # Mule accounts: 40 episodes × ~13 txns each = 520
    for _ in range(40):
        mule = random.choice(active_accounts)
        senders = random.sample(active_accounts, 10)
        dest = random.choice(active_accounts)
        transactions.extend(generate_mule(mule, senders, dest))

    # Dormant activation: 30 episodes × 5 txns each = 150
    if dormant_accounts:
        for _ in range(min(30, len(dormant_accounts))):
            dormant = random.choice(dormant_accounts)
            receivers = random.sample(active_accounts, 5)
            transactions.extend(generate_dormant_activation(dormant, receivers))

    # Rapid multihop: 60 episodes × ~6 txns each = 360
    for _ in range(60):
        chain = random.sample(active_accounts, 7)
        transactions.extend(generate_rapid_multihop(chain))

    log.info("Dataset generated",
             total_transactions=len(transactions),
             fraud_transactions=sum(1 for t in transactions if t["is_flagged"]))

    return customers, accounts, transactions


def seed(load_snowflake: bool = True) -> None:
    customers, accounts, transactions = generate_dataset()

    # Write CSVs
    _write_csv(DATA_DIR / "customers.csv", customers,
               ["id", "name", "email", "phone", "country", "risk_tier", "kyc_verified"])
    _write_csv(DATA_DIR / "accounts.csv", accounts, ACCOUNT_COLUMNS)
    _write_csv(DATA_DIR / "transactions.csv", transactions, TX_COLUMNS)

    if not load_snowflake:
        log.info("Snowflake load skipped (--no-snowflake)")
        return

    log.info("Loading data into Snowflake via COPY INTO...")
    try:
        from db.snowflake.session import get_engine
        engine = get_engine()
        if engine is None:
            log.warning("Snowflake not configured — data saved to CSV only")
            return

        with engine.connect() as conn:
            for table, csv_path in [
                ("accounts", DATA_DIR / "accounts.csv"),
                ("transactions", DATA_DIR / "transactions.csv"),
            ]:
                conn.execute(f"PUT file://{csv_path.resolve()} @aml_stage AUTO_COMPRESS=TRUE OVERWRITE=TRUE")
                conn.execute(
                    f"COPY INTO {table} FROM @aml_stage/{csv_path.name}.gz "
                    "FILE_FORMAT=(TYPE=CSV FIELD_OPTIONALLY_ENCLOSED_BY='\"' SKIP_HEADER=1 NULL_IF=('NULL','null','')) "
                    "ON_ERROR=CONTINUE PURGE=TRUE"
                )
                log.info(f"Loaded {table} into Snowflake")

    except Exception as exc:
        log.error("Snowflake load failed — data available in CSV", error=str(exc))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed AML dataset")
    parser.add_argument("--no-snowflake", action="store_true",
                        help="Skip Snowflake load — CSV output only")
    args = parser.parse_args()
    seed(load_snowflake=not args.no_snowflake)
