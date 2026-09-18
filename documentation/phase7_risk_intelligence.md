# Phase 7 — AI + Risk Intelligence Integration Layer Documentation

## 1. System Overview & Architecture

Phase 7 of **Project Nirman (PAIMANA AI Infrastructure Monitoring Platform)** elevates the core risk modeling and document retrieval infrastructure into a **Prescriptive Risk Intelligence & Decision Support Engine**.

Instead of merely returning raw risk probability scores, Phase 7 interprets model outputs, decomposes SHAP risk drivers, calculates model-versioned risk trajectories over time, enforces policy recommendation rules, prioritizes urgent early warnings, and synthesizes executive monitoring briefs.

```
                       NIRMAN AI ASSISTANT
                               │
                               ▼
                        QUERY ROUTER v2
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
       ▼                       ▼                       ▼
  Structured Data             RAG                 Risk Engine
       │                       │                       │
       │                       │              ┌────────┴────────┐
       │                       │              │                 │
       │                       │              ▼                 ▼
       │                       │        Risk Probability      SHAP
       │                       │              │                 │
       └───────────────────────┼──────────────┴─────────────────┘
                               ▼
                    RISK INTELLIGENCE LAYER
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
     Decomposition         Trajectory          Recommendations
          │                    │                    │
          └────────────────────┼────────────────────┘
                               ▼
                       Early-Warning Engine
                               │
                               ▼
                     Evidence / Context Builder
                               │
                               ▼
                              LLM
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
        Human-readable answer          Verified citations
```

---

## 2. Technical Component Specifications

### 2.1 Risk Driver Decomposition (`risk_decomposition_service.py`)
- Decomposes raw XGBoost SHAP outputs into `Primary Risk Drivers` (+ points added) and `Protective Factors` (- points added).
- **SHAP Representation Rule**: Explicitly documents and presents SHAP points as relative feature influence indicators rather than literal additions to the 0–100 probability score.

### 2.2 Model-Versioned Risk Trajectory & Mathematical Trend Detection (`risk_trajectory_service.py`)
- Evaluates historical `risk_scores` observations across reporting months (2018–2026).
- **Mathematical Trend Definitions** (computed over recent 6 periods):
  - `INSUFFICIENT_HISTORY`: `total_observations < 3` (prevents misleading trend claims on sparse history).
  - `DETERIORATING`: Moving average slope $m > 1.5$ points/month.
  - `IMPROVING`: Slope $m < -1.5$ points/month.
  - `VOLATILE`: Risk score variance $\sigma^2 > 25.0$.
  - `STABLE`: $|m| \le 1.5$ and $\sigma^2 \le 25.0$.

### 2.3 Configurable Policy Recommendation Engine (`recommendation_engine.py`)
- Configurable Monitoring Policy Parameters:
  ```python
  RECOMMENDATION_THRESHOLDS = {
      "schedule_slippage_threshold": 0.20,     # > 20% delay ratio (2.4+ months/year)
      "cost_expansion_threshold": 1.25,        # > 1.25x original cost
      "milestone_velocity_threshold": 0.50     # < 50% milestone progress velocity
  }
  ```
- Machine-Readable Recommendation Output:
  ```json
  {
    "recommendation_code": "SCHEDULE_ACCELERATION_REVIEW",
    "triggered": true,
    "severity": "HIGH",
    "trigger_conditions": [
      {"feature": "schedule_slippage_ratio", "value": 0.31, "threshold": 0.20}
    ],
    "rationale": "Observed schedule delay (0.31) exceeds configured policy threshold (0.20).",
    "recommended_review": "Review schedule recovery options and milestone dependencies.",
    "policy_disclaimer": "Recommendations are decision support advisories grounded in configured monitoring policy thresholds."
  }
  ```

### 2.4 Explainable Early-Warning Prioritization (`early_warning_service.py`)
- Scans portfolio for projects crossing operational cutoff ($T^* = 0.28$ or `risk_score >= 28.0`).
- Separates Risk Score from Urgency Rationale, assigning urgency rank and human-readable explanation strings (`"Critical risk score (86.0/100) | High cost risk index | High schedule delay index"`).

### 2.5 Executive Monitoring Briefing Service (`executive_briefing_service.py`)
- **Strict Evidence Separation**:
  - Authoritative Quantitative KPIs $\rightarrow$ PostgreSQL direct SQL queries (`SUM()`, `COUNT()`).
  - Documentary Context $\rightarrow$ PAIMANA RAG document search.
  - LLM $\rightarrow$ Synthesizes grounded executive overview without hallucinating numbers.

