import urllib.request
import urllib.error
import json
import sqlite3
import sqlalchemy
import pandas as pd
from pathlib import Path

# ============================================================
# CONFIG & PATHS
# ============================================================

DATABASE_URL = "postgresql://postgres:hulk@localhost:5432/nirman_db"
API_BASE_URL = "http://localhost:8000"
DOC_PATH = Path("documentation/phase4_data_intelligence.md")


def get_db_connection():
    engine = sqlalchemy.create_engine(DATABASE_URL)
    return engine.connect()


def fetch_api(endpoint):
    url = f"{API_BASE_URL}{endpoint}"
    req = urllib.request.urlopen(url)
    return req.getcode(), json.loads(req.read().decode())


def run_comprehensive_verification():
    print("=" * 110)
    print("PHASE 4 — DATA INTELLIGENCE LAYER COMPREHENSIVE VERIFICATION")
    print("=" * 110)

    # ------------------------------------------------------------
    # 1. DATABASE ROW COUNT & SCHEMA VERIFICATION
    # ------------------------------------------------------------
    print("\n=== 1. POSTGRESQL DATABASE VERIFICATION ===")
    conn = get_db_connection()
    
    cnt_projects = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM projects")).scalar()
    cnt_obs = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM project_observations")).scalar()
    cnt_feat = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM project_features")).scalar()
    cnt_risk = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM risk_scores")).scalar()
    cnt_live = conn.execute(sqlalchemy.text("SELECT COUNT(DISTINCT project_code) FROM project_observations WHERE reporting_month >= '2025-07'")).scalar()
    tot_orig_cost = conn.execute(sqlalchemy.text("SELECT SUM(original_cost) FROM projects")).scalar()

    print(f"PostgreSQL Master Projects Count  : {cnt_projects:,}")
    print(f"PostgreSQL Observations Count     : {cnt_obs:,}")
    print(f"PostgreSQL Features Count         : {cnt_feat:,}")
    print(f"PostgreSQL Risk Scores Count      : {cnt_risk:,}")
    print(f"PostgreSQL Live 2026 Projects     : {cnt_live:,}")
    print(f"PostgreSQL Total Original Cost    : ₹{tot_orig_cost:,.2f} Crore")

    assert cnt_projects == 3589, f"Expected 3,589 master projects, got {cnt_projects}"
    assert cnt_obs == 13098, f"Expected 13,098 observations, got {cnt_obs}"
    assert cnt_risk == 13098, f"Expected 13,098 risk scores, got {cnt_risk}"
    print("Database Verification: ✅ PASSED!")

    # ------------------------------------------------------------
    # 2. API NUMERICAL ACCURACY MATCH WITH DATABASE
    # ------------------------------------------------------------
    print("\n=== 2. API NUMERICAL ACCURACY MATCH WITH POSTGRESQL ===")
    status, summary_api = fetch_api("/api/analytics/summary")
    
    print("Executive Summary API Output:")
    print(json.dumps(summary_api, indent=2))

    # Assert exact match between DB and API
    assert summary_api["total_master_projects"] == cnt_projects, "Master project count mismatch!"
    assert summary_api["total_live_projects_2026"] == cnt_live, "Live 2026 project count mismatch!"
    assert abs(summary_api["total_original_cost_crore"] - float(tot_orig_cost)) < 1.0, "Total original cost mismatch!"

    print("API vs Database Numerical Accuracy: ✅ 100% MATCH!")

    # ------------------------------------------------------------
    # 3. RISK DISTRIBUTION VERIFICATION
    # ------------------------------------------------------------
    print("\n=== 3. RISK DISTRIBUTION API MATCH ===")
    status, risk_dist_api = fetch_api("/api/analytics/risk-distribution")
    
    db_risk_dist = pd.read_sql(sqlalchemy.text("""
        SELECT r.risk_category, COUNT(*) as cnt
        FROM (
            SELECT DISTINCT ON (project_code) project_code, risk_category
            FROM risk_scores
            ORDER BY project_code, reporting_month DESC
        ) r
        GROUP BY r.risk_category
    """), conn)

    db_map = dict(zip(db_risk_dist["risk_category"], db_risk_dist["cnt"]))
    api_map = {item["risk_category"]: item["project_count"] for item in risk_dist_api}

    print(f"DB Risk Breakdown : {db_map}")
    print(f"API Risk Breakdown: {api_map}")
    
    for cat, cnt in db_map.items():
        assert api_map[cat] == cnt, f"Mismatch in category {cat}: DB={cnt}, API={api_map[cat]}"

    print("Risk Distribution Verification: ✅ 100% MATCH!")

    # ------------------------------------------------------------
    # 4. STRUCTURED QUERY SERVICES (SEARCH, FILTER, COMPARE)
    # ------------------------------------------------------------
    print("\n=== 4. STRUCTURED QUERY SERVICES (SEARCH, FILTER, COMPARE) ===")
    
    # Search
    status, search_res = fetch_api("/api/projects/search?q=BHAVINI")
    print(f"Search 'BHAVINI' Result Count: {len(search_res)}")
    assert len(search_res) >= 1, "Search for BHAVINI returned 0 results!"

    # Filter
    status, filter_res = fetch_api("/api/projects/filter?state=TAMIL%20NADU&risk_category=CRITICAL&limit=10")
    print(f"Filter 'TAMIL NADU + CRITICAL' Count: {len(filter_res)}")

    # Compare
    status, compare_res = fetch_api("/api/projects/compare?codes=020100044,N04000073")
    print(f"Compare '020100044 vs N04000073' Result Count: {len(compare_res)}")
    assert len(compare_res) == 2, f"Expected 2 projects in comparison, got {len(compare_res)}"
    
    print("Structured Query Services: ✅ PASSED!")

    # ------------------------------------------------------------
    # 5. EDGE CASES & ERROR HANDLING
    # ------------------------------------------------------------
    print("\n=== 5. EDGE CASE & ERROR HANDLING VERIFICATION ===")
    
    # Invalid Project Risk -> 404
    try:
        urllib.request.urlopen(f"{API_BASE_URL}/api/risk/predict/INVALID_CODE")
        raise AssertionError("Expected 404 for invalid risk project")
    except urllib.error.HTTPError as e:
        assert e.code == 404, f"Expected 404, got {e.code}"
        print("  • Invalid Risk Code (INVALID_CODE) -> HTTP 404 ✅")

    # Invalid Project History -> 404
    try:
        urllib.request.urlopen(f"{API_BASE_URL}/api/projects/INVALID_CODE")
        raise AssertionError("Expected 404 for invalid project code")
    except urllib.error.HTTPError as e:
        assert e.code == 404, f"Expected 404, got {e.code}"
        print("  • Invalid Project Code (INVALID_CODE) -> HTTP 404 ✅")

    # Non-existent State Filter -> Empty List (HTTP 200)
    status, empty_filter = fetch_api("/api/projects/filter?state=NON_EXISTENT_STATE")
    assert status == 200 and len(empty_filter) == 0
    print("  • Non-existent State Filter -> Empty Array HTTP 200 ✅")

    # Non-existent Search -> Empty List (HTTP 200)
    status, empty_search = fetch_api("/api/projects/search?q=XYZ123NONEXISTENT")
    assert status == 200 and len(empty_search) == 0
    print("  • Non-existent Search Query -> Empty Array HTTP 200 ✅")

    conn.close()

    print("\n" + "=" * 110)
    print("ALL PHASE 4 COMPLETION CRITERIA & NUMERICAL VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=" * 110)


if __name__ == "__main__":
    run_comprehensive_verification()
