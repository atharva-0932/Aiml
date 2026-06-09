"""Topic name constants and message schema definitions."""
from core.config import settings

TX_RAW = settings.kafka_topic_tx_raw         # "transactions.raw"
TX_SCORED = settings.kafka_topic_tx_scored   # "transactions.scored"
TX_FLAGGED = settings.kafka_topic_tx_flagged # "transactions.flagged"
RISK_ALERTS = settings.kafka_topic_risk_alerts
SAR_REQUESTS = settings.kafka_topic_sar_requests

ALL_TOPICS = [TX_RAW, TX_SCORED, TX_FLAGGED, RISK_ALERTS, SAR_REQUESTS]

# Risk tier thresholds
THRESHOLD_MEDIUM = 30.0
THRESHOLD_HIGH = 70.0
THRESHOLD_CRITICAL = 90.0


def classify_risk_tier(composite_score: float) -> str:
    if composite_score >= THRESHOLD_CRITICAL:
        return "CRITICAL"
    if composite_score >= THRESHOLD_HIGH:
        return "HIGH"
    if composite_score >= THRESHOLD_MEDIUM:
        return "MEDIUM"
    return "LOW"
