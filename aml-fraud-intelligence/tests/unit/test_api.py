"""Unit tests for FastAPI endpoints (Phase 6) via TestClient."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.config import settings

HEADERS = {"X-API-Key": settings.api_key}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client: TestClient):
    with (
        patch("api.main._check_redis", new_callable=AsyncMock, return_value=True),
        patch("api.main._check_neo4j", new_callable=AsyncMock, return_value=True),
        patch("api.main._check_kafka", return_value=True),
    ):
        resp = client.get("/health", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_auth_required(client: TestClient):
    resp = client.get("/transactions")
    assert resp.status_code == 403


def test_transactions_endpoint(client: TestClient):
    with patch(
        "api.routes.transactions.scan_keys",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = client.get("/transactions", headers=HEADERS, params={"limit": 10})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_score_endpoint(client: TestClient):
    fake_graph = {
        "graph_risk": 40.0,
        "flags": ["CYCLE_DETECTED"],
        "cycle_count": 1,
        "is_mule": False,
        "layering_depth": 0,
        "pagerank": 0.2,
    }
    velocity = {
        "tx_count_1h": 1.0,
        "tx_volume_1h": 1000.0,
        "unique_receivers_24h": 1.0,
        "time_since_last_tx": 60.0,
    }
    with (
        patch(
            "api.routes.transactions.get_cached_graph_risk",
            new_callable=AsyncMock,
            return_value=fake_graph,
        ),
        patch(
            "api.routes.transactions.get_velocity_features",
            new_callable=AsyncMock,
            return_value=velocity,
        ),
    ):
        resp = client.post(
            "/transactions/score",
            headers=HEADERS,
            json={
                "sender_account": "acct-sender-test",
                "receiver_account": "acct-receiver-test",
                "amount": 9500.0,
                "bank": "JPMC",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["composite_score"], float)
    assert isinstance(body["tier"], str)
    assert body["tier"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_alerts_summary(client: TestClient):
    with patch(
        "api.routes.alerts.scan_keys",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = client.get("/alerts/summary", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["total_alerts"], int)
    assert isinstance(body["by_tier"], dict)
