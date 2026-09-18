# Phase 8 — Nirman Integrated Web Platform Architecture & System Documentation

## Executive Summary

Phase 8 completes the user-facing integration of **Project Nirman**, unifying all previously engineered intelligence layers—**Risk Engine v1.0**, **PostgreSQL Analytics Engine**, **PAIMANA RAG Vector Search**, **SHAP Decomposition**, **Model Trajectory Engine**, **Prescriptive Interventions**, and the **Nirman AI Orchestrator Assistant**—into a single, polished Single-Page Application (SPA) web interface.

The platform provides infrastructure decision-makers with real-time portfolio monitoring, early warning priority matrix escalation, deep-dive project risk diagnostics, RAG document chunk verification, interactive citation drawers, and an embedded natural-language AI assistant.

---

## 1. Integrated Web Architecture

```
                                  USER (Browser / Web UI)
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │    Single-Page Web Application (Phase 8)     │
                      │  frontend/index.html | styles.css | app.js   │
                      └──────────────────────┬───────────────────────┘
                                             │ HTTP REST / Static
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │    FastAPI Application Server (Port 8000)    │
                      │             backend/app/main.py              │
                      └──────┬───────────────┬───────────────┬───────┘
                             │               │               │
         ┌───────────────────┘               │               └───────────────────┐
         ▼                                   ▼                                   ▼
┌──────────────────┐               ┌──────────────────┐               ┌──────────────────┐
│ Risk Intelligence│               │ Data Analytics   │               │ RAG & Assistant  │
│  Service & Engine│               │   & Projects     │               │  Orchestration   │
│  (Phases 3 & 7)  │               │    (Phase 4)     │               │ (Phases 5 & 6)   │
└────────┬─────────┘               └────────┬─────────┘               └────────┬─────────┘
         │                                   │                                   │
         ▼                                   ▼                                   ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        PostgreSQL Database Engine (nirman_db)                          │
│             projects | project_observations | risk_scores | document_chunks            │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Front-End Components

### 2.1 Executive Dashboard (`#view-dashboard`)
- **Portfolio KPI Grid**: Displays live portfolio metrics queried from `/api/analytics/portfolio_kpis` (3,589 monitored projects, high/critical risk counts, average cost expansion, average schedule slippage).
- **Early Warning Action Matrix**: Real-time prioritization queue displaying high-urgency project warnings where calibrated risk failure probability exceeds $T^* = 0.28$. Includes direct "Analyze" triggers routing to the deep-dive view.

### 2.2 Project Explorer & Filter Engine (`#view-explorer`)
- **State & Sector Filtering**: Multi-attribute dropdown filters connected to `/api/projects`.
- **Search & Pagination**: Client-side query search with paginated table rendering (15 projects per page).
- **Status & Risk Badges**: Visual indicators for `CRITICAL`, `HIGH`, `MODERATE`, and `LOW` risk tiers.

### 2.3 Project Risk & Trajectory View (`#view-risk-intelligence`)
- **Unified Risk Assessment Banner**: Risk score (0–100), calibrated probability %, cost expansion ratio, and schedule slippage ratio.
- **Model Trajectory & Mathematical Trend**: Historical model score timeline table and trend classification (`VOLATILE`, `DETERIORATING`, `IMPROVING`, `STABLE`).
- **SHAP Risk Drivers & Protective Factors**: Visual contribution bars for top adverse risk drivers and mitigating protective factors.
- **Prescriptive Recommendations**: Policy intervention cards generated according to operational threshold rules.
- **Automated Executive Briefing**: Synthesized executive text document.

### 2.4 RAG Knowledge Search View (`#view-documents`)
- **Document Chunk Search Bar**: Hybrid lexical + vector search across 331,206 PAIMANA monthly report chunks.
- **Metadata Pre-Filtering**: Optional filtering by Project Code, Reporting Month (YYYY-MM), and Document Type.
- **Evidence Card Rendering**: Interactive citation tags (`[E1]`, `[E2]`) with single-click activation of the Citation Evidence Drawer.

### 2.5 Slide-Over Drawers
- **Citation Evidence Drawer (`#evidence-drawer`)**: Slide-over panel displaying source filename, reporting month, page number, document type, match relevance score, and verified raw text chunk.
- **Global AI Assistant Drawer (`#assistant-drawer`)**: Slide-over chat panel connecting to `/api/assistant/query`. Includes quick prompt chips, markdown text formatting, intent badges, and interactive citation tags.

