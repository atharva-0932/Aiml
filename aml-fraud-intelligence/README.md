# AML Fraud Intelligence

Production-grade Anti-Money Laundering detection platform for portfolio /
SWE–Data Engineering interviews. Detects suspicious transaction patterns
in real time with Kafka streaming, Redis velocity counters, Neo4j graph
analytics, and XGBoost scoring — results visualized in Streamlit.

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

Composite = 0.60 × XGBoost + 0.40 × Graph Risk
```

## Tech Stack

| Layer        | Technology                    |
|--------------|-------------------------------|
| API          | FastAPI + Uvicorn             |
| Event Bus    | Apache Kafka (KRaft)          |
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

## Build Status (all phases complete)

| Phase | Status |
|-------|--------|
| 1. Data simulation → `data/transactions.csv` | **Done** (~50k rows, ~6% labeled) |
| 2. Docker Compose (kafka, redis, neo4j) | **Done** |
| 3. Kafka producer + consumers | **Done** |
| 4. Neo4j graph analytics + GraphRiskScorer | **Done** |
| 5. XGBoost + SHAP + composite scoring | **Done** |
| 6. FastAPI (auth, transactions, alerts, graph) | **Done** |
| 7. Streamlit dashboard (3 pages) | **Done** |
| 8. Unit tests + cleanup | **Done** |

## Quick setup

```bash
cd aml-fraud-intelligence
cp -n .env.example .env
pip install -e ".[dev]"

# 1) Infra
docker compose -f docker/docker-compose.yml up -d kafka redis neo4j

# Host Kafka resolve (advertised as kafka:9092)
# add to /etc/hosts:  127.0.0.1 kafka

# 2) Seed + train (once)
PYTHONPATH=backend python3 -m data_simulation.seed
PYTHONPATH=backend python3 -m ml.train --csv data/transactions.csv

# 3) Pipeline (separate terminals)
PYTHONPATH=backend python3 -m kafka.consumers.graph_sync
PYTHONPATH=backend python3 -m kafka.consumers.ml_scorer
PYTHONPATH=backend python3 -m kafka.producer --delay 0

# 4) API + dashboard
uvicorn api.main:app --port 8000 --app-dir backend
streamlit run dashboard/Home.py --server.port 8501
```

Verify:

```bash
curl -H "X-API-Key: your-secret-api-key-here" http://localhost:8000/health
PYTHONPATH=backend python3 -m pytest tests/unit/ -v
```

## Tests

```bash
PYTHONPATH=backend python3 -m pytest tests/unit/ -v
```

Coverage: simulation CSV quality, graph Cypher/GDS, ML features/scorer, FastAPI TestClient.

## Interview talking points

- **Why Kafka?** Decouples ingestion from scoring; replay offsets to reprocess after model changes; partitions scale consumers.
- **Why Redis + Neo4j?** Redis for sub-ms velocity / alert cache (hot path); Neo4j for multi-hop AML topology (cycles, mule fan-in) that tabular features miss.
- **Composite score:** Blend supervised XGBoost (transaction features) with unsupervised graph risk so neither false-negatives alone; SHAP for analyst explainability.
- **Temporal train/test split:** AML episodes spread over a year so leakage from random splits is avoided — interviewers notice this.
- **Failure modes you fixed:** GDS native projection (no deprecated cypher project); bounded path queries / fast graph path so consumers don’t stall on dense graphs; API-key auth on every route including health.
- **What you’d productionize next:** Schema registry, DLQ, feature store, model registry/versioning, SSO, alert SLA metrics, and a real cold-path warehouse (Supabase hooks already stubbed).

## Constraints

- Python 3.11+
- No LangChain, ChromaDB, Snowflake, or PDF generation
- Secrets via `.env` only (Neo4j Compose service never mounts full `.env`)
- Supabase is external (not in Docker Compose)
- Kafka client: **confluent-kafka** only (not kafka-python)
