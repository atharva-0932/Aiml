"""
Application settings — all connection strings come from .env.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_db_url: str = ""

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_tx_raw: str = "transactions.raw"

    redis_url: str = "redis://localhost:6379/0"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    api_key: str = "dev-key"
    api_key_header: str = "X-API-Key"

    app_env: str = "development"
    log_level: str = "INFO"
    backend_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
