#!/usr/bin/env python3
"""
Phase 10 Full-System QA Suite 11: Analytics Ground-Truth Dual-Path Tests (ANALYTICS-001 to ANALYTICS-008)
Compares REST API outputs against independent, raw PostgreSQL SQL queries.
"""
import sys
import os
import urllib.request
import json
import sqlalchemy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from backend.app.config import DATABASE_URL

API_HOST = "http://127.0.0.1:8000"

def get_api(path):
    url = f"{API_HOST}{path}"
    try:
        req = urllib.request.urlopen(url, timeout=4)
        return req.status, json.loads(req.read().decode('utf-8'))
    except Exception as e:
        return 0, {"error": str(e)}

def run_tests():
    results = []
    engine = sqlalchemy.create_engine(DATABASE_URL)

    # 1. Independent Ground-Truth SQL Queries
    with engine.connect() as conn:
        sql_total_p = "SELECT COUNT(*) FROM projects;"
        sql_high_crit = """
            SELECT COUNT(*) FROM (
                SELECT DISTINCT ON (project_code) project_code, risk_category 
                FROM risk_scores 
                ORDER BY project_code, reporting_month DESC
            ) r WHERE risk_category IN ('HIGH', 'CRITICAL');
        """
        sql_tot_orig = "SELECT SUM(original_cost) FROM projects;"
        
        db_total_p = conn.execute(sqlalchemy.text(sql_total_p)).scalar() or 0
        db_high_crit = conn.execute(sqlalchemy.text(sql_high_crit)).scalar() or 0
        db_tot_orig = float(conn.execute(sqlalchemy.text(sql_tot_orig)).scalar() or 0.0)

    # 2. Fetch API Output
    st, kpi_api = get_api("/api/analytics/portfolio_kpis")

    # ANALYTICS-001: Total Monitored Projects Ground-Truth Verification
    api_total = kpi_api.get("total_master_projects") or kpi_api.get("total_projects", 0)
    results.append({
        "id": "ANALYTICS-001",
        "category": "Analytics Ground-Truth",
        "name": "Total Monitored Projects Count Match (API vs PostgreSQL)",
        "passed": st == 200 and api_total == db_total_p,
        "severity": "P0",
        "expected": f"PostgreSQL SQL Count: {db_total_p}",
        "actual": f"REST API Count: {api_total}",
        "hint": "Reconcile analytics_service.py SQL query against projects table count."
    })

    # ANALYTICS-002: Total Portfolio Original Cost Ground-Truth Verification
    api_orig_cost = kpi_api.get("total_original_cost_crore", 0.0)
    cost_diff = abs(api_orig_cost - round(db_tot_orig, 2))
    results.append({
        "id": "ANALYTICS-002",
        "category": "Analytics Ground-Truth",
        "name": "Total Original Cost Sum Match (API vs PostgreSQL)",
        "passed": st == 200 and cost_diff < 1.0,
        "severity": "P0",
        "expected": f"PostgreSQL SQL Sum: ₹{db_tot_orig:,.2f} Cr",
        "actual": f"REST API Sum: ₹{api_orig_cost:,.2f} Cr",
        "hint": "Check SUM(original_cost) aggregation in analytics service."
    })

    # ANALYTICS-003: High/Critical Risk Count Match
    api_high_crit = kpi_api.get("high_critical_risk_count", 0)
    results.append({
        "id": "ANALYTICS-003",
        "category": "Analytics Ground-Truth",
        "name": "High/Critical Risk Projects Count Match (API vs PostgreSQL)",
        "passed": st == 200 and api_high_crit == db_high_crit,
        "severity": "P0",
        "expected": f"PostgreSQL SQL High/Critical Count: {db_high_crit}",
        "actual": f"REST API High/Critical Count: {api_high_crit}",
        "hint": "Verify distinct project risk category query."
    })

    # ANALYTICS-004: Risk Distribution Total Population Match
    st_rd, rd_api = get_api("/api/analytics/risk-distribution")
    rd_total = 0
    if st_rd == 200 and isinstance(rd_api, list):
        rd_total = sum(item.get("project_count", 0) for item in rd_api)

    results.append({
        "id": "ANALYTICS-004",
        "category": "Analytics Distribution",
        "name": "Risk Distribution Sum Matches Total Monitored Population",
        "passed": st_rd == 200 and rd_total == db_total_p,
        "severity": "P1",
        "expected": f"Sum of Critical+High+Moderate+Low == {db_total_p}",
        "actual": f"Sum of risk distribution categories: {rd_total}",
        "hint": "Check risk-distribution GROUP BY query logic."
    })

    # ANALYTICS-005: State Statistics API Response Integrity
    st_state, state_api = get_api("/api/analytics/by-state")
    results.append({
        "id": "ANALYTICS-005",
        "category": "Analytics Breakdown",
        "name": "State-level Risk Statistics Breakdown API",
        "passed": st_state == 200 and isinstance(state_api, list) and len(state_api) > 0,
        "severity": "P1",
        "expected": "HTTP 200 with state statistics list",
        "actual": f"Returned {len(state_api) if isinstance(state_api, list) else 0} state records",
        "hint": "Verify /api/analytics/by-state endpoint"
    })

    # ANALYTICS-006: Agency Statistics API Response Integrity
    st_agency, agency_api = get_api("/api/analytics/by-agency")
    results.append({
        "id": "ANALYTICS-006",
        "category": "Analytics Breakdown",
        "name": "Agency-level Risk Statistics Breakdown API",
        "passed": st_agency == 200 and isinstance(agency_api, list) and len(agency_api) > 0,
        "severity": "P1",
        "expected": "HTTP 200 with agency statistics list",
        "actual": f"Returned {len(agency_api) if isinstance(agency_api, list) else 0} agency records",
        "hint": "Verify /api/analytics/by-agency endpoint"
    })

    return results

if __name__ == "__main__":
    res = run_tests()
    print(json.dumps(res, indent=2))
