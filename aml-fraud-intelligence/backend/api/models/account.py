from pydantic import BaseModel
from typing import Optional


class AccountRiskProfile(BaseModel):
    account_id: str
    composite_score: float
    anomaly_score: float
    classifier_score: float
    graph_risk_score: float
    risk_tier: str
    triggered_rules: list[str]
    graph_in_degree: int = 0
    graph_out_degree: int = 0
    cycle_membership: int = 0
    pagerank_score: float = 0.0
    hop_depth: int = 0
    shap_values: dict = {}
    cached: bool = False
