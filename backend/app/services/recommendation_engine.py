from typing import Dict, Any, List, Optional
from backend.app.services.query_service import compare_projects
from backend.app.services.risk_engine import RiskEngineService

# Configurable Monitoring Policy Parameters
RECOMMENDATION_THRESHOLDS = {
    "schedule_slippage_threshold": 0.20,     # > 20% delay ratio (2.4+ months/year)
    "cost_expansion_threshold": 1.25,        # > 1.25x original cost
    "milestone_velocity_threshold": 0.50     # < 50% milestone progress velocity
}


class PrescriptiveRecommendationEngine:
    """Generates structured, policy-grounded decision support recommendations for monitored infrastructure projects."""

    def __init__(self):
        self.risk_engine = RiskEngineService()

    def get_project_recommendations(self, project_code: str) -> Optional[Dict[str, Any]]:
        proj_list = compare_projects([project_code])
        if not proj_list:
            return None

        p = proj_list[0]
        risk_info = self.risk_engine.get_project_risk_assessment(project_code) or {}

        cost_exp = float(p.get("cost_expansion_ratio") or 1.0) if p.get("cost_expansion_ratio") else (
            float(p["latest_anticipated_cost"] / p["original_cost"]) if (p.get("original_cost") and p.get("latest_anticipated_cost") and p["original_cost"] > 0) else 1.0
        )
        
        delay_m = float(p.get("delay_months") or 0.0)
        orig_cost = float(p.get("original_cost") or 0.0)
        sched_ratio = delay_m / 12.0 if orig_cost > 0 else (delay_m / 24.0)

        recommendations = []

        # 1. Schedule Slippage Policy Trigger
        t_sched = RECOMMENDATION_THRESHOLDS["schedule_slippage_threshold"]
        if sched_ratio >= t_sched or delay_m >= 6.0:
            recommendations.append({
                "recommendation_code": "SCHEDULE_ACCELERATION_REVIEW",
                "triggered": True,
                "severity": "HIGH" if delay_m >= 12.0 else "MEDIUM",
                "trigger_conditions": [
                    {"feature": "schedule_slippage_ratio", "value": round(sched_ratio, 2), "threshold": t_sched},
                    {"feature": "delay_months", "value": round(delay_m, 1), "threshold": 6.0}
                ],
                "rationale": f"Observed schedule delay ({delay_m:.1f} months) exceeds the configured policy monitoring threshold ({t_sched*100:.0f}% slippage).",
                "recommended_review": "Conduct schedule acceleration review, assess critical path dependencies, and inspect contractor site deployment."
            })

        # 2. Cost Overrun Baseline Audit Policy Trigger
        t_cost = RECOMMENDATION_THRESHOLDS["cost_expansion_threshold"]
        if cost_exp >= t_cost:
            recommendations.append({
                "recommendation_code": "COST_BASELINE_REAUDIT",
                "triggered": True,
                "severity": "CRITICAL" if cost_exp >= 1.5 else "HIGH",
                "trigger_conditions": [
                    {"feature": "cost_expansion_ratio", "value": round(cost_exp, 2), "threshold": t_cost}
                ],
                "rationale": f"Anticipated cost expansion ratio ({cost_exp:.2f}x original cost) exceeds the policy threshold ({t_cost:.2f}x).",
                "recommended_review": "Initiate cost baseline re-audit, verify expenditure authorization, and evaluate scope expansion requests."
            })

        # 3. Expenditure & Milestone Tracking Policy Trigger
        if risk_info.get("risk_category") in ["MODERATE", "HIGH", "CRITICAL"] or (risk_info.get("risk_score") and risk_info.get("risk_score") >= 28.0):
            recommendations.append({
                "recommendation_code": "MILESTONE_VELOCITY_TRACKING",
                "triggered": True,
                "severity": "HIGH" if risk_info.get("risk_category") in ["HIGH", "CRITICAL"] else "MEDIUM",
                "trigger_conditions": [
                    {"feature": "risk_score", "value": risk_info.get("risk_score"), "threshold": 28.0}
                ],
                "rationale": f"Project categorized under {risk_info.get('risk_category')} risk by ML Risk Engine v1 (Score: {risk_info.get('risk_score')}/100).",
                "recommended_review": "Enforce bi-weekly milestone progress tracking and require monthly physical progress verification reports."
            })

        return {
            "project_code": project_code,
            "project_name": p.get("project_name"),
            "agency": p.get("agency"),
            "state": p.get("state"),
            "risk_score": risk_info.get("risk_score"),
            "risk_category": risk_info.get("risk_category"),
            "total_active_recommendations": len(recommendations),
            "recommendations": recommendations,
            "policy_parameters": RECOMMENDATION_THRESHOLDS,
            "policy_disclaimer": "Recommendations are decision support advisories grounded in configured monitoring policy thresholds."
        }
