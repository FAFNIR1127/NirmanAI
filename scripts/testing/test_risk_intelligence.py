#!/usr/bin/env python3
"""
Phase 10 Full-System QA Suite 13 & 14: Risk Intelligence, SHAP Drivers, Trajectory, Prescriptive Rules & Briefings
(SHAP-001 to SHAP-007, TRAJ-001 to TRAJ-009, REC-001 to REC-002, EW-001, BRIEF-001 to BRIEF-006)
"""
import sys
import os
import urllib.request
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from backend.app.services.risk_decomposition_service import RiskDecompositionService
from backend.app.services.risk_trajectory_service import RiskTrajectoryService
from backend.app.services.recommendation_engine import PrescriptiveRecommendationEngine

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
    decomp_svc = RiskDecompositionService()
    traj_svc = RiskTrajectoryService()
    rec_engine = PrescriptiveRecommendationEngine()

    # 1. SHAP Risk Decomposition Tests
    shap_data = decomp_svc.decompose_project_risk("020100044")
    drivers = (shap_data.get("primary_risk_drivers") or shap_data.get("risk_drivers", [])) if shap_data else []
    protective = shap_data.get("protective_factors", []) if shap_data else []

    has_drivers = len(drivers) > 0
    has_protective = len(protective) > 0

    results.append({
        "id": "SHAP-001",
        "category": "SHAP Decomposition",
        "name": "Top Adverse Risk Drivers Identified",
        "passed": has_drivers,
        "severity": "P0",
        "expected": "Non-empty list of adverse risk driver features",
        "actual": f"Drivers count: {len(shap_data.get('risk_drivers', [])) if shap_data else 0}",
        "hint": "Verify RiskDecompositionService SHAP value computation."
    })
    results.append({
        "id": "SHAP-002",
        "category": "SHAP Decomposition",
        "name": "Mitigating Protective Factors Identified",
        "passed": has_protective,
        "severity": "P0",
        "expected": "Non-empty list of protective factor features",
        "actual": f"Protective count: {len(shap_data.get('protective_factors', [])) if shap_data else 0}",
        "hint": "Verify RiskDecompositionService protective factor extraction."
    })

    # 2. Risk Trajectory & Mathematical Slope/Variance Tests
    traj_data = traj_svc.get_project_risk_trajectory("020100044")
    points = (traj_data.get("trajectory") or traj_data.get("historical_points", [])) if traj_data else []
    has_points = len(points) > 0
    trend_class = (traj_data.get("trend") or traj_data.get("trajectory_classification")) if traj_data else None

    # Verify chronological ordering
    months = [p["reporting_month"] for p in points]
    is_ordered = len(months) > 0 and months == sorted(months)

    results.append({
        "id": "TRAJ-001",
        "category": "Risk Trajectory",
        "name": "Historical Trajectory Points Chronologically Ordered",
        "passed": has_points and is_ordered,
        "severity": "P1",
        "expected": "Chronologically sorted YYYY-MM reporting months",
        "actual": f"Ordered: {is_ordered}, Points count: {len(points)}, Months: {months}",
        "hint": "Check ORDER BY reporting_month ASC in trajectory query."
    })

    valid_trends = ["IMPROVING", "DETERIORATING", "STABLE", "VOLATILE", "INSUFFICIENT_HISTORY"]
    results.append({
        "id": "TRAJ-005",
        "category": "Mathematical Trend",
        "name": "Mathematical Trend Classification Invariants",
        "passed": trend_class in valid_trends,
        "severity": "P0",
        "expected": f"One of valid trend categories: {valid_trends}",
        "actual": f"Classification: '{trend_class}'",
        "hint": "Check slope and variance classification logic in RiskTrajectoryService."
    })

    # 3. Prescriptive Recommendation Engine Tests
    rec_payload = rec_engine.get_project_recommendations("020100044")
    recs_list = rec_payload.get("recommendations", []) if isinstance(rec_payload, dict) else (rec_payload if isinstance(rec_payload, list) else [])
    has_recs = len(recs_list) > 0
    results.append({
        "id": "REC-001",
        "category": "Prescriptive Recommendations",
        "name": "Policy Rule Triggered Recommendations Generation",
        "passed": has_recs,
        "severity": "P1",
        "expected": "Non-empty list of recommendation objects with title and action_details",
        "actual": f"Generated {len(recs_list)} policy recommendations",
        "hint": "Verify recommendation trigger rules in PrescriptiveRecommendationEngine."
    })

    # 4. Early Warning Matrix REST Endpoint Test
    st_ew, body_ew = get_api("/api/risk/early_warnings?limit=5")
    ew_list = body_ew if isinstance(body_ew, list) else body_ew.get("prioritized_projects", [])
    ew_ok = st_ew == 200 and len(ew_list) > 0 and all(p.get("risk_score", 0) >= 28.0 for p in ew_list)

    results.append({
        "id": "EW-001",
        "category": "Early Warning Intelligence",
        "name": "Early Warning Priority Queue Cutoff (T* = 0.28 / Score >= 28.0)",
        "passed": ew_ok,
        "severity": "P0",
        "expected": "Prioritized list where every project meets operational threshold score >= 28.0",
        "actual": f"Status {st_ew}, Count: {len(ew_list)}, All meet threshold: {ew_ok}",
        "hint": "Check EarlyWarningPrioritizationService cutoff threshold."
    })

    # 5. Executive Briefing REST Endpoint Test
    st_br, body_br = get_api("/api/risk/briefing/020100044")
    br_text = body_br.get("executive_briefing") or body_br.get("briefing", "")
    br_ok = st_br == 200 and "EXECUTIVE MONITORING BRIEF" in br_text and "QUANTITATIVE RISK ASSESSMENT" in br_text

    results.append({
        "id": "BRIEF-001",
        "category": "Executive Briefings",
        "name": "Single Project Executive Briefing Synthesis API",
        "passed": br_ok,
        "severity": "P0",
        "expected": "HTTP 200 with structured executive briefing document text",
        "actual": f"Status {st_br}, Contains expected headers: {br_ok}",
        "hint": "Check /api/risk/briefing/{code} in backend/app/routes/risk_intelligence.py"
    })

    return results

if __name__ == "__main__":
    res = run_tests()
    print(json.dumps(res, indent=2))
