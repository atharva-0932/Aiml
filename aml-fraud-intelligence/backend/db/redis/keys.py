"""
Centralised Redis key schema.
All keys defined here — never hardcode key strings elsewhere.
"""


def risk_tx(tx_id: str) -> str:
    """Composite risk score for a single transaction. TTL: 5min."""
    return f"risk:tx:{tx_id}"


def risk_acct(account_id: str) -> str:
    """Full risk profile JSON for an account. TTL: 5min."""
    return f"risk:acct:{account_id}"


def vel_1h(account_id: str) -> str:
    """Transaction count in last 1 hour (INCR counter). TTL: 1h."""
    return f"vel:1h:{account_id}"


def vel_24h(account_id: str) -> str:
    """Transaction count in last 24 hours. TTL: 24h."""
    return f"vel:24h:{account_id}"


def graph_neighbors(account_id: str) -> str:
    """2-hop Neo4j neighbor result JSON. TTL: 60s."""
    return f"graph:nbr:{account_id}"


def graph_cycles_recent() -> str:
    """Sorted set: account_id → last_cycle_timestamp. TTL: 10min."""
    return "graph:cycles:recent"


def flagged_sorted() -> str:
    """Sorted set: account_id → composite_score. Top-N leaderboard."""
    return "flagged:sorted"


ALERTS_CHANNEL = "alerts:live"

# TTL constants (seconds)
TTL_RISK_SCORE = 300       # 5 minutes
TTL_GRAPH_NEIGHBORS = 60   # 1 minute
TTL_VELOCITY_1H = 3600     # 1 hour
TTL_VELOCITY_24H = 86400   # 24 hours
TTL_CYCLES = 600           # 10 minutes