---

## 3. Automated Benchmark Verification Results (`verify_risk_intelligence.py`)

Executing `python scripts/validation/verify_risk_intelligence.py`:

| Test Case | Description / Benchmark | Result | Status |
| :--- | :--- | :--- | :--- |
| **Test 1** | Risk Driver Decomposition (`020100044`) | 3 Drivers, 3 Protective Factors | ✅ **PASSED** |
| **Test 2** | SHAP Relative Influence Caveat Note | Explicit Caveat Statement Verified | ✅ **PASSED** |
| **Test 3** | Model-Versioned Risk Trajectory | 7 Observations under `risk_engine_v1` | ✅ **PASSED** |
| **Test 4** | Mathematical Trend Classification | Slope -2.66 $\rightarrow$ Classified as `VOLATILE` | ✅ **PASSED** |
| **Test 5** | Sparse History Handling Guard | Non-existent Project $\rightarrow$ Clean `None` | ✅ **PASSED** |
| **Test 6** | Prescriptive Policy Recommendation Trigger | Code `MILESTONE_VELOCITY_TRACKING` | ✅ **PASSED** |
| **Test 7** | Recommendation Schema & Policy Disclaimer | Machine-Readable JSON + Disclaimer | ✅ **PASSED** |
| **Test 8** | Early-Warning Threshold Cutoff ($T^*=0.28$) | 10 Projects Cutoff Verified | ✅ **PASSED** |
| **Test 9** | Early-Warning Urgency Ranking & Rationale | Rank 1 Rationale String Verified | ✅ **PASSED** |
| **Test 10** | Executive Briefing Evidence Separation | KPIs: 3,589 Projects \| RAG Chunks: 3 | ✅ **PASSED** |
| **Test 11** | Assistant Trajectory Query (`RISK_TRAJECTORY_TREND`) | Tools: `['get_project_risk_trajectory']` | ✅ **PASSED** |
| **Test 12** | Assistant Recommendations Query (`PRESCRIPTIVE_RECOMMENDATIONS`) | Tools: `['get_project_recommendations']` | ✅ **PASSED** |
| **Test 13** | Assistant Early Warning Query (`EARLY_WARNING_PRIORITIZATION`) | Tools: `['get_early_warning_projects']` | ✅ **PASSED** |
| **Test 14** | Assistant Executive Briefing Query (`EXECUTIVE_MONITORING_BRIEF`) | Tools: `['get_executive_briefing']` | ✅ **PASSED** |
| **Test 15** | Unknown Project Code Handling | Sufficiency `NONE` | ✅ **PASSED** |
| **Test 16** | Insufficient Evidence Hard Guard | Hard Guard Prevented Speculation | ✅ **PASSED** |
| **Test 17** | Citation Integrity & `[E1]` Tag Mapping | Citations Verified with `[E1]` Tags | ✅ **PASSED** |
| **Test 18** | REST API Router Endpoints Integrity | All 4 Router Endpoints Returned HTTP 200 JSON | ✅ **PASSED** |

### Summary Benchmark Metrics
- **Total Test Cases**: **18**
- **Passed Test Cases**: **18 (100.0%)**
- **Verification Suite Pass Rate**: **100% pass rate across the 18-case Phase 7 verification suite**

> [!NOTE]
> **Trajectory Edge Case Preservation (Project 020100044)**:
> The historical risk trajectory for project `020100044` across 7 reporting periods is:
> `2018-04 (51.0), 2019-04 (49.1), 2020-04 (82.2), 2021-04 (83.9), 2022-04 (83.9), 2023-04 (80.8), 2024-04 (31.3)`
> The trajectory algorithm classified this as **`VOLATILE`** (slope $m = -2.66$, variance $\sigma^2 = 428.92$).
> Because the score variance exceeds the $\sigma^2 > 25.0$ volatility threshold, the high score variance condition correctly overrides the negative slope ($m = -2.66$), demonstrating that trend classification is not simply *negative slope = improving*.

---

## 4. REST API Endpoints

- `GET /api/risk/decomposition/{project_code}`: SHAP driver decomposition & protective factors.
- `GET /api/risk/trajectory/{project_code}`: Historical risk trajectory and mathematical trend.
- `GET /api/risk/recommendations/{project_code}`: Policy-grounded decision support recommendations.
- `GET /api/risk/early-warnings`: Prioritized list of early warning projects.
- `GET /api/risk/executive-briefing`: Executive monitoring briefing with quantitative KPIs and RAG context.
