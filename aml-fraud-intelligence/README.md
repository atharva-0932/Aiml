# AML Fraud Intelligence Platform

Production-grade AI-powered Anti-Money Laundering detection platform built with a Lambda Architecture for sub-100ms transaction scoring.

## Architecture

```
Transaction Ingest (FastAPI)
    │
    ├──► Kafka (transactions.raw)
    │         ├── ml_scorer consumer  → Redis cache + transactions.scored/flagged
    │         ├── graph_sync consumer → Neo4j
    │         └── alert_dispatcher    → Redis Pub/Sub → Dashboard SSE
    │
    └──► Redis velocity INCR (sub-1ms)

Cold Path:
    Snowflake ← snowflake_writer consumer (batch COPY INTO every 30s)
    Snowpark feature engineering → XGBoost + Isolation Forest training
```

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Event Streaming | Apache Kafka (KRaft, no Zookeeper) |
| Hot Path Cache | Redis 7 (hiredis) |
| Graph Database | Neo4j 5 + Graph Data Science |
| Analytical DWH | Snowflake (Snowpark feature engineering) |
| ML | XGBoost, Isolation Forest, SHAP |
| GenAI | LangChain + Gemini 1.5 Pro / GPT-4o + ChromaDB RAG |
| Reports | WeasyPrint + Jinja2 PDF |
| Dashboard | Streamlit + Plotly + PyVis |
| Deployment | Docker Compose |

## Quick Start

### 1. Clone and configure

```bash
cd aml-fraud-intelligence
cp .env.example .env
# Fill in SNOWFLAKE_* and GEMINI_API_KEY in .env
```

### 2. Start infrastructure

```bash
cd docker
docker compose up redis kafka neo4j -d
```

### 3. Run Snowflake migrations

```bash
pip install schemachange
schemachange deploy \
  -f backend/db/snowflake/migrations \
  --snowflake-account $SNOWFLAKE_ACCOUNT \
  --snowflake-user $SNOWFLAKE_USER \
  --snowflake-password $SNOWFLAKE_PASSWORD \
  --snowflake-database AML_DB \
  --snowflake-schema PUBLIC \
  --snowflake-warehouse COMPUTE_WH
```

### 4. Seed synthetic data (50k transactions)

```bash
cd backend
PYTHONPATH=. python -m data_simulation.seed
# Use --no-snowflake to output CSV only without loading to Snowflake
```

### 5. Build Neo4j graph

```python
import asyncio
from graph.graph_builder import build_full_graph
asyncio.run(build_full_graph())
```

### 6. Train ML models

```bash
# Option A: from Snowpark (requires Snowflake)
PYTHONPATH=backend python -m ml.train

# Option B: from CSV (offline)
PYTHONPATH=backend python -m ml.train --csv data/transactions.csv
```

### 7. Start all services

```bash
cd docker
docker compose up --build
```

**Services:**
- FastAPI backend: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Streamlit dashboard: http://localhost:8501
- Neo4j browser: http://localhost:7474

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/transactions/ingest` | Ingest batch (publishes to Kafka) |
| GET | `/api/v1/transactions/flagged` | Paginated flagged transactions |
| GET | `/api/v1/accounts/{id}/risk-profile` | Risk profile (Redis-first) |
| GET | `/api/v1/accounts/{id}/graph-neighbors` | 2-hop Neo4j neighbors |
| POST | `/api/v1/risk/score` | Score a transaction (hot path) |
| GET | `/api/v1/graph/cycles` | Circular flow detection |
| GET | `/api/v1/graph/mules` | Mule account candidates |
| GET | `/api/v1/risk/top-flagged` | Redis leaderboard top-N |
| GET | `/api/v1/alerts/stream` | SSE real-time alert stream |
| POST | `/api/v1/copilot/chat` | Streaming GenAI Q&A |
| POST | `/api/v1/copilot/explain/{id}` | Explain why account was flagged |
| POST | `/api/v1/copilot/sar/{id}` | Generate SAR draft |
| POST | `/api/v1/reports/generate` | Download PDF report |

## AML Patterns Simulated

| Pattern | Count | Description |
|---|---|---|
| Structuring | ~400 | Transactions just below $10,000 CTR threshold |
| Layering | ~480 | 4–7 hop cross-bank transfer chains |
| Circular Flow | ~240 | A→B→C→A fund cycles |
| Mule Account | ~520 | Fan-in → consolidation patterns |
| Dormant Activation | ~150 | 180+ day silent → sudden activity |
| Rapid Multi-hop | ~360 | 5+ hops within 2 hours |

## Running Tests

```bash
pip install pytest pytest-asyncio
PYTHONPATH=backend pytest tests/unit/ -v
```

## Deployment

### Railway (quick)
1. Push to GitHub
2. Create Railway project, add Redis + Neo4j services
3. Set Snowflake env vars
4. Deploy backend and dashboard services

### AWS (production)
- ECS Fargate (backend + consumers + dashboard)
- MSK (managed Kafka)
- ElastiCache Redis
- Neo4j AuraDB
- Snowflake cloud

## Resume Talking Points

- Lambda Architecture: Kafka hot path (<50ms scoring) + Snowflake cold path
- Redis feature store: velocity INCR counters for real-time ML features
- Neo4j GDS: PageRank, cycle detection, mule identification across 50k+ transactions
- Composite risk scorer: 0.4×XGBoost + 0.35×IsolationForest + 0.25×GraphRisk
- LangChain RAG pipeline with ChromaDB for automated SAR generation
- Snowpark DataFrames for in-warehouse batch feature engineering
- Snowflake Time Travel for AML audit trail compliance
