# 🔐 AI-Powered AML & Fraud Intelligence Platform

> A production-grade Anti-Money Laundering detection system simulating how banks catch suspicious fund movement, money laundering rings, mule accounts, and layering schemes — using graph analytics, machine learning, and a GenAI investigator copilot.

![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi)
![Kafka](https://img.shields.io/badge/Apache_Kafka-3.7-231F20?style=flat-square&logo=apachekafka)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis)
![Neo4j](https://img.shields.io/badge/Neo4j-5.18-008CC1?style=flat-square&logo=neo4j)
![Snowflake](https://img.shields.io/badge/Snowflake-DWH-29B5E8?style=flat-square&logo=snowflake)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35-FF4B4B?style=flat-square&logo=streamlit)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker)
![LangChain](https://img.shields.io/badge/LangChain-RAG-1C3C3C?style=flat-square)
![Tests](https://img.shields.io/badge/Tests-14%20passing-brightgreen?style=flat-square)

---

## What This Detects

| AML Pattern | How |
|---|---|
| **Structuring** | Multiple payments just below the $10,000 CTR reporting threshold |
| **Layering** | 4–8 hop cross-bank transfer chains to obscure fund origin |
| **Circular Fund Flow** | A → B → C → A money loops within 72 hours |
| **Mule Accounts** | Fan-in from 10+ sources, 92% forwarded to single destination |
| **Dormant Activation** | Account silent 180+ days, then sudden high-value activity |
| **Rapid Multi-hop** | 5+ transfers across 5+ accounts within 2 hours |

---

## Architecture — Lambda Design

```
Transaction Ingest (FastAPI)
    │
    ├──► Kafka (transactions.raw)  ◄── HOT PATH (<50ms)
    │         ├── ml_scorer     → Redis score cache + routed to scored/flagged topic
    │         ├── graph_sync    → Neo4j relationship write (async)
    │         └── alert_dispatcher → Redis Pub/Sub → live dashboard SSE
    │
    └──► Redis velocity INCR    ← real-time feature store, sub-1ms

COLD PATH (analytical):
    Kafka (transactions.scored/flagged)
        └──► snowflake_writer consumer
                └──► Snowflake DWH  ←→  Snowpark feature engineering
                                              └──► XGBoost + Isolation Forest training
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| API | FastAPI + Uvicorn | 12 REST endpoints, SSE alert stream |
| Event Bus | Apache Kafka 3.7 (KRaft) | Transaction event streaming, 4 consumer groups |
| Hot Cache | Redis 7 (hiredis) | Sub-1ms velocity counters + risk score cache |
| Graph DB | Neo4j 5 + GDS plugin | PageRank, cycle detection, mule scoring |
| Data Warehouse | Snowflake + Snowpark | Analytical cold path, Time Travel audit trail |
| ML | XGBoost + Isolation Forest + SHAP | Composite 0–100 risk scorer with explainability |
| GenAI | LangChain + Gemini 1.5 Pro + ChromaDB | RAG-powered copilot, automated SAR generation |
| Reports | WeasyPrint + Jinja2 | PDF evidence reports for FIU submission |
| Dashboard | Streamlit + Plotly + PyVis | 7-page investigator interface |
| Deployment | Docker Compose | One-command local setup |

---

## Composite Risk Score

```
Composite = 0.40 × XGBoost  +  0.35 × Isolation Forest  +  0.25 × Graph Risk

Tiers:  LOW < 30  |  MEDIUM 30–70  |  HIGH 70–90  |  CRITICAL > 90
```

---

## Modules

```
aml-fraud-intelligence/
├── backend/
│   ├── api/              FastAPI — 12 endpoints, API key auth, SSE
│   ├── kafka/            Producer + 4 consumers (ml_scorer, graph_sync, alert_dispatcher, snowflake_writer)
│   ├── ml/               IsolationForest + XGBoost + SHAP + CompositeRiskScorer
│   ├── graph/            Cycle, layering, mule detection + Neo4j Cypher queries
│   ├── genai/            LangChain chains, ChromaDB RAG, SAR generator
│   ├── reports/          WeasyPrint PDF + Jinja2 HTML template
│   ├── db/               Snowflake (Snowpark), Redis (hiredis), Neo4j (async driver)
│   └── data_simulation/  6 AML pattern generators, full seeder (50k transactions)
├── dashboard/
│   └── pages/            7 Streamlit pages — Overview, Explorer, Graph, Heatmaps, Timeline, Copilot, Reports
├── docker/               docker-compose.yml + Dockerfiles
└── tests/                14 unit tests (all passing)
```

---

## Quick Start

```bash
# 1. Enter the project
cd aml-fraud-intelligence

# 2. Configure credentials
cp .env.example .env
# Fill in SNOWFLAKE_* and GEMINI_API_KEY

# 3. Start infrastructure (Redis + Kafka + Neo4j)
cd docker && docker compose up redis kafka neo4j -d

# 4. Seed 50k synthetic transactions (no Snowflake needed)
cd .. && PYTHONPATH=backend python3 -m data_simulation.seed --no-snowflake

# 5. Train ML models from seeded CSV
PYTHONPATH=backend python3 -m ml.train --csv data/transactions.csv

# 6. Launch everything
cd docker && docker compose up --build
```

| Service | URL |
|---|---|
| FastAPI backend | http://localhost:8000 |
| Interactive API docs | http://localhost:8000/docs |
| Streamlit dashboard | http://localhost:8501 |
| Neo4j browser | http://localhost:7474 |

---

## Dashboard Pages

| Page | What You See |
|---|---|
| Overview | KPI cards, risk distribution donut, live top-risk leaderboard |
| Transaction Explorer | Filterable table of all 2,014 flagged transactions |
| Graph Investigation | Interactive PyVis network — click any account to see 2-hop connections |
| Risk Heatmaps | Hour × day heatmap + global geo scatter of flagged transactions |
| Timeline Replay | Animated Plotly fund flow replay by AML pattern |
| Copilot Chat | LangChain RAG assistant — ask "Why was account X flagged?" |
| Evidence Reports | Download PDF investigation report + SAR draft for any account |

---

## Running Tests

```bash
PYTHONPATH=aml-fraud-intelligence/backend python3 -m pytest aml-fraud-intelligence/tests/unit/ -v
# 14 passed
```

---

## Resume Talking Points

- **Lambda Architecture** — Kafka hot path achieving <50ms transaction scoring; Snowflake cold path for batch analytics
- **Redis feature store** — real-time velocity tracking with INCR + EXPIRE sliding window counters (sub-1ms)
- **Neo4j GDS** — PageRank centrality, variable-length cycle detection, mule fan-in/fan-out scoring across 50k+ transactions
- **Composite scorer** — 0.4×XGBoost + 0.35×IsolationForest + 0.25×GraphRisk with SHAP explainability per prediction
- **LangChain RAG** — ChromaDB vector store over transaction embeddings, structured SAR output via Pydantic
- **Snowpark** — pushed window function feature engineering (velocity, rolling z-score) into Snowflake warehouse
- **Snowflake Time Travel** — full AML audit trail, any table state recoverable up to 90 days
- **4 Kafka consumer groups** — ml_scorer, graph_sync, alert_dispatcher, snowflake_writer — independent parallel processing

---

## Target Roles

Designed to demonstrate skills for:
- Fintech / Risk Analytics Engineering
- Data Science & ML Engineering
- AI/ML Internships
- Quantitative Technology roles at JPMorgan Chase, Goldman Sachs, UBS, Morgan Stanley
