"""
HTTP client for the FastAPI backend.
All dashboard pages talk to the backend exclusively through this module.
"""
from __future__ import annotations

import os
import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev-key")
HEADERS = {"X-API-Key": API_KEY}
TIMEOUT = 10.0


def _client() -> httpx.Client:
    return httpx.Client(base_url=BACKEND_URL, headers=HEADERS, timeout=TIMEOUT)


def get_flagged_transactions(limit: int = 200, offset: int = 0) -> list[dict]:
    with _client() as c:
        r = c.get("/api/v1/transactions/flagged", params={"limit": limit, "offset": offset})
        r.raise_for_status()
        return r.json().get("data", [])


def get_risk_profile(account_id: str) -> dict:
    with _client() as c:
        r = c.get(f"/api/v1/accounts/{account_id}/risk-profile")
        r.raise_for_status()
        return r.json()


def get_graph_neighbors(account_id: str) -> list[dict]:
    with _client() as c:
        r = c.get(f"/api/v1/accounts/{account_id}/graph-neighbors")
        r.raise_for_status()
        return r.json()


def get_graph_cycles(lookback_days: int = 3) -> list[dict]:
    with _client() as c:
        r = c.get("/api/v1/graph/cycles", params={"lookback_days": lookback_days})
        r.raise_for_status()
        return r.json()


def get_graph_mules() -> list[dict]:
    with _client() as c:
        r = c.get("/api/v1/graph/mules")
        r.raise_for_status()
        return r.json()


def get_top_flagged(n: int = 20) -> list[dict]:
    with _client() as c:
        r = c.get("/api/v1/risk/top-flagged", params={"n": n})
        r.raise_for_status()
        return r.json()


def get_copilot_explanation(account_id: str) -> str:
    with _client() as c:
        r = c.post(f"/api/v1/copilot/explain/{account_id}", timeout=30.0)
        r.raise_for_status()
        return r.json().get("explanation", "")


def generate_sar(account_id: str, notes: str = "") -> dict:
    with _client() as c:
        r = c.post(f"/api/v1/copilot/sar/{account_id}",
                   json={"notes": notes}, timeout=60.0)
        r.raise_for_status()
        return r.json()


def generate_report(account_id: str, investigator: str = "AML Analyst") -> bytes:
    with _client() as c:
        r = c.post("/api/v1/reports/generate",
                   json={"account_id": account_id, "investigator_name": investigator},
                   timeout=60.0)
        r.raise_for_status()
        return r.content


def health() -> dict:
    try:
        with _client() as c:
            r = c.get("/health")
            return r.json()
    except Exception:
        return {"status": "unreachable"}
