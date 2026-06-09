-- V001: Create accounts table
-- Snowflake note: VARCHAR(36) for UUIDs, TIMESTAMP_NTZ for UTC timestamps

CREATE TABLE IF NOT EXISTS accounts (
    id              VARCHAR(36)     NOT NULL,
    customer_id     VARCHAR(36)     NOT NULL,
    account_type    VARCHAR(20),                        -- checking | savings | business | crypto
    bank_code       VARCHAR(10),
    country         VARCHAR(3),
    risk_tier       INTEGER         DEFAULT 1,          -- 1=low | 2=medium | 3=high
    created_at      TIMESTAMP_NTZ,
    is_dormant      BOOLEAN         DEFAULT FALSE,
    dormant_since   TIMESTAMP_NTZ,
    CONSTRAINT pk_accounts PRIMARY KEY (id)
);