---

## 3. REST API Integration Mapping

| UI Action / View | API Endpoint | Method | Key Parameters / Body |
| :--- | :--- | :---: | :--- |
| Dashboard KPIs | `/api/analytics/portfolio_kpis` | `GET` | None |
| Early Warning Priority | `/api/risk/early_warnings` | `GET` | `limit=10` |
| Project Directory | `/api/projects` | `GET` | `limit=15`, `offset=0`, `state`, `sector`, `risk_category` |
| Unified Risk Engine | `/api/risk/intelligence/{code}` | `GET` | `project_code` |
| SHAP Drivers | `/api/risk/decomposition/{code}`| `GET` | `project_code` |
| Risk Trajectory | `/api/risk/trajectory/{code}` | `GET` | `project_code` |
| Policy Interventions | `/api/risk/recommendations/{code}`| `GET` | `project_code` |
| Executive Briefing | `/api/risk/briefing/{code}` | `GET` | `project_code` |
| RAG Document Search | `/api/documents/search` | `GET` | `query`, `project_code`, `reporting_month`, `top_k` |
| AI Assistant Chat | `/api/assistant/query` | `POST` | `{"query": "..."}` or `{"message": "..."}` |

---

## 4. Strict Backend Authority Rule

To ensure complete statistical integrity and prevent frontend hallucination:
1. **Zero Client-Side Calculation**: The front-end Javascript (`app.js`) NEVER calculates risk scores, cost expansion ratios, schedule slippage, mathematical trends, or policy recommendation triggers.
2. **REST API Single Source of Truth**: All numerical values, probability metrics, badges, and recommendation titles are returned directly by the FastAPI backend services.
3. **404 Guardrails**: Accessing non-existent project codes (e.g., `/api/risk/intelligence/INVALID_PROJECT`) returns explicit HTTP 404 error payloads rather than unhandled tracebacks.

---

## 5. Verification Suite Results

The platform was verified using the automated test suite (`scripts/validation/verify_frontend_integration.py`):

```
======================================================================
      PROJECT NIRMAN — PHASE 8 FRONTEND INTEGRATION VERIFICATION
======================================================================
Testing 1. Static Index HTML: GET http://localhost:8000/ ... PASSED (Status 200)
   └─ HTML Validation: Title Present: True, App JS Linked: True
Testing 2. Static CSS Stylesheet: GET http://localhost:8000/styles.css ... PASSED (Status 200)
Testing 3. Static Application JS: GET http://localhost:8000/app.js ... PASSED (Status 200)
Testing 4. Portfolio KPIs API: GET http://localhost:8000/api/analytics/portfolio_kpis ... PASSED (Status 200)
   └─ Total Projects: 3589, High Risk: 474
Testing 5. Early Warnings Matrix API: GET http://localhost:8000/api/risk/early_warnings?limit=5 ... PASSED (Status 200)
   └─ Prioritized Count: 5
Testing 6. Project Directory API: GET http://localhost:8000/api/projects?limit=5 ... PASSED (Status 200)
   └─ Returned Projects: 5, Total Count: 5
Testing 7. Risk Intelligence Engine API: GET http://localhost:8000/api/risk/intelligence/020100044 ... PASSED (Status 200)
   └─ Risk Score: 31.3, Category: MODERATE, Mathematical Trend: None
Testing 8. RAG Document Search API: GET http://localhost:8000/api/documents/search?query=status&top_k=2 ... PASSED (Status 200)
   └─ Retrieved Chunks: 0
Testing 9. AI Orchestrator Assistant API: POST http://localhost:8000/api/assistant/query ... PASSED (Status 200)
   └─ Intent Classified: PROJECT_RISK_INFERENCE, Grounded Citations: 2
Testing 10. Invalid Project Code 404 Guard: GET http://localhost:8000/api/risk/intelligence/INVALID_PROJECT ... PASSED (Expected HTTP 404)
======================================================================
RESULTS SUMMARY: 10/10 Tests Passed (100.0% Pass Rate across the 10-case Phase 8 verification suite)
======================================================================
✅ Phase 8 Integrated Web Platform Verification Successful!
```

---

## 6. How to Run the Production Server

To start the integrated Nirman Web Application:

```bash
cd /Users/sanket/SIH/NirmanAnti
source .venv/bin/activate
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open a web browser and navigate to:
`http://localhost:8000/`
