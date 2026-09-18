"""
ml_prediction_service.py

Production-grade Machine Learning inference service for Project Nirman.
Supports:
1. Mode 1 (Existing Project): Queries live database, reconstructs feature vector with retrospective deltas, runs calibrated pipeline, returns prediction + SHAP drivers.
2. Mode 2 (What-If Analysis): Accepts arbitrary project parameters, calculates dynamic ratios, runs calibrated pipeline, returns instant counterfactual prediction + SHAP drivers.
"""

from pathlib import Path
import json
import time
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import joblib
import sqlalchemy
import shap

from backend.app.config import DATABASE_URL, FALLBACK_SQLITE_PATH
from backend.app.schemas.ml import MLPredictionRequest, MLPredictionResponse, RiskDriver
from backend.app.core.logging_config import logger

VERSION_DIR = Path("/Users/sanket/SIH/NirmanAnti/models/risk_engine_v2")
PRIORS_PATH = Path("/Users/sanket/SIH/NirmanAnti/processed/features/sector_risk_priors.json")

# Human-readable labels for features
FEATURE_LABEL_MAP = {
    "delta_expenditure": "Monthly Spending Velocity / Flux",
    "elapsed_ratio": "Elapsed Project Duration vs Planned Timeline",
    "required_progress_velocity": "Required Monthly Construction Pace",
    "sector_historical_risk": "Sectoral Historical Disruption Rate",
    "revised_cost": "Sanctioned Budget Revision Scale",
    "months_elapsed": "Total Elapsed Project Age",
    "months_remaining": "Contractual Remaining Runway",
    "months_originally_planned": "Original Baseline Schedule Length",
    "agency_encoded": "Implementing Agency Structural Track Record",
    "expenditure_ratio": "Cumulative Fund Utilization Ratio",
    "expenditure_burn_rate": "Historical Capital Outlay Burn Rate",
    "cumulative_expenditure": "Cumulative Capital Expended",
    "original_delay_months": "Accumulated Milestone Delay",
    "required_spend_rate_monthly": "Required Monthly Capital Inflow",
    "delay_months": "Active Schedule Slip",
    "cost_expansion_ratio": "Total Cost Escalation Multiplier",
    "schedule_slippage_ratio": "Relative Delay vs Sanctioned Scope",
    "physical_progress": "Verified Physical Progress",
    "cost_overrun_velocity": "Cost Growth Velocity per Elapsed Month",
    "interaction_slippage_cost": "Compounded Delay-Escalation Interaction",
    "delta_anticipated_cost": "Recent Budget Adjustment Acceleration",
    "delta_delay_months": "Recent Delay Acceleration",
    "delta_physical_progress": "Recent Progress Acceleration",
    "remaining_funds_ratio": "Proportion of Anticipated Budget Unspent",
    "milestone_rate": "Milestone Completion Ratio"
}


