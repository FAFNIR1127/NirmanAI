# Documentation: Phase 4 — Data Intelligence Layer

This document describes the architectural design, service abstractions, REST API reference, numerical verification protocols, and data flow for **Phase 4 of Project Nirman (PAIMANA AI Infrastructure Monitoring Platform)**.

---

## 1. Executive Strategy & Purpose

Before integrating large language models (LLMs) or retrieval-augmented generation (RAG), **Project Nirman** relies on a controlled, deterministic **Data Intelligence Layer**.

Rather than permitting an LLM to generate arbitrary SQL queries over the production database, the Data Intelligence Layer exposes structured, parameterized Python services and REST API endpoints. This guarantees:
1. **100% Numerical Accuracy**: Aggregations are calculated directly in PostgreSQL using B-Tree indexed SQL queries.
2. **Security & Parameterization**: Prevents SQL injection and hallucinated query execution.
3. **High Performance**: Pre-calculated risk scores and B-Tree indexes serve query responses in under 15ms.

---

## 2. Architecture & Data Flow

```
                         USER / LLM QUERY ROUTER
                                   │
                                   ▼
                       FastAPI REST API Server
                                   │
            ┌──────────────────────┼──────────────────────┐
            ▼                      ▼                      ▼
  Data Query Service       Analytics Service      Risk Engine Service
  (query_service.py)      (analytics_service.py)  (risk_engine.py)
   ├── search_projects()   ├── exec_summary()     ├── predict_risk()
   ├── filter_projects()   ├── risk_dist()        ├── risk_drivers()
   └── compare_projects()  └── state/agency_stats()└── protective_factors()
            │                      │                      │
            └──────────────────────┼──────────────────────┘
                                   ▼
                     PostgreSQL Database (`nirman_db`)
                      ├── projects (3,589 Master Rows)
                      ├── project_observations (13,098 Rows)
                      ├── project_features (Engineered Ratios)
                      └── risk_scores (Calibrated Scores & SHAP)
```

---

## 3. Service Layer Reference

### A. Data Query Service (`backend/app/services/query_service.py`)
- `search_projects(query_str, limit)`: Performs case-insensitive wildcard search across `project_code` and `project_name`.
- `filter_projects(state, agency, risk_category, min_cost, max_cost, limit)`: Evaluates multi-attribute filter criteria.
- `compare_projects(project_codes)`: Retrieves side-by-side comparative metrics for a list of project codes.

### B. Analytics Service (`backend/app/services/analytics_service.py`)
- `get_executive_summary()`: Computes total master projects, live 2026 projects, total original cost, total anticipated cost, cost overrun %, and risk level counts.
- `get_risk_distribution()`: Calculates project counts, average risk score, and total anticipated cost across `LOW`, `MODERATE`, `HIGH`, and `CRITICAL` risk categories.
- `get_state_statistics(limit)`: Aggregates project counts, total costs, average risk scores, and critical project counts by Indian State/UT.
- `get_agency_statistics(limit)`: Aggregates project counts, total costs, cost overrun %, and critical project counts by Implementing Agency.
- `get_cost_delay_analytics()`: Computes cost expansion ratio distributions and schedule delay statistics.

### C. Risk Engine Service (`backend/app/services/risk_engine.py`)
- `get_project_risk_assessment(project_code)`: Loads calibrated XGBoost predictions, 0–100 Nirman Risk Score, cost/schedule indices, TreeSHAP risk drivers (+ impact), and protective factors (- impact).

---

## 4. REST API Reference

| Method | Endpoint | Description | Sample Query / Response |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | API & Model Health Check | `{"status": "healthy", "model_version": "risk_engine_v1"}` |
| `GET` | `/api/projects` | List Monitored Projects | `?limit=100` |
| `GET` | `/api/projects/search` | Search Projects | `?q=BHAVINI` |
| `GET` | `/api/projects/filter` | Multi-Attribute Filter | `?state=TAMIL%20NADU&risk_category=CRITICAL` |
| `GET` | `/api/projects/compare` | Side-by-Side Comparison | `?codes=020100044,N04000073` |
| `GET` | `/api/projects/{code}` | Project History & Metadata | `/api/projects/020100044` |
| `GET` | `/api/risk/predict/{code}` | Live Risk & TreeSHAP | `/api/risk/predict/020100044` |
| `GET` | `/api/analytics/summary` | Executive Portfolio Summary | Total cost, overrun %, risk counts |
| `GET` | `/api/analytics/risk-distribution` | Risk Category Breakdown | Low, Moderate, High, Critical counts & costs |
| `GET` | `/api/analytics/by-state` | State-level Aggregations | Project counts and risk scores per state |
| `GET` | `/api/analytics/by-agency` | Agency-level Aggregations | Project counts and overrun % per agency |
| `GET` | `/api/analytics/cost-delay-stats` | Cost Overrun & Delay Stats | Expansion ratios and delay durations |

---

## 5. Verification & Accuracy Audit Results

Executed `scripts/validation/verify_data_intelligence.py` against live PostgreSQL (`nirman_db`):
- **Database Row Counts**: Master Projects = 3,589 | Observations = 13,098 | Risk Scores = 13,098 (100% Match).
- **Executive Summary**: Total Original Cost = ₹4,843,971.35 Crore | API vs PostgreSQL Match = **100.0%**.
- **Risk Distribution Match**: CRITICAL (2,263), HIGH (1,124), MODERATE (4,233), LOW (5,478) (100% Match).
- **Edge Cases**: Non-existent projects return clean `404 Not Found`; empty searches return `[]` (`HTTP 200`).
