"""Shared FastAPI client for the Streamlit dashboard."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Load project .env whether launched from repo root or dashboard/
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "your-secret-api-key-here")
API_KEY_HEADER = os.getenv("API_KEY_HEADER", "X-API-Key")


class ApiError(Exception):
    pass


def _headers() -> dict[str, str]:
    return {API_KEY_HEADER: API_KEY}


def get(path: str, params: dict[str, Any] | None = None, timeout: float = 60.0) -> Any:
    url = f"{BACKEND_URL}{path}"
    try:
        resp = requests.get(url, headers=_headers(), params=params or {}, timeout=timeout)
    except requests.RequestException as exc:
        raise ApiError(f"API request failed: {exc}") from exc
    if resp.status_code == 403:
        raise ApiError("API auth failed — check API_KEY in .env")
    if resp.status_code >= 400:
        raise ApiError(f"API {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def post(path: str, json_body: dict[str, Any], timeout: float = 60.0) -> Any:
    url = f"{BACKEND_URL}{path}"
    try:
        resp = requests.post(url, headers=_headers(), json=json_body, timeout=timeout)
    except requests.RequestException as exc:
        raise ApiError(f"API request failed: {exc}") from exc
    if resp.status_code >= 400:
        raise ApiError(f"API {resp.status_code}: {resp.text[:300]}")
    return resp.json()
