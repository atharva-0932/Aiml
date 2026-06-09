"""
Entity generation using Faker.
Produces customers, accounts, devices, and merchants as base entities.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

ACCOUNT_TYPES = ["checking", "savings", "business", "crypto"]
TRANSACTION_TYPES = ["wire", "ACH", "SWIFT", "internal", "crypto", "RTGS"]
CHANNELS = ["mobile", "branch", "ATM", "online", "API"]
CURRENCIES = ["USD", "EUR", "GBP", "SGD", "AED"]
COUNTRIES = ["US", "GB", "DE", "SG", "AE", "NG", "CN", "RU", "MX", "BR"]
BANK_CODES = ["BOFA", "JPMC", "CITI", "HSBC", "BARC", "DEUT", "SGBK", "ANON"]


def new_id() -> str:
    return str(uuid.uuid4())


def random_timestamp(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def make_customer(risk_tier: int = 1) -> dict[str, Any]:
    return {
        "id": new_id(),
        "name": fake.name(),
        "email": fake.email(),
        "phone": fake.phone_number(),
        "country": random.choice(COUNTRIES),
        "risk_tier": risk_tier,
        "kyc_verified": random.random() > 0.1,
    }


def make_account(customer_id: str, is_dormant: bool = False) -> dict[str, Any]:
    created = fake.date_time_between(start_date="-5y", end_date="-6m", tzinfo=timezone.utc)
    dormant_since = None
    if is_dormant:
        dormant_since = fake.date_time_between(
            start_date=created, end_date="-7m", tzinfo=timezone.utc
        )
    return {
        "id": new_id(),
        "customer_id": customer_id,
        "account_type": random.choice(ACCOUNT_TYPES),
        "bank_code": random.choice(BANK_CODES),
        "country": random.choice(COUNTRIES),
        "risk_tier": random.choices([1, 2, 3], weights=[70, 20, 10])[0],
        "created_at": created.isoformat(),
        "is_dormant": is_dormant,
        "dormant_since": dormant_since.isoformat() if dormant_since else None,
    }


def make_device(account_id: str) -> dict[str, Any]:
    return {
        "id": new_id(),
        "account_id": account_id,
        "fingerprint": fake.sha256()[:32],
        "os": random.choice(["iOS", "Android", "Windows", "macOS"]),
        "ip_hash": fake.ipv4()[:8],
    }


def make_merchant() -> dict[str, Any]:
    return {
        "id": new_id(),
        "name": fake.company(),
        "category": random.choice(["retail", "casino", "forex", "crypto", "luxury", "wire"]),
        "country": random.choice(COUNTRIES),
        "mcc_code": str(random.randint(1000, 9999)),
    }
