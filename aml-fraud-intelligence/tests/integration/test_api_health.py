"""
Integration test — verify FastAPI health endpoint.
Requires backend to be running: uvicorn api.main:app
"""
import pytest
import httpx

BASE_URL = "http://localhost:8000"


@pytest.mark.integration
def test_health_endpoint():
    r = httpx.get(f"{BASE_URL}/health", timeout=5.0)
    assert r.status_code == 200
    data = r.json()
    assert "status" in data


@pytest.mark.integration
def test_root_endpoint():
    r = httpx.get(f"{BASE_URL}/", timeout=5.0)
    assert r.status_code == 200
    assert "docs" in r.json()


@pytest.mark.integration
def test_ingest_requires_api_key():
    r = httpx.post(
        f"{BASE_URL}/api/v1/transactions/ingest",
        json={"transactions": []},
    )
    assert r.status_code == 403
