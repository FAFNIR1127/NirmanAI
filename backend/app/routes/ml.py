"""
ml.py - REST Router for Machine Learning Model Prediction, Governance & What-If Simulation
"""

from fastapi import APIRouter, HTTPException, status
from pathlib import Path
import json

from backend.app.schemas.ml import MLPredictionRequest, MLPredictionResponse
from backend.app.services.ml_prediction_service import ml_prediction_service
from backend.app.core.logging_config import logger

router = APIRouter(prefix="/api/ml", tags=["Machine Learning"])

REPORTS_DIR = Path("/Users/sanket/SIH/NirmanAnti/reports/model_evaluation")
VERSION_DIR = Path("/Users/sanket/SIH/NirmanAnti/models/risk_engine_v2")


@router.post("/predict", response_model=MLPredictionResponse, summary="Predict Project Risk (Existing Project or What-If Simulation)")
def predict_project_risk(request: MLPredictionRequest):
    """
    Dual-mode Machine Learning inference endpoint:
    - **Mode 1 (Existing Project)**: Pass `{"project_code": "N18000419"}` to query live database, calculate retrospective deltas, and return calibrated prediction with SHAP drivers.
    - **Mode 2 (What-If Analysis)**: Pass parameters (`original_cost`, `anticipated_cost`, `physical_progress`, `months_elapsed`, etc.) to run instant counterfactual simulation.
    """
    try:
        if request.project_code:
            logger.info(f"ML Predict (Mode 1: Existing Project): {request.project_code}")
            result = ml_prediction_service.predict_existing_project(request.project_code)
        else:
            logger.info(f"ML Predict (Mode 2: What-If Analysis): Cost={request.original_cost}->{request.anticipated_cost}, Prog={request.physical_progress}%")
            result = ml_prediction_service.predict_what_if(request)
        return result
    except ValueError as ve:
        logger.warning(f"ML Predict Validation Error: {ve}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"ML Predict Internal Error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Prediction error: {str(e)}")


@router.get("/metrics", summary="Get Scientific Validation & Holdout Benchmark Metrics")
def get_model_metrics():
    """
    Returns the comprehensive scientific benchmark report on the locked 2024-2025 holdout:
    - ROC-AUC, PR-AUC, Brier Score, Brier Skill Score
    - Confusion Matrix (Operational Threshold vs Default 0.50)
    - Subgroup Dissections (by Sector, Cost Tier, Project Age)
    - Temporal Stability (2024 vs 2025)
    """
    report_file = REPORTS_DIR / "final_holdout_evaluation_report.json"
    if not report_file.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holdout evaluation report not found.")
    with open(report_file, "r") as f:
        return json.load(f)


@router.get("/model_info", summary="Get Production Model Architecture & Feature Schema")
def get_model_info():
    """
    Returns production model metadata:
    - Model Architecture (Tuned XGBoost + 5-Fold Isotonic Calibration)
    - 34 Leakage-Safe Feature Columns
    - Operational Cost-Minimizing Threshold
    - Bayesian Sector Risk Priors
    """
    schema_file = VERSION_DIR / "feature_schema.json"
    th_file = VERSION_DIR / "threshold_config.json"
    priors_file = Path("/Users/sanket/SIH/NirmanAnti/processed/features/sector_risk_priors.json")

    schema = json.load(open(schema_file)) if schema_file.exists() else {}
    th = json.load(open(th_file)) if th_file.exists() else {}
    priors = json.load(open(priors_file)) if priors_file.exists() else {}

    return {
        "model_version": "risk_engine_v2",
        "architecture": "XGBoost Classifier + 5-Fold Isotonic CalibratedClassifierCV",
        "target_definition": "target_severe_risk_12m (cost escalation >= 5% or delay growth >= 3m within 12 months)",
        "feature_count": schema.get("num_features", 34),
        "feature_columns": schema.get("feature_columns", []),
        "operational_threshold": th.get("operational_threshold", 0.25),
        "f1_optimal_threshold": th.get("f1_optimal_threshold", 0.35),
        "cost_penalty_ratio": th.get("cost_penalty_ratio", "5FN + 1FP"),
        "training_era": "2018-04 to 2023-04 (7,377 evaluable observations)",
        "locked_holdout": "2024-04 to 2025-04 (1,772 evaluable observations)",
        "sector_priors": priors
    }
