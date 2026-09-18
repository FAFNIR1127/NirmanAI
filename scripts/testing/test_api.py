#!/usr/bin/env python3
"""
Phase 10 Full-System QA Suite 6, 7, 8, 9, 10: FastAPI REST API Contracts & Endpoint Edge Cases
(API-001 to API-002, PRJ-001 to PRJ-014, SEARCH-001 to SEARCH-012, FILTER-001 to FILTER-015, CMP-001 to CMP-009)
"""
import sys
import os
import urllib.request
import urllib.parse
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

API_HOST = "http://127.0.0.1:8000"

def get(path):
    url = f"{API_HOST}{path}"
    try:
        req = urllib.request.urlopen(url, timeout=4)
        return req.status, json.loads(req.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))
    except Exception as e:
        return 0, {"error": str(e)}

def run_tests():
    results = []

    # API-001: Health Endpoint
    status, payload = get("/api/health")
    results.append({
        "id": "API-001",
        "category": "API Contracts",
        "name": "GET /api/health Schema & Contract Compliance",
        "passed": status == 200 and payload.get("status") == "healthy",
        "severity": "P0",
        "expected": "HTTP 200 with status=='healthy'",
        "actual": f"Status: {status}, Payload: {payload}",
        "hint": "Check /api/health endpoint in backend/app/routes/health.py"
    })

    # PRJ-001 to PRJ-007: Project Directory Limits
    prj_limit_cases = [
        ("PRJ-001", "/api/projects", 200, "Default pagination"),
        ("PRJ-002", "/api/projects?limit=1", 200, "Limit=1"),
        ("PRJ-003", "/api/projects?limit=5", 200, "Limit=5"),
        ("PRJ-004", "/api/projects?limit=500", 200, "Limit=500 (Max)"),
        ("PRJ-006", "/api/projects?limit=-1", 422, "Negative limit validation guard")
    ]

    for t_id, path, exp_status, desc in prj_limit_cases:
        st, body = get(path)
        passed = st == exp_status
        if st == 200 and isinstance(body, list) and "limit=" in path and exp_status == 200:
            exp_len = int(path.split("limit=")[1].split("&")[0])
            passed = len(body) <= exp_len

        results.append({
            "id": t_id,
            "category": "Project Directory API",
            "name": f"Project Listing: {desc}",
            "passed": passed,
            "severity": "P1",
            "expected": f"HTTP {exp_status}",
            "actual": f"Status {st}, Records returned: {len(body) if isinstance(body, list) else 'Error'}",
            "hint": "Check query parameter validation in backend/app/routes/projects.py"
        })

    # PRJ-010 to PRJ-014: Single Project Lookup & Security Guards
    prj_lookup_cases = [
        ("PRJ-010", "/api/projects/020100044", 200, "Known valid project code '020100044'"),
        ("PRJ-011", "/api/projects/NONEXISTENT_CODE_99999", 404, "Nonexistent project code guard"),
        ("PRJ-013", "/api/projects/" + urllib.parse.quote("' OR '1'='1"), 404, "SQL Injection string project lookup guard")
    ]

    for t_id, path, exp_status, desc in prj_lookup_cases:
        st, body = get(path)
        passed = st == exp_status
        if st == 200 and isinstance(body, dict):
            passed = body.get("project_code") == "020100044" and "observations" in body

        results.append({
            "id": t_id,
            "category": "Project Detail API",
            "name": f"Project Lookup: {desc}",
            "passed": passed,
            "severity": "P0",
            "expected": f"HTTP {exp_status}",
            "actual": f"Status {st}, Body keys: {list(body.keys()) if isinstance(body, dict) else body}",
            "hint": "Check get_project_details service in backend/app/services/project_service.py"
        })

    # SEARCH-001 to SEARCH-012: Project Search Tests
    search_cases = [
        ("SEARCH-001", "/api/projects/search?q=BHAVINI", 200, "Search keyword 'BHAVINI'"),
        ("SEARCH-002", "/api/projects/search?q=Pune", 200, "Search keyword 'Pune'"),
        ("SEARCH-003a", "/api/projects/search?q=pune", 200, "Case-insensitive search 'pune'"),
        ("SEARCH-003b", "/api/projects/search?q=PUNE", 200, "Case-insensitive search 'PUNE'"),
        ("SEARCH-005", "/api/projects/search?q=020100044", 200, "Exact project code search '020100044'"),
        ("SEARCH-012", "/api/projects/search?q=XZY_NONEXISTENT_QUERY_TERM_9999", 200, "No-match query returns empty list")
    ]

    for t_id, path, exp_status, desc in search_cases:
        st, body = get(path)
        passed = st == exp_status and isinstance(body, list)
        if t_id == "SEARCH-012":
            passed = passed and len(body) == 0
        elif t_id in ["SEARCH-003a", "SEARCH-003b"]:
            st1, b1 = get("/api/projects/search?q=pune")
            st2, b2 = get("/api/projects/search?q=PUNE")
            passed = st1 == 200 and st2 == 200 and len(b1) == len(b2)

        results.append({
            "id": t_id,
            "category": "Project Search API",
            "name": f"Search Test: {desc}",
            "passed": passed,
            "severity": "P1",
            "expected": f"HTTP {exp_status} with matching list",
            "actual": f"Status {st}, Matches: {len(body) if isinstance(body, list) else 0}",
            "hint": "Check search_projects query in backend/app/services/query_service.py"
        })

    # FILTER-001 to FILTER-015: Project Filter Permutations
    filter_cases = [
        ("FILTER-001", "/api/projects/filter?state=MAHARASHTRA", 200, "Filter state='MAHARASHTRA'"),
        ("FILTER-003", "/api/projects/filter?risk_category=CRITICAL", 200, "Filter risk_category='CRITICAL'"),
        ("FILTER-006", "/api/projects/filter?min_cost=100&max_cost=500", 200, "Filter min_cost=100 & max_cost=500"),
        ("FILTER-010", "/api/projects/filter?state=MAHARASHTRA&risk_category=HIGH", 200, "Combined filter state + risk")
    ]

    for t_id, path, exp_status, desc in filter_cases:
        st, body = get(path)
        passed = st == exp_status and isinstance(body, list)
        results.append({
            "id": t_id,
            "category": "Project Filter API",
            "name": f"Filter Test: {desc}",
            "passed": passed,
            "severity": "P1",
            "expected": f"HTTP {exp_status} list output",
            "actual": f"Status {st}, Matched records: {len(body) if isinstance(body, list) else 0}",
            "hint": "Check filter_projects query logic in query_service.py"
        })

    # CMP-001 to CMP-009: Compare Projects API
    cmp_cases = [
        ("CMP-001", "/api/projects/compare?codes=020100044,220100262", 200, 2, "Compare two valid project codes"),
        ("CMP-003", "/api/projects/compare?codes=020100044", 200, 1, "Compare single project code"),
        ("CMP-006", "/api/projects/compare?codes=NONEXISTENT_1,NONEXISTENT_2", 200, 0, "Compare nonexistent codes")
    ]

    for t_id, path, exp_status, exp_count, desc in cmp_cases:
        st, body = get(path)
        passed = st == exp_status and isinstance(body, list) and len(body) == exp_count
        results.append({
            "id": t_id,
            "category": "Project Comparison API",
            "name": f"Compare Test: {desc}",
            "passed": passed,
            "severity": "P1",
            "expected": f"HTTP {exp_status} with {exp_count} records",
            "actual": f"Status {st}, Records: {len(body) if isinstance(body, list) else 0}",
            "hint": "Check compare_projects in query_service.py"
        })

    return results

if __name__ == "__main__":
    res = run_tests()
    print(json.dumps(res, indent=2))
