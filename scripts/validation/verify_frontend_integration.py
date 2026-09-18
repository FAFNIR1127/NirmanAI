#!/usr/bin/env python3
"""
scripts/validation/verify_frontend_integration.py

Phase 8 — Automated Frontend Integration & End-to-End Verification Suite.
Validates:
1. Static File Serving (index.html, styles.css, app.js) via FastAPI.
2. Backend API Connectivity for all integrated views:
   - /api/analytics/portfolio_kpis
   - /api/risk/early_warnings
   - /api/projects
   - /api/risk/intelligence/{project_code}
   - /api/documents/search
   - /api/assistant/query
3. Strict Backend Authority Rule & Error Edge-Case Handling (404 for invalid project).
"""

import sys
import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"

def test_endpoint(name, url, method="GET", body=None, expected_status=200):
    print(f"Testing {name}: {method} {url} ...", end=" ")
    try:
        req = urllib.request.Request(url, method=method)
        if body:
            req.add_header("Content-Type", "application/json")
            data = json.dumps(body).encode("utf-8")
            req.data = data

        with urllib.request.urlopen(req) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            data_bytes = resp.read()
            
            if status != expected_status:
                print(f"FAILED (Expected {expected_status}, got {status})")
                return False, None

            print(f"PASSED (Status {status})")
            return True, (data_bytes, content_type)

    except urllib.error.HTTPError as e:
        if e.code == expected_status:
            print(f"PASSED (Expected HTTP {expected_status})")
            return True, (e.read(), e.headers.get("Content-Type", ""))
        else:
            print(f"FAILED (HTTP {e.code})")
            return False, None
    except Exception as e:
        print(f"FAILED (Error: {e})")
        return False, None

def main():
    print("=" * 70)
    print("      PROJECT NIRMAN — PHASE 8 FRONTEND INTEGRATION VERIFICATION")
    print("=" * 70)

    results = []

    # 1. Test Static File Serving
    ok, res = test_endpoint("1. Static Index HTML", f"{BASE_URL}/")
    if ok and res:
        html_str = res[0].decode("utf-8")
        has_title = "<title>Project Nirman" in html_str
        has_app_js = "app.js" in html_str
        print(f"   └─ HTML Validation: Title Present: {has_title}, App JS Linked: {has_app_js}")
        results.append(ok and has_title and has_app_js)
    else:
        results.append(False)

    ok, res = test_endpoint("2. Static CSS Stylesheet", f"{BASE_URL}/styles.css")
    results.append(ok)

    ok, res = test_endpoint("3. Static Application JS", f"{BASE_URL}/app.js")
    results.append(ok)

    # 2. Test Core REST APIs
    ok, res = test_endpoint("4. Portfolio KPIs API", f"{BASE_URL}/api/analytics/portfolio_kpis")
    if ok and res:
        kpis = json.loads(res[0].decode("utf-8"))
        print(f"   └─ Total Projects: {kpis.get('total_projects')}, High Risk: {kpis.get('high_critical_risk_count')}")
    results.append(ok)

    ok, res = test_endpoint("5. Early Warnings Matrix API", f"{BASE_URL}/api/risk/early_warnings?limit=5")
    if ok and res:
        ew_data = json.loads(res[0].decode("utf-8"))
        ew_list = ew_data if isinstance(ew_data, list) else ew_data.get('prioritized_projects', [])
        print(f"   └─ Prioritized Count: {len(ew_list)}")
    results.append(ok)


    ok, res = test_endpoint("6. Project Directory API", f"{BASE_URL}/api/projects?limit=5")
    if ok and res:
        proj_data = json.loads(res[0].decode("utf-8"))
        proj_list = proj_data if isinstance(proj_data, list) else proj_data.get('projects', [])
        total_cnt = len(proj_list) if isinstance(proj_data, list) else proj_data.get('total_count', len(proj_list))
        print(f"   └─ Returned Projects: {len(proj_list)}, Total Count: {total_cnt}")
    results.append(ok)


    ok, res = test_endpoint("7. Risk Intelligence Engine API", f"{BASE_URL}/api/risk/intelligence/020100044")
    if ok and res:
        ri = json.loads(res[0].decode("utf-8"))
        score = ri.get('risk_assessment', {}).get('risk_score')
        cat = ri.get('risk_assessment', {}).get('risk_category')
        trend = ri.get('risk_trajectory', {}).get('trajectory_classification')
        print(f"   └─ Risk Score: {score}, Category: {cat}, Mathematical Trend: {trend}")
    results.append(ok)

    ok, res = test_endpoint("8. RAG Document Search API", f"{BASE_URL}/api/documents/search?query=status&top_k=2")
    if ok and res:
        rag = json.loads(res[0].decode("utf-8"))
        chunks = rag.get('results', rag.get('chunks', []))
        print(f"   └─ Retrieved Chunks: {len(chunks)}")
    results.append(ok)

    ok, res = test_endpoint(
        "9. AI Orchestrator Assistant API",
        f"{BASE_URL}/api/assistant/query",
        method="POST",
        body={"query": "What is the risk of project 020100044?"}
    )
    if ok and res:
        ast = json.loads(res[0].decode("utf-8"))
        intent = ast.get('intent')
        citations = len(ast.get('citations', []))
        print(f"   └─ Intent Classified: {intent}, Grounded Citations: {citations}")
    results.append(ok)

    # 3. Test Edge Cases & Authority Rules
    ok, res = test_endpoint("10. Invalid Project Code 404 Guard", f"{BASE_URL}/api/risk/intelligence/INVALID_PROJECT", expected_status=404)
    results.append(ok)

    print("=" * 70)
    passed_count = sum(1 for r in results if r)
    total_count = len(results)
    pass_rate = (passed_count / total_count) * 100

    print(f"RESULTS SUMMARY: {passed_count}/{total_count} Tests Passed ({pass_rate:.1f}% Pass Rate)")
    print("=" * 70)

    if passed_count == total_count:
        print("✅ Phase 8 Integrated Web Platform Verification Successful!")
        sys.exit(0)
    else:
        print("❌ Phase 8 Verification Failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
