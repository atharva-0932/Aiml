from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Snowflake ──────────────────────────────────────────────────────────────
    snowflake_account: str = ""
    snowflake_user: str = ""
    snowflake_password: str = ""
    snowflake_database: str = "AML_DB"
    snowflake_schema: str = "PUBLIC"
    snowflake_warehouse: str = "COMPUTE_WH"
    snowflake_role: str = "SYSADMIN"

    # ── Kafka ──────────────────────────────────────────────────────────────────
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_topic_tx_raw: str = "transactions.raw"
    kafka_topic_tx_scored: str = "transactions.scored"
    kafka_topic_tx_flagged: str = "transactions.flagged"
    kafka_topic_risk_alerts: str = "risk.alerts"
    kafka_topic_sar_requests: str = "sar.requests"

    # ── Redis ──────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Neo4j ──────────────────────────────────────────────────────────────────
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # ── GenAI ──────────────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: str = "gemini"

    # ── Security ───────────────────────────────────────────────────────────────
    api_key: str = "dev-key"
    api_key_header: str = "X-API-Key"

    # ── App ────────────────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"
    backend_url: str = "http://localhost:8000"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
