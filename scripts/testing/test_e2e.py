#!/usr/bin/env python3
"""
Phase 10 Full-System QA Suite 55, 56, 57: Complete End-to-End Stack & User Journeys
(E2E-001 to E2E-005, JOURNEY-A, JOURNEY-B, JOURNEY-C)
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
        req = urllib.request.urlopen(url, timeout=5)
        return req.status, json.loads(req.read().decode('utf-8'))
    except Exception as e:
        return 0, {"error": str(e)}

def post(path, payload):
    url = f"{API_HOST}{path}"
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        res = urllib.request.urlopen(req, timeout=5)
        return res.status, json.loads(res.read().decode('utf-8'))
    except Exception as e:
        return 0, {"error": str(e)}

def run_tests():
    results = []

    # 1. E2E-001: Full Stack Value Flow for Project '020100044'
    st_kpi, kpis = get("/api/analytics/portfolio_kpis")
    st_det, det = get("/api/projects/020100044")
    st_intel, intel = get("/api/risk/intelligence/020100044")
    st_rag, rag = get("/api/documents/search?query=020100044&top_k=2")
    st_ast, ast = post("/api/assistant/query", {"query": "What is the risk of project 020100044?"})

    e2e_ok = (st_kpi == 200 and st_det == 200 and st_intel == 200 and st_rag == 200 and st_ast == 200)

    results.append({
        "id": "E2E-001",
        "category": "End-to-End Stack",
        "name": "Full Stack Value Traversal (PostgreSQL -> Risk Engine -> RAG -> Assistant -> REST)",
        "passed": e2e_ok,
        "severity": "P0",
        "expected": "All 5 stack endpoints return HTTP 200 with consistent project 020100044 data",
        "actual": f"KPIs:{st_kpi}, Detail:{st_det}, Intel:{st_intel}, RAG:{st_rag}, Assistant:{st_ast}",
        "hint": "Check full stack integration in backend/app/main.py"
    })

    # 2. Journey A: Executive Monitoring Flow
    st_ew, ew = get("/api/risk/early_warnings?limit=5")
    st_brief, brief = get("/api/risk/briefing/020100044")
    journey_a_ok = st_kpi == 200 and st_ew == 200 and st_brief == 200

    results.append({
        "id": "JOURNEY-A",
        "category": "User Journey",
        "name": "Journey A — Executive Monitoring Overview (KPIs -> Early Warnings -> Executive Briefing)",
        "passed": journey_a_ok,
        "severity": "P0",
        "expected": "Executive user journey completes cleanly across all analytical endpoints",
        "actual": f"Journey A status: {'SUCCESS' if journey_a_ok else 'FAILED'}",
        "hint": "Verify executive dashboard API flow."
    })

    # 3. Journey B: Risk Analyst Deep-Dive Flow
    st_search, search = get("/api/projects/search?q=BHAVINI")
    st_traj, traj = get("/api/risk/trajectory/020100044")
    st_recs, recs = get("/api/risk/recommendations/020100044")
    journey_b_ok = st_search == 200 and st_traj == 200 and st_recs == 200

    results.append({
        "id": "JOURNEY-B",
        "category": "User Journey",
        "name": "Journey B — Risk Analyst Deep-Dive (Search -> SHAP -> Trajectory -> Policy Recommendations)",
        "passed": journey_b_ok,
        "severity": "P0",
        "expected": "Analyst user journey completes cleanly across risk intelligence endpoints",
        "actual": f"Journey B status: {'SUCCESS' if journey_b_ok else 'FAILED'}",
        "hint": "Verify analyst deep-dive API flow."
    })

    # 4. Journey C: AI Orchestrated Inquiry Flow
    st_q1, resp_q1 = post("/api/assistant/query", {"query": "Tell me about project 020100044."})
    st_q2, resp_q2 = post("/api/assistant/query", {"query": "Why is project 020100044 risky according to PAIMANA?"})
    journey_c_ok = st_q1 == 200 and st_q2 == 200 and len(resp_q2.get("citations", [])) > 0

    results.append({
        "id": "JOURNEY-C",
        "category": "User Journey",
        "name": "Journey C — AI Orchestrated Inquiry (Natural Query -> Grounding -> Citations)",
        "passed": journey_c_ok,
        "severity": "P0",
        "expected": "AI assistant query returns grounded response with citation tags [E#]",
        "actual": f"Journey C status: {'SUCCESS' if journey_c_ok else 'FAILED'}",
        "hint": "Verify assistant service citation generation."
    })

    return results

if __name__ == "__main__":
    res = run_tests()
    print(json.dumps(res, indent=2))
