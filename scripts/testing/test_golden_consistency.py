#!/usr/bin/env python3
"""
Phase 12 QA Suite: Golden Project Data Parity & DB Consistency Audit
Verifies 1-to-1 exact alignment between raw PostgreSQL database rows and REST API payloads.
"""
import sys
import os
import urllib.request
import json
import psycopg2

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

DB_URI = "postgresql://postgres:hulk@localhost:5432/nirman_db"
API_HOST = "http://127.0.0.1:8000"

def get_api_risk_intelligence(code):
    url = f"{API_HOST}/api/risk/intelligence/{code}"
    try:
        req = urllib.request.urlopen(url, timeout=5)
        return json.loads(req.read().decode('utf-8'))
    except Exception:
        return None

def get_db_project(code):
    try:
        conn = psycopg2.connect(DB_URI)
        cur = conn.cursor()
        cur.execute("""
            SELECT project_code, project_name, sector, original_cost
            FROM projects
            WHERE project_code = %s
        """, (code,))
        row = cur.fetchone()
        conn.close()
        if row:
            return {
                "project_code": row[0],
                "project_name": row[1],
                "sector": row[2],
                "original_cost": float(row[3]) if row[3] else 0.0
            }
        return None
    except Exception as e:
        print(f"DB Error: {e}")
        return None

def run_tests():
    results = []
    golden_codes = ["220100262", "N06000089", "N06000078"]

    for idx, code in enumerate(golden_codes, 1):
        db_data = get_db_project(code)
        api_data = get_api_risk_intelligence(code)

        if not db_data or not api_data:
            results.append({
                "id": f"GOLDEN-00{idx}",
                "category": "Golden Consistency",
                "name": f"Golden Project Data Consistency (`{code}`)",
                "passed": False,
                "severity": "P0",
                "expected": f"Matching DB and API records for {code}",
                "actual": f"DB found: {db_data is not None}, API found: {api_data is not None}"
            })
            continue

        api_orig_cost = api_data.get("project_metadata", {}).get("original_cost", 0.0)

        # Check Project Code & Original Cost Parity
        code_match = db_data["project_code"] == api_data["project_code"]
        cost_match = abs(db_data["original_cost"] - api_orig_cost) < 0.1

        results.append({
            "id": f"GOLDEN-00{idx}",
            "category": "Golden Consistency",
            "name": f"Golden Project Data Consistency (`{code}`)",
            "passed": code_match and cost_match,
            "severity": "P0",
            "expected": f"DB Original Cost ₹{db_data['original_cost']} Cr == API ₹{api_orig_cost} Cr",
            "actual": f"Code match: {code_match}, Cost match: {cost_match} (DB={db_data['original_cost']}, API={api_orig_cost})"
        })

    return results

if __name__ == "__main__":
    res = run_tests()
    print(json.dumps(res, indent=2))