class MLPredictionService:
    def __init__(self):
        self._load_artifacts()

    def _load_artifacts(self):
        try:
            with open(VERSION_DIR / "feature_schema.json") as f:
                self.schema = json.load(f)
            self.feature_cols = self.schema["feature_columns"]
            self.num_features = len(self.feature_cols)

            with open(VERSION_DIR / "threshold_config.json") as f:
                self.th_config = json.load(f)
            self.operational_threshold = float(self.th_config.get("operational_threshold", 0.25))

            with open(PRIORS_PATH) as f:
                self.sector_priors = json.load(f)

            self.agency_le = joblib.load(VERSION_DIR / "agency_encoder.joblib")
            self.state_le = joblib.load(VERSION_DIR / "state_encoder.joblib")
            self.imputer = joblib.load(VERSION_DIR / "imputer.joblib")
            self.base_model = joblib.load(VERSION_DIR / "xgboost_base.joblib")
            self.calibrator = joblib.load(VERSION_DIR / "calibrator.joblib")

            # Tree SHAP Explainer
            self.explainer = shap.TreeExplainer(self.base_model)
            logger.info("✅ MLPredictionService initialized successfully with locked Risk Engine v2 artifacts.")
        except Exception as e:
            logger.error(f"Failed to initialize MLPredictionService: {e}")
            raise

    def get_db_engine(self):
        try:
            engine = sqlalchemy.create_engine(DATABASE_URL)
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("SELECT 1"))
            return engine
        except Exception:
            return sqlalchemy.create_engine(f"sqlite:///{FALLBACK_SQLITE_PATH}")

    def _encode_category(self, encoder, val: Optional[str]) -> int:
        clean_val = str(val) if val else "Unknown"
        if clean_val in encoder.classes_:
            return int(encoder.transform([clean_val])[0])
        elif "Unknown" in encoder.classes_:
            return int(encoder.transform(["Unknown"])[0])
        else:
            return 0

    def _get_sector_risk(self, sector: Optional[str]) -> float:
        if not sector:
            return float(self.sector_priors.get("global_prior", 0.3348))
        return float(self.sector_priors.get("sectors", {}).get(sector, self.sector_priors.get("global_prior", 0.3348)))

    def predict_existing_project(self, project_code: str) -> Dict[str, Any]:
        engine = self.get_db_engine()
        query = """
            SELECT 
                p.project_code, p.project_name, p.sector, p.agency, p.state, p.original_cost::float,
                o.reporting_month, o.original_doc, o.revised_doc, o.anticipated_doc,
                o.revised_cost::float, o.anticipated_cost::float, o.cumulative_expenditure::float,
                o.physical_progress::float, o.original_delay_months::float, o.revised_delay_months::float,
                o.milestones_achieved, o.milestones_total
            FROM projects p
            JOIN project_observations o ON p.project_code = o.project_code
            WHERE p.project_code = :code
            ORDER BY o.reporting_month DESC
            LIMIT 2;
        """
        with engine.connect() as conn:
            df = pd.read_sql(sqlalchemy.text(query), conn, params={"code": project_code})

        if df.empty:
            raise ValueError(f"Project code '{project_code}' not found in database.")

        latest = df.iloc[0]
        prev = df.iloc[1] if len(df) > 1 else None

        # Feature construction
        features = {}
        features["original_cost"] = float(latest["original_cost"]) if pd.notna(latest["original_cost"]) else 100.0
        features["revised_cost"] = float(latest["revised_cost"]) if pd.notna(latest["revised_cost"]) else features["original_cost"]
        features["anticipated_cost"] = float(latest["anticipated_cost"]) if pd.notna(latest["anticipated_cost"]) else features["original_cost"]
        features["cumulative_expenditure"] = float(latest["cumulative_expenditure"]) if pd.notna(latest["cumulative_expenditure"]) else 0.0
        features["physical_progress"] = float(latest["physical_progress"]) if pd.notna(latest["physical_progress"]) else 0.0
        features["original_delay_months"] = float(latest["original_delay_months"]) if pd.notna(latest["original_delay_months"]) else 0.0
        features["revised_delay_months"] = float(latest["revised_delay_months"]) if pd.notna(latest["revised_delay_months"]) else 0.0
        features["milestones_achieved"] = float(latest["milestones_achieved"]) if pd.notna(latest["milestones_achieved"]) else 0.0
        features["milestones_total"] = float(latest["milestones_total"]) if pd.notna(latest["milestones_total"]) else 0.0

        # Durations
        # Parse Dates
        dt_rep = pd.to_datetime(str(latest["reporting_month"]) + "-01")
        dt_orig_doc = pd.to_datetime(str(latest["original_doc"]) + "-01", errors="coerce")
        dt_ant_doc = pd.to_datetime(str(latest["anticipated_doc"]) + "-01", errors="coerce")
        
        # Approximations if dates missing
        features["months_elapsed"] = 36.0
        features["months_originally_planned"] = 48.0
        features["months_remaining"] = 12.0
        if pd.notna(dt_ant_doc):
            features["months_remaining"] = max(1.0, (dt_ant_doc - dt_rep).days / 30.4375)

        # Derived metrics
        safe_planned = max(1.0, features["months_originally_planned"])
        safe_elapsed = max(1.0, features["months_elapsed"])
        safe_remaining = max(1.0, features["months_remaining"])

        features["cost_expansion_ratio"] = min(50.0, max(0.1, features["anticipated_cost"] / max(1.0, features["original_cost"])))
        features["expenditure_ratio"] = min(1.5, max(0.0, features["cumulative_expenditure"] / max(1.0, features["anticipated_cost"])))
        features["expenditure_progress_gap"] = features["expenditure_ratio"] - (features["physical_progress"] / 100.0)
        features["delay_months"] = features["original_delay_months"]
        features["schedule_slippage_ratio"] = min(20.0, max(-1.0, features["delay_months"] / safe_planned))
        features["elapsed_ratio"] = min(20.0, features["months_elapsed"] / safe_planned)
        features["cost_overrun_velocity"] = (features["anticipated_cost"] - features["original_cost"]) / safe_elapsed
        features["expenditure_burn_rate"] = features["cumulative_expenditure"] / safe_elapsed
        features["remaining_funds_ratio"] = (features["anticipated_cost"] - features["cumulative_expenditure"]) / max(1.0, features["anticipated_cost"])
        features["required_spend_rate_monthly"] = max(0.0, features["anticipated_cost"] - features["cumulative_expenditure"]) / safe_remaining
        features["required_progress_velocity"] = max(0.0, 100.0 - features["physical_progress"]) / safe_remaining
        features["progress_velocity"] = features["physical_progress"] / safe_elapsed
        features["milestone_rate"] = features["milestones_achieved"] / max(1.0, features["milestones_total"]) if features["milestones_total"] > 0 else 0.0

        features["interaction_slippage_cost"] = features["schedule_slippage_ratio"] * features["cost_expansion_ratio"]
        features["interaction_gap_velocity"] = features["expenditure_progress_gap"] * features["progress_velocity"]

        # Deltas
        if prev is not None:
            features["delta_anticipated_cost"] = features["anticipated_cost"] - (float(prev["anticipated_cost"]) if pd.notna(prev["anticipated_cost"]) else features["anticipated_cost"])
            features["delta_delay_months"] = features["delay_months"] - (float(prev["original_delay_months"]) if pd.notna(prev["original_delay_months"]) else features["delay_months"])
            features["delta_expenditure"] = features["cumulative_expenditure"] - (float(prev["cumulative_expenditure"]) if pd.notna(prev["cumulative_expenditure"]) else features["cumulative_expenditure"])
            features["delta_physical_progress"] = features["physical_progress"] - (float(prev["physical_progress"]) if pd.notna(prev["physical_progress"]) else features["physical_progress"])
        else:
            features["delta_anticipated_cost"] = 0.0
            features["delta_delay_months"] = 0.0
            features["delta_expenditure"] = 0.0
            features["delta_physical_progress"] = 0.0

        features["sector_historical_risk"] = self._get_sector_risk(latest.get("sector"))
        features["agency_encoded"] = self._encode_category(self.agency_le, latest.get("agency"))
        features["state_encoded"] = self._encode_category(self.state_le, latest.get("state"))

        project_name = str(latest["project_name"]) if pd.notna(latest["project_name"]) else project_code
        return self._run_inference(features, mode="existing_project", project_code=project_code, project_name=project_name)

    def predict_what_if(self, req: MLPredictionRequest) -> Dict[str, Any]:
        features = {}
        features["original_cost"] = float(req.original_cost)
        features["revised_cost"] = float(req.revised_cost) if req.revised_cost is not None else features["original_cost"]
        features["anticipated_cost"] = float(req.anticipated_cost) if req.anticipated_cost is not None else features["original_cost"]
        features["cumulative_expenditure"] = float(req.cumulative_expenditure) if req.cumulative_expenditure is not None else 0.0
        features["physical_progress"] = float(req.physical_progress) if req.physical_progress is not None else 0.0
        features["original_delay_months"] = float(req.delay_months) if req.delay_months is not None else 0.0
        features["revised_delay_months"] = float(req.delay_months) if req.delay_months is not None else 0.0
        features["milestones_achieved"] = 0.0
        features["milestones_total"] = 0.0

        features["months_elapsed"] = float(req.months_elapsed) if req.months_elapsed is not None else 24.0
        features["months_originally_planned"] = float(req.months_originally_planned) if req.months_originally_planned is not None else 36.0
        features["months_remaining"] = float(req.months_remaining) if req.months_remaining is not None else 12.0
        features["delay_months"] = features["original_delay_months"]

        safe_planned = max(1.0, features["months_originally_planned"])
        safe_elapsed = max(1.0, features["months_elapsed"])
        safe_remaining = max(1.0, features["months_remaining"])

        features["cost_expansion_ratio"] = min(50.0, max(0.1, features["anticipated_cost"] / max(1.0, features["original_cost"])))
        features["expenditure_ratio"] = min(1.5, max(0.0, features["cumulative_expenditure"] / max(1.0, features["anticipated_cost"])))
        features["expenditure_progress_gap"] = features["expenditure_ratio"] - (features["physical_progress"] / 100.0)
        features["schedule_slippage_ratio"] = min(20.0, max(-1.0, features["delay_months"] / safe_planned))
        features["elapsed_ratio"] = min(20.0, features["months_elapsed"] / safe_planned)
        features["cost_overrun_velocity"] = (features["anticipated_cost"] - features["original_cost"]) / safe_elapsed
        features["expenditure_burn_rate"] = features["cumulative_expenditure"] / safe_elapsed
        features["remaining_funds_ratio"] = (features["anticipated_cost"] - features["cumulative_expenditure"]) / max(1.0, features["anticipated_cost"])
        features["required_spend_rate_monthly"] = max(0.0, features["anticipated_cost"] - features["cumulative_expenditure"]) / safe_remaining
        features["required_progress_velocity"] = max(0.0, 100.0 - features["physical_progress"]) / safe_remaining
        features["progress_velocity"] = features["physical_progress"] / safe_elapsed
        features["milestone_rate"] = 0.0

        features["interaction_slippage_cost"] = features["schedule_slippage_ratio"] * features["cost_expansion_ratio"]
        features["interaction_gap_velocity"] = features["expenditure_progress_gap"] * features["progress_velocity"]

        # What-if defaults for deltas (steady state)
        features["delta_anticipated_cost"] = 0.0
        features["delta_delay_months"] = 0.0
        features["delta_expenditure"] = features["expenditure_burn_rate"] * 1.0
        features["delta_physical_progress"] = features["progress_velocity"] * 1.0

        features["sector_historical_risk"] = self._get_sector_risk(req.sector)
        features["agency_encoded"] = self._encode_category(self.agency_le, req.agency)
        features["state_encoded"] = self._encode_category(self.state_le, req.state)

        return self._run_inference(features, mode="what_if_analysis", project_code=None, project_name="Simulated Project Scenario")

    def _run_inference(self, feature_dict: Dict[str, float], mode: str, project_code: Optional[str], project_name: Optional[str]) -> Dict[str, Any]:
        t0 = time.perf_counter()

        # Build ordered vector
        row = [feature_dict.get(c, 0.0) for c in self.feature_cols]
        input_df = pd.DataFrame([row], columns=self.feature_cols)

        # Impute
        input_imp = self.imputer.transform(input_df)
        input_imp_df = pd.DataFrame(input_imp, columns=self.feature_cols)

        # Calibrated prediction
        prob = float(self.calibrator.predict_proba(input_imp_df)[0, 1])
        risk_score = round(prob * 100.0, 1)

        # Operational threshold check
        is_severe_risk = bool(prob >= self.operational_threshold)

        if prob >= 0.45:
            risk_tier = "High"
        elif prob >= 0.25:
            risk_tier = "Moderate"
        else:
            risk_tier = "Low"

        # SHAP calculation
        shap_vals = self.explainer.shap_values(input_imp_df)[0]
        
        # Sort contributors
        contributors = []
        for feat, val in zip(self.feature_cols, shap_vals):
            contributors.append({
                "feature": feat,
                "label": FEATURE_LABEL_MAP.get(feat, feat),
                "attribution": float(val)
            })

        risk_drivers = [
            RiskDriver(
                feature=c["feature"],
                attribution=round(c["attribution"], 4),
                description=f"{c['label']} elevates risk attribution by +{c['attribution']:.3f}"
            )
            for c in sorted(contributors, key=lambda x: x["attribution"], reverse=True)
            if c["attribution"] > 0
        ][:3]

        protective_factors = [
            RiskDriver(
                feature=c["feature"],
                attribution=round(c["attribution"], 4),
                description=f"{c['label']} acts as a risk stabilizer by {c['attribution']:.3f}"
            )
            for c in sorted(contributors, key=lambda x: x["attribution"])
            if c["attribution"] < 0
        ][:3]

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return {
            "mode": mode,
            "project_code": project_code,
            "project_name": project_name,
            "predicted_risk_probability": round(prob, 4),
            "risk_score": risk_score,
            "risk_tier": risk_tier,
            "is_severe_risk_alert": is_severe_risk,
            "operational_threshold": self.operational_threshold,
            "confidence_assessment": f"Isotonic probability: {prob:.2%} (Decision bound: >= {self.operational_threshold:.0%})",
            "key_risk_drivers": [d.model_dump() for d in risk_drivers],
            "protective_factors": [d.model_dump() for d in protective_factors],
            "inference_latency_ms": latency_ms
        }


ml_prediction_service = MLPredictionService()
