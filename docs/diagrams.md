# AML Fraud Intelligence — Diagrams

Paste either block into [mermaid.live](https://mermaid.live) to export PNG/SVG.

---

## 1. System Architecture

```mermaid
flowchart TB
  subgraph SOURCE["Data Source"]
    CSV["transactions.csv<br/>~50k rows · ~6% AML-labeled"]
  end

  subgraph INGEST["Ingestion"]
    PROD["Kafka Producer"]
  end

  subgraph BUS["Event Bus"]
    KAFKA["Apache Kafka KRaft<br/>topic: transactions.raw<br/>4 partitions"]
  end

  subgraph CONSUMERS["Consumers"]
    MLS["ml_scorer<br/>velocity · XGBoost · SHAP<br/>GraphRisk · composite"]
    GS["graph_sync<br/>batch MERGE → Neo4j"]
  end

  subgraph SCORE["Scoring Logic"]
    COMP["Composite =<br/>0.60 × XGBoost + 0.40 × Graph Risk"]
  end

  subgraph STORE["Storage"]
    REDIS["Redis 7 hot cache<br/>risk_score · shap · alert<br/>velocity · graph_risk"]
    NEO["Neo4j 5 + GDS<br/>cycles · mule · PageRank"]
    SUP["Supabase Postgres<br/>cold path · optional"]
  end

  subgraph API["API Layer"]
    FAST["FastAPI :8000<br/>X-API-Key auth<br/>/transactions · /alerts · /graph"]
  end

  subgraph UI["Presentation"]
    ST["Streamlit :8501<br/>Overview · Explorer · Graph"]
  end

  CSV --> PROD --> KAFKA
  KAFKA --> MLS
  KAFKA --> GS
  MLS --> COMP
  COMP --> REDIS
  MLS -.-> SUP
  GS --> NEO
  MLS --> NEO
  REDIS --> FAST
  NEO --> FAST
  FAST -->|"X-API-Key"| ST

  classDef kafka fill:#fff3e0,stroke:#ef6c00,color:#000
  classDef redis fill:#ffebee,stroke:#c62828,color:#000
  classDef neo fill:#e8f5e9,stroke:#2e7d32,color:#000
  classDef api fill:#e3f2fd,stroke:#1565c0,color:#000
  classDef ui fill:#f3e5f5,stroke:#6a1b9a,color:#000
  classDef score fill:#fffde7,stroke:#f9a825,color:#000

  class KAFKA,PROD kafka
  class REDIS redis
  class NEO neo
  class FAST api
  class ST ui
  class COMP,MLS score
```

**Risk tiers:** LOW &lt; 30 · MEDIUM 30–70 · HIGH 70–90 · CRITICAL &gt; 90

---

## 2. Analyst User Flow

```mermaid
flowchart TD
  START([Analyst opens Streamlit :8501]) --> OVERVIEW

  subgraph OVERVIEW["Overview"]
    KPI["KPI cards<br/>Total tx · Alerts · Critical · Flagged %"]
    DONUT["Pattern donut<br/>6 AML labels"]
    TOP10["Top 10 high-risk accounts"]
    REFRESH["Optional auto-refresh 30s"]
    KPI --> DONUT --> TOP10 --> REFRESH
  end

  OVERVIEW --> CHOICE{Investigate how?}

  CHOICE -->|Transaction| EXPLORER
  CHOICE -->|Account network| GRAPH

  subgraph EXPLORER["Transaction Explorer"]
    FILT["Filter: tier · pattern · min score"]
    TABLE["Review scored transaction table"]
    PICK["Select transaction"]
    SHAP["GET /transactions/id<br/>SHAP top-5 bar chart"]
    WHY["Understand why score is high"]
    FILT --> TABLE --> PICK --> SHAP --> WHY
  end

  subgraph GRAPH["Graph Investigation"]
    PASTE["Paste Account ID"]
    RISK["GET /graph/account/id<br/>graph_risk · flags · mule · PageRank"]
    NET["GET /graph/neighbors/id<br/>PyVis 2-hop network"]
    TRACE["Trace cycles / mule / multi-hop"]
    PASTE --> RISK --> NET --> TRACE
  end

  WHY --> ENDNODE([Triage HIGH / CRITICAL alert])
  TRACE --> ENDNODE

  subgraph PIPELINE["Background pipeline"]
    direction LR
    P1["Producer → Kafka"] --> P2["ml_scorer → Redis"]
    P1 --> P3["graph_sync → Neo4j"]
    P2 --> P4["FastAPI serves UI"]
    P3 --> P4
  end

  classDef ui fill:#f3e5f5,stroke:#6a1b9a,color:#000
  classDef api fill:#e3f2fd,stroke:#1565c0,color:#000
  classDef bg fill:#f5f5f5,stroke:#757575,color:#000
  classDef endc fill:#e8f5e9,stroke:#2e7d32,color:#000

  class OVERVIEW,EXPLORER,GRAPH ui
  class SHAP,RISK,NET api
  class PIPELINE,P1,P2,P3,P4 bg
  class ENDNODE endc
```
