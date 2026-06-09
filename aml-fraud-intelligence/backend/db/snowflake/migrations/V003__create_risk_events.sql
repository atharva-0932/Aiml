-- V003: Create risk_events table
-- Stores composite risk scores from ML pipeline + triggered rule metadata

CREATE TABLE IF NOT EXISTS risk_events (
    id                VARCHAR(36)     NOT NULL,
    account_id        VARCHAR(36),
    transaction_id    VARCHAR(36),
    risk_score        FLOAT,                            -- 0.0–100.0 final score
    anomaly_score     FLOAT,                            -- Isolation Forest output (0–1)
    classifier_score  FLOAT,                            -- XGBoost probability (0–1)
    graph_risk_score  FLOAT,                            -- Neo4j PageRank-derived (0–1)
    composite_score   FLOAT,                            -- 0.4×xgb + 0.35×iso + 0.25×graph × 100
    risk_tier         VARCHAR(10),                      -- LOW | MEDIUM | HIGH | CRITICAL
    triggered_rules   VARIANT,                          -- JSON array of rule names
    shap_values       VARIANT,                          -- SHAP feature contribution map
    created_at        TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_risk_events PRIMARY KEY (id)
)
CLUSTER BY (created_at, account_id);
