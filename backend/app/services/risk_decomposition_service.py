from typing import Dict, Any, List, Optional
from backend.app.services.risk_engine import RiskEngineService


class RiskDecompositionService:
    """Decomposes raw ML risk assessments into structured feature influence drivers and protective factors."""

    def __init__(self):
        self.risk_engine = RiskEngineService()

    def decompose_project_risk(self, project_code: str) -> Optional[Dict[str, Any]]:
        raw_assessment = self.risk_engine.get_project_risk_assessment(project_code)
        if not raw_assessment:
            return None

        drivers_raw = raw_assessment.get("risk_drivers", [])
        protective_raw = raw_assessment.get("protective_factors", [])

        primary_drivers = []
        for d in drivers_raw:
            fname = d.get("feature_name") or d.get("feature_code") or "Risk Driver"
            pts = d.get("points_added") or f"+{d.get('shap_impact', 0):.1f}"
            val = d.get("value", 0.0)
            primary_drivers.append({
                "feature_code": d.get("feature_code", ""),
                "feature_name": fname,
                "value": round(float(val), 2) if isinstance(val, (int, float)) else val,
                "points_added": pts,
                "influence_type": "RISK_DRIVER",
                "description": f"Increases model risk assessment by relative influence of {pts} points."
            })

        protective_factors = []
        for p in protective_raw:
            fname = p.get("feature_name") or p.get("feature_code") or "Protective Factor"
            pts = p.get("points_added") or f"{p.get('shap_impact', 0):.1f}"
            val = p.get("value", 0.0)
            protective_factors.append({
                "feature_code": p.get("feature_code", ""),
                "feature_name": fname,
                "value": round(float(val), 2) if isinstance(val, (int, float)) else val,
                "points_added": pts,
                "influence_type": "PROTECTIVE_FACTOR",
                "description": f"Exhibits favorable indicator behavior ({pts} relative impact)."
            })

        return {
            "project_code": raw_assessment["project_code"],
            "project_name": raw_assessment["project_name"],
            "agency": raw_assessment["agency"],
            "state": raw_assessment["state"],
            "reporting_month": raw_assessment["reporting_month"],
            "risk_score": raw_assessment["risk_score"],
            "risk_category": raw_assessment["risk_category"],
            "predicted_prob": raw_assessment["predicted_severe_risk_prob"],
            "early_warning": raw_assessment["early_warning"],
            "primary_risk_drivers": primary_drivers,
            "protective_factors": protective_factors,
            "shap_caveat_note": (
                "SHAP feature contribution points indicate relative model influence towards severe risk "
                "prediction and are not literal arithmetic additions to the 0-100 risk score."
            )
        }
