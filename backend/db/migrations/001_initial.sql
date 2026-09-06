-- Phase 3: cold-path schema for Supabase (Postgres)
-- Apply via: psql "$SUPABASE_DB_URL" -f backend/db/migrations/001_initial.sql
-- or the Supabase SQL editor.

CREATE TABLE IF NOT EXISTS transactions (
  transaction_id TEXT PRIMARY KEY,
  timestamp TIMESTAMPTZ,
  sender_account TEXT,
  receiver_account TEXT,
  amount FLOAT,
  bank TEXT,
  pattern_label TEXT,
  risk_score FLOAT,
  scored_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
  id SERIAL PRIMARY KEY,
  transaction_id TEXT REFERENCES transactions(transaction_id),
  composite_score FLOAT,
  pattern TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shap_explanations (
  transaction_id TEXT REFERENCES transactions(transaction_id),
  feature_name TEXT,
  shap_value FLOAT
);

CREATE INDEX IF NOT EXISTS ix_transactions_sender ON transactions (sender_account);
CREATE INDEX IF NOT EXISTS ix_transactions_risk ON transactions (risk_score DESC);
CREATE INDEX IF NOT EXISTS ix_alerts_transaction ON alerts (transaction_id);
