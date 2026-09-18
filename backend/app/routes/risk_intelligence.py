from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from backend.app.services.risk_decomposition_service import RiskDecompositionService
from backend.app.services.risk_trajectory_service import RiskTrajectoryService
from backend.app.services.recommendation_engine import PrescriptiveRecommendationEngine
from backend.app.services.early_warning_service import EarlyWarningPrioritizationService
from backend.app.services.executive_briefing_service import ExecutiveBriefingService

router = APIRouter(prefix="/api/risk", tags=["Phase 7 — Risk Intelligence Engine"])

decomposition_service = RiskDecompositionService()
trajectory_service = RiskTrajectoryService()
recommendation_engine = PrescriptiveRecommendationEngine()
early_warning_service = EarlyWarningPrioritizationService()
executive_briefing_service = ExecutiveBriefingService()


from backend.app.services.risk_engine import risk_engine_service
from backend.app.services.project_service import get_project_details
from backend.app.services.cache_service import cache_service

@router.get("/intelligence/{project_code}")
def get_unified_project_risk_intelligence(project_code: str):
    """Retrieve unified risk intelligence, SHAP drivers, trajectory, recommendations, and metadata."""
    cache_key = f"risk:intelligence:{project_code}"
    cached = cache_service.get(cache_key)
    if cached:
        return cached

    metadata = get_project_details(project_code)
    risk_assessment = risk_engine_service.get_project_risk_assessment(project_code)
    
    if not risk_assessment:
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Project '{project_code}' not found.")
        # Synthesize baseline risk assessment from actual metadata observations
        orig_cost = metadata.get("original_cost") or 1.0
        antic_cost = metadata.get("anticipated_cost") or orig_cost
        cost_overrun_pct = max(0.0, (antic_cost - orig_cost) / orig_cost * 100)
        delay_m = metadata.get("delay_months") or 0.0
        
        # Determine baseline category
        if cost_overrun_pct > 50 or delay_m > 36:
            cat = "Critical"
            prob = 0.85
            score = 85.0
        elif cost_overrun_pct > 20 or delay_m > 12:
            cat = "High"
            prob = 0.60
            score = 60.0
        elif cost_overrun_pct > 5 or delay_m > 3:
            cat = "Moderate"
            prob = 0.35
            score = 35.0
        else:
            cat = "Low"
            prob = 0.15
            score = 15.0
            
        risk_assessment = {
            "project_code": project_code,
            "project_name": metadata.get("project_name", ""),
            "agency": metadata.get("agency", ""),
            "state": metadata.get("state", ""),
            "reporting_month": metadata.get("reporting_month", "2026-07"),
            "predicted_severe_risk_prob": prob,
            "risk_score": score,
            "risk_category": cat,
            "early_warning": prob >= 0.28,
            "cost_risk_index": round(min(1.0, cost_overrun_pct / 100), 2),
            "schedule_risk_index": round(min(1.0, delay_m / 60), 2),
            "risk_drivers": [{"factor": "Cost & Timeline Variance", "impact": "High"}],
            "protective_factors": [{"factor": "Recorded In Database", "impact": "Positive"}],
            "model_version": "risk_engine_v1"
        }
    
    decomposition = decomposition_service.decompose_project_risk(project_code)
    if not decomposition:
        decomposition = {
            "project_code": project_code,
            "overall_risk_score": risk_assessment.get("risk_score", 0),
            "risk_category": risk_assessment.get("risk_category", "Low"),
            "risk_drivers": risk_assessment.get("risk_drivers", []),
            "protective_factors": risk_assessment.get("protective_factors", [])
        }
    trajectory = trajectory_service.get_project_risk_trajectory(project_code)
    recommendations = recommendation_engine.get_project_recommendations(project_code)

    res = {
        "project_code": project_code,
        "project_metadata": metadata,
        "risk_assessment": risk_assessment,
        "risk_decomposition": decomposition,
        "risk_trajectory": trajectory,
        "prescriptive_recommendations": recommendations
    }
    cache_service.set(cache_key, res, ttl_seconds=300)
    return res



