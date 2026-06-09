-- V002: Create transactions table
-- Clustering key on (timestamp, sender_account_id) replaces PostgreSQL indexes
-- VARIANT type replaces JSONB for semi-structured metadata
-- VARCHAR(45) for IP addresses (no INET type in Snowflake)

CREATE TABLE IF NOT EXISTS transactions (
    id                   VARCHAR(36)     NOT NULL,
    sender_account_id    VARCHAR(36),
    receiver_account_id  VARCHAR(36),
    amount               NUMBER(18, 2)   NOT NULL,
    currency             VARCHAR(3)      DEFAULT 'USD',
    transaction_type     VARCHAR(30),                   -- wire | ACH | SWIFT | internal | crypto
    channel              VARCHAR(20),                   -- mobile | branch | ATM | online | API
    device_id            VARCHAR(36),
    merchant_id          VARCHAR(36),
    ip_address           VARCHAR(45),
    geo_lat              FLOAT,
    geo_lon              FLOAT,
    timestamp            TIMESTAMP_NTZ   NOT NULL,
    is_flagged           BOOLEAN         DEFAULT FALSE,
    aml_label            VARCHAR(30),                   -- NULL=normal | structuring | layering | circular | mule | dormant | rapid_hop
    metadata             VARIANT,                       -- arbitrary semi-structured fields
    CONSTRAINT pk_transactions PRIMARY KEY (id)
)
CLUSTER BY (timestamp, sender_account_id);
