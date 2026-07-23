"""Centralised Redis key schema for velocity + risk scores."""


def tx_count_1h(account_id: str) -> str:
    return f"tx_count:{account_id}:1h"


def tx_volume_1h(account_id: str) -> str:
    return f"tx_volume:{account_id}:1h"


def unique_receivers_24h(account_id: str) -> str:
    return f"unique_receivers:{account_id}:24h"


def last_tx_ts(account_id: str) -> str:
    return f"last_tx_ts:{account_id}"


def risk_score(transaction_id: str) -> str:
    return f"risk_score:{transaction_id}"


def graph_risk(account_id: str) -> str:
    return f"graph_risk:{account_id}"


TTL_1H = 3600
TTL_24H = 86400
