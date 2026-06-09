from pydantic import BaseModel
from typing import Optional


class RiskScoreRequest(BaseModel):
    transaction: dict


class RiskScoreResponse(BaseModel):
    transaction_id: str
    account_id: str
    composite_score: float
    risk_tier: str
    anomaly_score: float
    classifier_score: float
    graph_risk_score: float
    triggered_rules: list[str]
    shap_values: dict = {}


class AlertEvent(BaseModel):
    account_id: str
    tx_id: Optional[str]
    composite_score: float
    risk_tier: str
    triggered_rules: list[str]
    amount: Optional[float]
    timestamp: str
