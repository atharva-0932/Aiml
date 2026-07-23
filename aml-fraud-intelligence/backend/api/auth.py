"""API key auth dependency — X-API-Key header from .env."""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from core.config import settings


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    expected = settings.api_key
    header_name = settings.api_key_header or "X-API-Key"
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid or missing {header_name}",
        )
    return x_api_key
