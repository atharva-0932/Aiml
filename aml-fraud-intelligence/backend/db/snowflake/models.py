"""
SQLAlchemy ORM models using Snowflake dialect.
Note: Snowflake uses VARCHAR(36) for IDs, VARIANT for JSON, TIMESTAMP_NTZ for UTC.
"""
from sqlalchemy import Column, String, Float, Boolean, Integer, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Account(Base):
    __tablename__ = "accounts"
    id = Column(String(36), primary_key=True)
    customer_id = Column(String(36), nullable=False)
    account_type = Column(String(20))
    bank_code = Column(String(10))
    country = Column(String(3))
    risk_tier = Column(Integer, default=1)
    created_at = Column(String(50))
    is_dormant = Column(Boolean, default=False)
    dormant_since = Column(String(50))


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String(36), primary_key=True)
    sender_account_id = Column(String(36))
    receiver_account_id = Column(String(36))
    amount = Column(Float)
    currency = Column(String(3))
    transaction_type = Column(String(30))
    channel = Column(String(20))
    device_id = Column(String(36))
    merchant_id = Column(String(36))
    ip_address = Column(String(45))
    geo_lat = Column(Float)
    geo_lon = Column(Float)
    timestamp = Column(String(50))
    is_flagged = Column(Boolean, default=False)
    aml_label = Column(String(30))


class RiskEvent(Base):
    __tablename__ = "risk_events"
    id = Column(String(36), primary_key=True)
    account_id = Column(String(36))
    transaction_id = Column(String(36))
    risk_score = Column(Float)
    anomaly_score = Column(Float)
    classifier_score = Column(Float)
    graph_risk_score = Column(Float)
    composite_score = Column(Float)
    risk_tier = Column(String(10))
    triggered_rules = Column(Text)
    shap_values = Column(Text)
    created_at = Column(String(50))