@router.get("/decomposition/{project_code}")
def get_risk_decomposition(project_code: str):
    """Retrieve structured risk driver decomposition and protective factors."""
    res = decomposition_service.decompose_project_risk(project_code)
    if not res:
        metadata = get_project_details(project_code)
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Risk assessment not found for project code '{project_code}'.")
        return {
            "project_code": project_code,
            "overall_risk_score": 25.0,
            "risk_category": "Low",
            "risk_drivers": [],
            "protective_factors": []
        }
    return res


@router.get("/trajectory/{project_code}")
def get_risk_trajectory(project_code: str):
    """Retrieve model-versioned historical risk trajectory and mathematical trend classification."""
    res = trajectory_service.get_project_risk_trajectory(project_code)
    if not res:
        raise HTTPException(status_code=404, detail=f"No risk trajectory history found for project code '{project_code}'.")
    return res


@router.get("/recommendations/{project_code}")
def get_prescriptive_recommendations(project_code: str):
    """Retrieve policy-grounded decision support recommendations for a project."""
    res = recommendation_engine.get_project_recommendations(project_code)
    if not res:
        raise HTTPException(status_code=404, detail=f"Project code '{project_code}' not found.")
    return res


@router.get("/early-warnings")
@router.get("/early_warnings")
def get_early_warning_projects(limit: int = Query(15, ge=1, le=100)):
    """Retrieve prioritized list of monitored projects crossing operational risk threshold."""
    return early_warning_service.get_early_warning_projects(limit=limit)


@router.get("/executive-briefing")
def get_executive_monitoring_briefing():
    """Synthesize portfolio executive monitoring brief separating quantitative KPIs and RAG context."""
    return executive_briefing_service.get_executive_briefing()


@router.get("/briefing/{project_code}")
def get_single_project_briefing(project_code: str):
    """Synthesize executive briefing for a specific project."""
    risk_assessment = risk_engine_service.get_project_risk_assessment(project_code)
    if not risk_assessment:
        raise HTTPException(status_code=404, detail=f"Project code '{project_code}' not found.")
    
    meta = get_project_details(project_code) or {}
    score = risk_assessment.get("risk_score")
    score_str = f"{score:.1f}" if score is not None else "N/A"
    cat = risk_assessment.get("risk_category", "UNKNOWN")
    prob = risk_assessment.get("risk_probability")
    prob_str = f"{prob * 100:.1f}%" if prob is not None else "N/A"
    
    cost_idx = risk_assessment.get("cost_risk_index")
    cost_str = f"{cost_idx:.2f}x" if cost_idx is not None else "1.00x"
    
    sched_idx = risk_assessment.get("schedule_risk_index")
    sched_str = f"{sched_idx:.2f}" if sched_idx is not None else "0.00"

    drivers = risk_assessment.get("risk_drivers") or []
    driver_names = [d.get("feature_description") or d.get("feature_name") or str(d) if isinstance(d, dict) else str(d) for d in drivers]
    drivers_str = ", ".join(driver_names) if driver_names else "None identified"
    
    factors = risk_assessment.get("protective_factors") or []
    factor_names = [f.get("feature_description") or f.get("feature_name") or str(f) if isinstance(f, dict) else str(f) for f in factors]
    factors_str = ", ".join(factor_names) if factor_names else "None identified"

    briefing_text = (
        f"EXECUTIVE MONITORING BRIEF — PROJECT {project_code}\n\n"
        f"1. QUANTITATIVE RISK ASSESSMENT\n"
        f"- Project Name: {meta.get('name') or 'N/A'}\n"
        f"- Risk Score: {score_str}/100 ({cat})\n"
        f"- Calibrated Failure Probability: {prob_str}\n"
        f"- Cost Risk Index: {cost_str}\n"
        f"- Schedule Risk Index: {sched_str}\n\n"
        f"2. EARLY WARNING INTERVENTION\n"
        f"- Early Warning Triggered: {'YES' if risk_assessment.get('early_warning') else 'NO'}\n"
        f"- Primary Risk Drivers: {drivers_str}\n"
        f"- Protective Factors: {factors_str}\n"
    )

    return {"project_code": project_code, "executive_briefing": briefing_text, "briefing": briefing_text}

