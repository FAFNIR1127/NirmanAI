#!/usr/bin/env python3
"""
Phase 12 QA Suite: API Contract Snapshot & Schema Validation
Verifies strict response schema conformance across core REST API endpoints.
"""
import sys
import os
import urllib.request
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
        return 0, str(e)

def run_tests():
    results = []

    # 1. Health Contract
    st, data = get("/api/health")
    has_keys = isinstance(data, dict) and all(k in data for k in ["status", "service", "model_version", "operational_threshold", "database_status"])
    results.append({
        "id": "CONTRACT-001",
        "category": "API Contract",
        "name": "Health Endpoint Schema (`/api/health`)",
        "passed": st == 200 and has_keys,
        "severity": "P0",
        "expected": "Keys: status, service, model_version, operational_threshold, database_status",
        "actual": f"Status {st}, Keys valid: {has_keys}"
    })

    # 2. Analytics KPIs Contract
    st, data = get("/api/analytics/portfolio_kpis")
    has_keys = isinstance(data, dict) and all(k in data for k in [
        "total_projects", "total_original_cost_crore", "total_anticipated_cost_crore",
        "total_cost_overrun_crore", "overall_cost_overrun_percent", "high_critical_risk_count",
        "critical_risk_project_count", "high_risk_project_count"
    ])
    results.append({
        "id": "CONTRACT-002",
        "category": "API Contract",
        "name": "Portfolio KPIs Endpoint Schema (`/api/analytics/portfolio_kpis`)",
        "passed": st == 200 and has_keys,
        "severity": "P0",
        "expected": "Valid PortfolioKPIs JSON object",
        "actual": f"Status {st}, Keys valid: {has_keys}"
    })

    # 3. Projects List Contract
    st, data = get("/api/projects?limit=5")
    has_list = isinstance(data, list) and len(data) > 0
    proj_valid = has_list and all(k in data[0] for k in ["project_code", "project_name", "risk_category", "risk_score"])
    results.append({
        "id": "CONTRACT-003",
        "category": "API Contract",
        "name": "Projects Explorer List Schema (`/api/projects`)",
        "passed": st == 200 and proj_valid,
        "severity": "P0",
        "expected": "Valid List of ProjectSummary objects with project_code, risk_category, etc.",
        "actual": f"Status {st}, List valid: {has_list}, Proj fields valid: {proj_valid}"
    })

    # 4. Risk Intelligence Contract
    st, data = get("/api/risk/intelligence/220100262")
    has_keys = isinstance(data, dict) and all(k in data for k in [
        "project_code", "project_metadata", "risk_assessment",
        "risk_decomposition", "risk_trajectory", "prescriptive_recommendations"
    ])
    results.append({
        "id": "CONTRACT-004",
        "category": "API Contract",
        "name": "Risk Intelligence Endpoint Schema (`/api/risk/intelligence/{code}`)",
        "passed": st == 200 and has_keys,
        "severity": "P0",
        "expected": "Valid RiskIntelligenceResponse schema with project_metadata, risk_assessment, etc.",
        "actual": f"Status {st}, Keys valid: {has_keys}"
    })

    # 5. Document RAG Search Contract
    st, data = get("/api/documents/search?query=cost+overrun&top_k=3")
    has_keys = isinstance(data, dict) and "total_matches" in data and "retrieved_chunks" in data and isinstance(data["retrieved_chunks"], list)
    results.append({
        "id": "CONTRACT-005",
        "category": "API Contract",
        "name": "Document Search Endpoint Schema (`/api/documents/search`)",
        "passed": st == 200 and has_keys,
        "severity": "P0",
        "expected": "Valid DocumentSearchResponse schema with total_matches and retrieved_chunks",
        "actual": f"Status {st}, Keys valid: {has_keys}"
    })

    return results

if __name__ == "__main__":
    res = run_tests()
    print(json.dumps(res, indent=2))
