from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TransactionIn(BaseModel):
    id: Optional[str] = None
    sender_account_id: str
    receiver_account_id: str
    amount: float = Field(gt=0)
    currency: str = "USD"
    transaction_type: str = "wire"
    channel: str = "online"
    device_id: Optional[str] = None
    merchant_id: Optional[str] = None
    ip_address: Optional[str] = None
    geo_lat: Optional[float] = None
    geo_lon: Optional[float] = None
    timestamp: Optional[str] = None
    aml_label: Optional[str] = None
    bank_code: Optional[str] = None
    country: Optional[str] = None


class TransactionOut(TransactionIn):
    id: str
    is_flagged: bool = False
    timestamp: str


class TransactionBatch(BaseModel):
    transactions: list[TransactionIn]
