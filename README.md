# AML Fraud Intelligence

Production-style **Anti-Money Laundering (AML) detection platform** built for SWE / Data Engineering portfolio interviews.

It simulates ~50k bank transactions, streams them through **Kafka**, scores each event with **XGBoost + Neo4j graph risk + SHAP**, caches hot results in **Redis**, exposes them via **FastAPI**, and lets analysts investigate in a **Streamlit** dashboard (Overview · Explorer · Graph).

```
Composite Risk = 0.60 × XGBoost + 0.40 × Graph Risk
Tiers: LOW < 30 | MEDIUM 30–70 | HIGH 70–90 | CRITICAL > 90
Alert when composite_score > 70
```

---

## Table of contents

1. [What this project does](#what-this-project-does)
2. [Architecture](#architecture)
3. [Tech stack](#tech-stack)
4. [Repository layout](#repository-layout)
5. [AML patterns detected](#aml-patterns-detected)
6. [Phase-by-phase build (what was done)](#phase-by-phase-build-what-was-done)
7. [Scoring pipeline (deep dive)](#scoring-pipeline-deep-dive)
8. [API reference](#api-reference)
9. [Dashboard](#dashboard)
10. [Redis / Neo4j / Supabase](#redis--neo4j--supabase)
11. [Setup & run](#setup--run)
12. [Tests](#tests)
13. [Diagrams](#diagrams)
14. [Interview talking points](#interview-talking-points)
15. [Constraints & non-goals](#constraints--non-goals)

---

## What this project does

| Capability | Implementation |
|------------|----------------|
| Synthetic AML dataset | ~49,953 transactions, ~5.9% labeled with 6 ground-truth patterns |
| Real-time stream | Kafka topic `transactions.raw` (4 partitions, KRaft) |
| Velocity features | Redis counters (1h count/volume, 24h unique receivers) |
| Tabular ML | XGBoost classifier + SHAP top-5 explanations |
| Graph AML analytics | Neo4j Cypher + GDS PageRank (cycles, mule, layering) |
| Composite risk | Weighted blend of model + graph scores |
| Hot path reads | Redis keys for scores, SHAP, alerts |
| Cold path writes | Optional Supabase (Postgres) upserts |
| Investigation UI | 3 Streamlit pages via FastAPI only (no direct DB from UI) |
| Auth | `X-API-Key` on all protected API routes |
| Tests | 17 unit tests (simulation, graph, ML, API) |

---

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │           Streamlit (:8501)             │
                    │  Overview · Explorer · Graph (PyVis)    │
                    └──────────────────┬──────────────────────┘
                                       │ X-API-Key
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │          FastAPI (:8000)                │
                    │  /transactions  /alerts  /graph         │
                    └──────────┬───────────────┬──────────────┘
                               │               │
                    ┌──────────▼──────┐   ┌────▼─────────────┐
                    │  Redis (hot)    │   │  Neo4j + GDS     │
                    │  risk/shap/     │   │  cycles·mule·PR  │
                    │  alert/velocity │   └──────────────────┘
                    └──────────▲──────┘
                               │
         ┌─────────────────────┴─────────────────────┐
         │              Kafka (KRaft)                │
         │           topic: transactions.raw         │
         └──────▲──────────────────────▲─────────────┘
                │                      │
     ┌──────────┴────────┐   ┌─────────┴──────────┐
     │  kafka.producer   │   │  ml_scorer          │
     │  (CSV → topic)    │   │  XGBoost+Graph+SHAP │
     └───────────────────┘   │  graph_sync→Neo4j   │
                             └─────────┬───────────┘
                                       │ optional
                                       ▼
                             ┌───────────────────┐
                             │ Supabase (cold)   │
                             └───────────────────┘
```

Mermaid versions (architecture + analyst flow): [`docs/diagrams.md`](docs/diagrams.md).

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| API | FastAPI + Uvicorn |
| Event bus | Apache Kafka (Confluent `cp-kafka` 7.6.1, KRaft, **no Zookeeper**) |
| Kafka client | **confluent-kafka** only |
| Hot cache | Redis 7 (+ hiredis) |
| Graph DB | Neo4j 5 Enterprise + Graph Data Science plugin |
| Cold storage | Supabase / Postgres (optional, external) |
| ML | XGBoost + SHAP + scikit-learn |
| Dashboard | Streamlit + Plotly + PyVis |
| Infra | Docker Compose |
| Config | `.env` via `pydantic-settings` |
| Tests | pytest + pytest-asyncio + FastAPI TestClient |

---

## Repository layout

```
.
├── backend/
│   ├── api/                  # FastAPI app, auth, routes, CSV store
│   ├── core/                 # Settings from .env
│   ├── data_simulation/      # Seed ~50k labeled transactions
│   ├── db/
│   │   ├── redis/            # Client, key schema, cache helpers
│   │   ├── neo4j/            # Async driver
│   │   ├── supabase/         # Optional cold-path writes
│   │   └── migrations/       # 001_initial.sql
│   ├── graph/                # Cypher analytics + GraphRiskScorer
│   ├── kafka/
│   │   ├── producer.py
│   │   ├── topics.py / serde.py
│   │   └── consumers/
│   │       ├── ml_scorer.py  # Score + Redis (+ optional Supabase)
│   │       └── graph_sync.py # Batch MERGE into Neo4j
│   └── ml/                   # Features, train, XGBoost/SHAP/composite
│       └── models/           # model.json, feature_columns.json, metrics
├── dashboard/
│   ├── Home.py               # Overview
│   ├── api_client.py         # BACKEND_URL + X-API-Key
│   └── pages/
│       ├── 1_Explorer.py
│       └── 2_Graph.py
├── data/transactions.csv
├── docker/docker-compose.yml # kafka, redis, neo4j, streamlit
├── docs/diagrams.md
├── tests/unit/               # 17 tests
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## AML patterns detected

Ground-truth labels in `pattern_label` (null = clean):

| # | Label | Behavior |
|---|-------|----------|
| 1 | `structuring` | Multiple payments just under $10,000 |
| 2 | `layering` | 4–8 hop cross-bank transfer chains |
| 3 | `circular_flow` | A → B → C → A style cycles (within ~72h) |
| 4 | `mule` | Fan-in from 10+ sources; most volume exits to one destination |
| 5 | `dormant_activation` | Long silence (180+ days), then sudden high-value activity |
| 6 | `rapid_multihop` | 5+ hops across 5+ accounts within ~2 hours |

Dataset quality targets (enforced by unit tests):

- All 6 labels present
- Flagged rate **5–8%**
- No nulls in required fields (`transaction_id`, `timestamp`, `sender_account`, `receiver_account`, `amount`, `bank`)
- Timestamps span **> 30 days** (actually ~year-scale for temporal ML split)

---

## Phase-by-phase build (what was done)

### Phase 1 — Data simulation ✅

- Generators for normal traffic + 6 AML episode types
- Output: `data/transactions.csv` (~49,953 rows)
- AML episode timestamps spread across the past year so a **temporal train/test split** is valid

```bash
PYTHONPATH=backend python3 -m data_simulation.seed
```

### Phase 2 — Docker Compose infra ✅

Services on `aml-network`:

| Service | Ports | Notes |
|---------|-------|-------|
| `kafka` | 9092 | Confluent KRaft; advertised as `kafka:9092` |
| `redis` | 6379 | Hot cache, no persistence for demo |
| `neo4j` | 7474, 7687 | Auth `neo4j/password`; GDS plugin; **no full `.env` mount** |
| `streamlit` | 8501 | Optional container; talks to host API via `host.docker.internal` |

```bash
docker compose -f docker/docker-compose.yml up -d kafka redis neo4j
```

### Phase 3 — Kafka producer + consumers ✅

- Topic `transactions.raw` created on startup (4 partitions, RF=1)
- **Producer** streams CSV rows (optional `--delay`)
- **`ml_scorer`** — velocity → features → XGBoost → graph risk → composite → Redis (+ optional Supabase)
- **`graph_sync`** — batches TRANSFER edges into Neo4j (batch size 50)

```bash
PYTHONPATH=backend python3 -m kafka.consumers.graph_sync
PYTHONPATH=backend python3 -m kafka.consumers.ml_scorer
PYTHONPATH=backend python3 -m kafka.producer --delay 0
```

### Phase 4 — Neo4j graph analytics ✅

- Cypher: cycle detection, mule heuristic, layering chains
- GDS PageRank via native `gds.graph.project('…', 'Account', 'TRANSFER')`
- `GraphRiskScorer` → `graph_risk` 0–100 + flags (`CYCLE_DETECTED`, `MULE_PATTERN`, `LAYERING_CHAIN`, `HIGH_PAGERANK`)
- Streaming path uses a **fast mode** (cycles + mule + PageRank; skips expensive layering) so Kafka consumers do not stall on dense graphs
- Fixture + 4 unit tests

### Phase 5 — XGBoost + SHAP + composite ✅

**9 features:**

`amount`, `amount_to_mean_ratio`, `is_round_amount`, `hour_of_day`, `is_weekend`, `tx_count_1h`, `tx_volume_1h`, `unique_receivers_24h`, `time_since_last_tx`

**Training metrics** (from `backend/ml/models/training_metrics.json`):

| Metric | Value |
|--------|-------|
| AUC-ROC | ~0.995 |
| Recall (flagged) | ~0.988 |
| Precision | ~0.43 |
| F1 | ~0.60 |
| Train / test | 39,962 / 9,991 (temporal split) |

Artifacts: `model.json`, `feature_columns.json`, `training_metrics.json`.

```bash
PYTHONPATH=backend python3 -m ml.train --csv data/transactions.csv
```

### Phase 6 — FastAPI ✅

- App: `backend/api/main.py`
- Auth: `X-API-Key` (from `.env`)
- In-memory CSV join via `api.store` + Redis/Neo4j for live scores
- Routes for health, transactions, live score, alerts, graph account/neighbors

```bash
uvicorn api.main:app --port 8000 --app-dir backend
# Docs: http://localhost:8000/docs
```

### Phase 7 — Streamlit dashboard ✅

Three pages only (no LangChain / PDF / heatmaps):

| Page | File | What it shows |
|------|------|----------------|
| Overview | `dashboard/Home.py` | KPI cards, pattern donut, top-10 risk accounts, 30s auto-refresh |
| Explorer | `pages/1_Explorer.py` | Filters + scored table + SHAP bar chart |
| Graph | `pages/2_Graph.py` | Account risk card + PyVis network (capped for UI) |

All data via FastAPI (`BACKEND_URL` + `API_KEY`).

```bash
streamlit run dashboard/Home.py --server.port 8501
```

### Phase 8 — Unit tests + cleanup ✅

- `tests/unit/test_simulation.py` — CSV quality (4)
- `tests/unit/test_graph.py` — Neo4j analytics (4)
- `tests/unit/test_ml.py` — features / composite / model / temporal split (4)
- `tests/unit/test_api.py` — TestClient auth + endpoints (5)
- GDS deprecation fixed (native project)
- Neo4j Compose env isolated from full `.env`
- **17 tests passing**

```bash
PYTHONPATH=backend python3 -m pytest tests/unit/ -v
```

---

## Scoring pipeline (deep dive)

For each Kafka message, `ml_scorer`:

1. Deserialize transaction
2. Read Redis velocity for `sender_account`
3. Extract 9 features
4. `XGBoostScorer.score` → 0–100
5. `GraphRiskScorer` (cached in Redis 1h) → `graph_risk` + flags
6. Composite + tier
7. SHAP top-5 feature contributions
8. Write Redis:
   - `risk_score:{tx_id}`
   - `shap:{tx_id}` (TTL 24h)
   - `alert:{tx_id}` if composite **> 70** (TTL 24h)
   - velocity keys + `graph_risk:{account}`
9. Optional Supabase: upsert transaction, insert alert/SHAP rows

`graph_sync` independently MERGEs account nodes and TRANSFER relationships for investigation queries.

---

## API reference

Base URL: `http://localhost:8000`  
Header: `X-API-Key: <API_KEY from .env>`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Status of Kafka / Redis / Neo4j + CSV load count |
| GET | `/transactions` | Scored txs from Redis (`limit`, `offset`, `tier`, `pattern`) |
| GET | `/transactions/{id}` | Detail + SHAP |
| POST | `/transactions/score` | Live score a single payload |
| GET | `/alerts` | Alerts with composite > 70 |
| GET | `/alerts/summary` | `total_alerts`, `by_tier`, `by_pattern` |
| GET | `/graph/account/{id}` | Graph risk summary for an account |
| GET | `/graph/neighbors/{id}` | 2-hop neighborhood for PyVis |

Example:

```bash
curl -H "X-API-Key: your-secret-api-key-here" http://localhost:8000/health
curl -H "X-API-Key: your-secret-api-key-here" http://localhost:8000/alerts/summary
curl -H "X-API-Key: your-secret-api-key-here" \
  "http://localhost:8000/transactions?tier=HIGH&limit=10"
```

---

## Dashboard

### Overview (`Home.py`)

- **Total Transactions** — CSV length loaded by API
- **Total Alerts** — composite > 70
- **Critical Alerts** — score > 90
- **Flagged Rate** — alerts / total %
- Pattern distribution donut (Plotly)
- Top 10 high-risk accounts (alert count, max score, patterns)
- Sidebar: auto-refresh every 30 seconds

### Transaction Explorer

- Multiselect tier / pattern, min-score slider
- Colored tiers (CRITICAL red → LOW green)
- Select a row → SHAP horizontal bar chart

### Graph Investigation

- Account ID search
- Risk card: `graph_risk`, flags, cycles, mule, PageRank
- PyVis HTML network (nodes by risk color, edges labeled with amount)

---

## Redis / Neo4j / Supabase

### Redis key schema

| Key | Meaning | TTL |
|-----|---------|-----|
| `tx_count:{account}:1h` | Velocity count | 1h |
| `tx_volume:{account}:1h` | Velocity volume | 1h |
| `unique_receivers:{account}:24h` | Fan-out set | 24h |
| `last_tx_ts:{account}` | Recency | — |
| `risk_score:{tx}` | Composite score | — |
| `shap:{tx}` | Top SHAP JSON | 24h |
| `alert:{tx}` | Alert payload if score > 70 | 24h |
| `graph_risk:{account}` | Cached graph score JSON | 1h |

### Neo4j

- Nodes: `(:Account {id})`
- Rels: `[:TRANSFER {amount, timestamp, transaction_id, bank, …}]`
- Analytics: cycles, mule, layering, PageRank

### Supabase (optional)

Migration: `backend/db/migrations/001_initial.sql`  
Tables: `transactions`, `alerts`, `shap_explanations`  
If `SUPABASE_DB_URL` is unset/placeholder, writes are skipped safely.

---

## Setup & run

### Prerequisites

- Docker Desktop
- Python 3.11+ (project also runs on newer 3.x locally)
- macOS: `brew install libomp` (required by XGBoost)
- `/etc/hosts` entry because Kafka advertises `kafka:9092`:

```text
127.0.0.1 kafka
```

### Install

```bash
cp -n .env.example .env
# edit API_KEY / connection URLs if needed
pip install -e ".[dev]"
```
### Full demo sequence

```bash
# 1) Infra
docker compose -f docker/docker-compose.yml up -d kafka redis neo4j

# 2) Data + model (once)
PYTHONPATH=backend python3 -m data_simulation.seed
PYTHONPATH=backend python3 -m ml.train --csv data/transactions.csv

# 3) Pipeline (3 terminals)
PYTHONPATH=backend python3 -m kafka.consumers.graph_sync
PYTHONPATH=backend python3 -m kafka.consumers.ml_scorer
PYTHONPATH=backend python3 -m kafka.producer --delay 0

# 4) API + UI
uvicorn api.main:app --port 8000 --app-dir backend
streamlit run dashboard/Home.py --server.port 8501
```

### Replay scoring (refresh Redis alerts/SHAP)

Stop `ml_scorer`, then:

```bash
docker exec -it docker-kafka-1 kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group ml_scorer --topic transactions.raw \
  --reset-offsets --to-earliest --execute

PYTHONPATH=backend python3 -m kafka.consumers.ml_scorer
```

### Useful URLs

| Service | URL |
|---------|-----|
| API docs | http://localhost:8000/docs |
| Streamlit | http://localhost:8501 |
| Neo4j Browser | http://localhost:7474 |

---

## Tests

```bash
PYTHONPATH=backend python3 -m pytest tests/unit/ -v
```

| File | Focus | Count |
|------|-------|-------|
| `test_simulation.py` | CSV labels, flagged rate, nulls, temporal span | 4 |
| `test_graph.py` | Cycles, mule, layering, GraphRiskScorer | 4 |
| `test_ml.py` | Features, composite, XGBoost load, temporal split | 4 |
| `test_api.py` | Health, 403 auth, list txs, live score, alerts summary | 5 |
| **Total** | | **17** |

Notes:

- Graph tests need Neo4j running
- API score test mocks graph cache / velocity for speed
- `httpx` is required for FastAPI `TestClient`

---

## Diagrams

See [`docs/diagrams.md`](docs/diagrams.md) for:

1. **System architecture** (Mermaid flowchart)
2. **Analyst user flow** (Overview → Explorer / Graph → triage)

Export PNG/SVG via [mermaid.live](https://mermaid.live).

---

## Interview talking points

- **Streaming vs batch:** Kafka decouples CSV ingestion from scoring; consumer groups + offset reset let you reprocess after model changes.
- **Hot vs cold path:** Redis for sub-ms investigation reads; Supabase hooks for durable analytics (optional).
- **Why graph + ML:** Tabular velocity catches structuring/dormant spikes; Neo4j catches cycles and mule fan-in that single-row features miss.
- **Composite design:** Fixed 60/40 blend keeps scoring interpretable in interviews; SHAP explains the ML half.
- **Temporal split:** AML episodes are time-spread so random shuffle leakage is avoided.
- **Ops realism:** API-key auth, bounded/fast graph path for consumer SLAs, GDS native projection (no deprecated cypher project), Neo4j Compose env isolation.
- **What you’d harden next:** Schema registry, DLQ, feature store, model registry, SSO, alert SLAs, stronger cold-path warehouse.

---

## Constraints & non-goals

- No LangChain, ChromaDB, Snowflake, or PDF report generation
- No `kafka-python` — **confluent-kafka** only
- Secrets only via `.env` (Neo4j service does not mount the full env file)
- Supabase is external (not in Docker Compose)
- Dashboard never talks to Redis/Neo4j directly — **FastAPI only**
- Demo-oriented: Redis is non-persistent; scale/HA/security hardening left as production follow-ups

---

## License / intent

Built as an interview portfolio system demonstrating end-to-end data engineering + ML + graph analytics + API + UI, not as a production compliance product.
