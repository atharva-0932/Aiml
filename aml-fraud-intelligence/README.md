# AML Fraud Intelligence

Production-grade Anti-Money Laundering detection platform for portfolio /
SWE–Data Engineering interviews. Detects suspicious transaction patterns
in real time with Kafka streaming, Redis velocity counters, Neo4j graph
analytics, and XGBoost scoring — results visualized in Streamlit.

## Architecture

```
FastAPI → Kafka → [ml_scorer, graph_sync] consumers
                     ↓               ↓
                  Redis           Neo4j
                     ↓
                Supabase (cold path)
                     ↓
                Streamlit
```

## Tech Stack

| Layer        | Technology                    |
|--------------|-------------------------------|
| API          | FastAPI + Uvicorn             |
| Event Bus    | Apache Kafka 3.7 (KRaft)      |
| Hot Cache    | Redis 7 (hiredis)             |
| Graph DB     | Neo4j 5 + GDS plugin          |
| Cold Storage | Supabase (hosted Postgres)    |
| ML           | XGBoost + SHAP                |
| Dashboard    | Streamlit + Plotly + PyVis    |
| Deployment   | Docker Compose                |

## AML Patterns

1. **Structuring** — multiple payments just below $10,000
2. **Layering** — 4–8 hop cross-bank transfer chains
3. **Circular Flow** — A → B → C → A within 72 hours
4. **Mule Accounts** — fan-in from 10+ sources, ~92% forwarded to one destination
5. **Dormant Activation** — silent 180+ days, then sudden high-value activity
6. **Rapid Multi-hop** — 5+ transfers across 5+ accounts within 2 hours

## Composite Risk Score

```
Composite = 0.60 × XGBoost + 0.40 × Graph Risk
Tiers: LOW < 30 | MEDIUM 30–70 | HIGH 70–90 | CRITICAL > 90
```

## Build Status

| Phase | Status |
|-------|--------|
| 1. Data simulation → `data/transactions.csv` | **Done** (50k rows, 6% labeled) |
| 2. Docker Compose (kafka, redis, neo4j) | **Done** (containers healthy) |
| 3. Kafka producer + consumers | **Done** (stub scoring) |
| 4. Redis velocity counters | Pending (hooks live in ml_scorer) |
| 5. Neo4j graph sync + Cypher | **Done** (queries + GraphRiskScorer + tests) |
| 6. XGBoost + SHAP | Pending |
| 7. FastAPI endpoints | Pending |
| 8. Supabase cold path | Pending (upsert hook live; needs real URL + migration) |
| 9. Streamlit dashboard (3 pages) | Pending |
| 10. Unit tests | Pending |

## Phase 1 — Data Simulation

Generate ~50k synthetic transactions with ground-truth AML labels.

```bash
cd aml-fraud-intelligence
pip install -e .
PYTHONPATH=backend python -m data_simulation.seed
```

Output: `data/transactions.csv`

Columns: `transaction_id`, `timestamp`, `sender_account`, `receiver_account`,
`amount`, `bank`, `pattern_label` (null if clean).

Target: **5–8%** of rows labeled with one of the six AML patterns.

## Phase 2 — Docker Compose (infra only)

Services: `kafka` (KRaft :9092), `redis` (:6379), `neo4j` + GDS (:7474/:7687).
Network: `aml-network`. No Postgres / FastAPI / Streamlit yet.

```bash
cd aml-fraud-intelligence
cp -n .env.example .env
docker compose -f docker/docker-compose.yml config   # validate
# later: docker compose -f docker/docker-compose.yml up -d
```

## Phase 3 — Kafka producer + consumers

Topic: `transactions.raw` (4 partitions, RF=1), created on startup.

```bash
# Install Phase 3 deps
pip install -e .

# Optional: apply Supabase migration (cold-path writes)
# psql "$SUPABASE_DB_URL" -f backend/db/migrations/001_initial.sql

# Terminal 1 — ML scorer (Redis velocity + stub score + Supabase upsert)
PYTHONPATH=backend python3 -m kafka.consumers.ml_scorer

# Terminal 2 — Graph sync (Neo4j MERGE, batch 50)
PYTHONPATH=backend python3 -m kafka.consumers.graph_sync

# Terminal 3 — Producer (streams data/transactions.csv)
PYTHONPATH=backend python3 -m kafka.producer
# faster smoke test: PYTHONPATH=backend python3 -m kafka.producer --delay 0
```

`.env` must use **localhost** hosts when running these scripts on the host machine
(`KAFKA_BOOTSTRAP_SERVERS=localhost:9092`, etc.).

Because Kafka advertises `PLAINTEXT://kafka:9092` inside Docker, add this line to
`/etc/hosts` so host-side clients can resolve the broker after metadata redirect:

```text
127.0.0.1 kafka
```

## Phase 4 — Neo4j Cypher + graph risk scoring

```bash
PYTHONPATH=backend python3 -m graph.seed_fixture
PYTHONPATH=backend python3 -m pytest tests/unit/test_graph.py -v
```

`GraphRiskScorer` returns `graph_risk` 0–100 from cycles / mule / layering / PageRank.
Not wired into Kafka consumers yet (Phase 5).

## Constraints

- Python 3.11
- No LangChain, ChromaDB, Snowflake, or PDF generation
- Secrets via `.env` only
- Supabase is external (not in Docker Compose)
- Kafka client: **confluent-kafka** only (not kafka-python)
