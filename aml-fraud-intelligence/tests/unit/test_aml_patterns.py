"""Unit tests for AML pattern simulation."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from data_simulation.schema import make_account, make_customer
from data_simulation.aml_patterns import (
    generate_structuring, generate_layering,
    generate_circular, generate_mule, generate_dormant_activation,
)


def _make_accounts(n=10):
    customers = [make_customer() for _ in range(n)]
    return [make_account(c["id"]) for c in customers]


def test_structuring_amounts_below_threshold():
    accounts = _make_accounts(6)
    txns = generate_structuring(accounts[0], accounts[1:], n_transactions=5)
    assert len(txns) == 5
    for t in txns:
        assert 8_500 <= t["amount"] <= 9_999
        assert t["aml_label"] == "structuring"
        assert t["is_flagged"] is True


def test_layering_decreasing_amounts():
    accounts = _make_accounts(8)
    txns = generate_layering(accounts, n_hops=5)
    assert len(txns) >= 4
    amounts = [t["amount"] for t in txns]
    assert all(amounts[i] >= amounts[i + 1] * 0.7 for i in range(len(amounts) - 1))


def test_circular_contains_cycle():
    accounts = _make_accounts(5)
    txns = generate_circular(accounts)
    assert len(txns) >= 3
    senders = [t["sender_account_id"] for t in txns]
    receivers = [t["receiver_account_id"] for t in txns]
    # Last receiver should equal first sender (cycle)
    assert receivers[-1] == senders[0]


def test_mule_consolidation_amount():
    accounts = _make_accounts(15)
    mule = accounts[0]
    senders = accounts[1:11]
    dest = accounts[11]
    txns = generate_mule(mule, senders, dest)
    # Last transaction is consolidation
    consolidation = txns[-1]
    assert consolidation["sender_account_id"] == mule["id"]
    assert consolidation["receiver_account_id"] == dest["id"]
    # Consolidation should be ~92% of total inflows
    total_in = sum(t["amount"] for t in txns[:-1])
    assert abs(consolidation["amount"] - total_in * 0.92) < 1.0
