import json
import shutil
from pathlib import Path
import joblib

# ============================================================
# PATHS & CONFIG
# ============================================================

SOURCE_MODELS_DIR = Path("models")
TARGET_VERSION_DIR = SOURCE_MODELS_DIR / "risk_engine_v1"
TARGET_VERSION_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_SCHEMA = {
    "features": [
        {"name": "original_cost", "type": "float", "description": "Original Approved Cost (₹ Crore)"},
        {"name": "revised_cost", "type": "float", "description": "Revised Approved Cost (₹ Crore)"},
        {"name": "anticipated_cost", "type": "float", "description": "Anticipated Completion Cost (₹ Crore)"},
        {"name": "cumulative_expenditure", "type": "float", "description": "Cumulative Expenditure to Date (₹ Crore)"},
        {"name": "physical_progress", "type": "float", "description": "Physical Progress Percentage (0-100%)"},
        {"name": "original_delay_months", "type": "float", "description": "Schedule Delay relative to Original DOC (Months)"},
        {"name": "revised_delay_months", "type": "float", "description": "Schedule Delay relative to Revised DOC (Months)"},
        {"name": "milestones_achieved", "type": "float", "description": "Milestones Achieved Count"},
        {"name": "milestones_total", "type": "float", "description": "Total Scheduled Milestones Count"},
        {"name": "months_elapsed", "type": "float", "description": "Months Elapsed since Project Approval"},
        {"name": "months_originally_planned", "type": "float", "description": "Originally Planned Project Duration (Months)"},
        {"name": "months_remaining", "type": "float", "description": "Months Remaining to Anticipated DOC"},
        {"name": "cost_expansion_ratio", "type": "float", "description": "Anticipated Cost / Original Cost Ratio"},
        {"name": "expenditure_ratio", "type": "float", "description": "Cumulative Expenditure / Anticipated Cost Ratio"},
        {"name": "expenditure_progress_gap", "type": "float", "description": "Expenditure Ratio - Physical Progress Ratio Gap"},
        {"name": "delay_months", "type": "float", "description": "Anticipated Delay Duration (Months)"},
        {"name": "schedule_slippage_ratio", "type": "float", "description": "Delay Months / Originally Planned Duration Ratio"},
        {"name": "milestone_rate", "type": "float", "description": "Milestones Achieved / Total Milestones Ratio"},
        {"name": "progress_velocity", "type": "float", "description": "Monthly Rate of Physical Execution Progress (%/Month)"},
        {"name": "agency_encoded", "type": "int", "description": "Implementing Agency Categorical Encoding"},
        {"name": "state_encoded", "type": "int", "description": "State Location Categorical Encoding"}
    ]
}

MODEL_METADATA = {
    "model_version": "risk_engine_v1",
    "model_architecture": "XGBoost Classifier + 5-Fold Sigmoid CalibratedClassifierCV",
    "target_variable": "target_severe_risk_12m",
    "prediction_horizon_months": 12,
    "calibration_method": "sigmoid_platt_scaling",
    "operational_threshold": 0.28,
    "training_period": "2018-04 to 2023-04",
    "validation_period": "2024-04 to 2025-04",
    "evaluable_train_samples": 6543,
    "evaluable_val_samples": 939,
    "metrics_untouched_holdout": {
        "accuracy": 0.6837,
        "precision": 0.3333,
        "recall_at_optimal_threshold": 0.6612,
        "f1_score_at_optimal_threshold": 0.3846,
        "roc_auc": 0.5464,
        "pr_auc": 0.3077,
        "brier_score_loss": 0.2080
    }
}

THRESHOLD_CONFIG = {
    "optimal_operational_threshold": 0.28,
    "default_classification_threshold": 0.50,
    "risk_categories": {
        "LOW": {"min_score": 0.0, "max_score": 30.0, "color": "#10B981"},
        "MODERATE": {"min_score": 30.1, "max_score": 60.0, "color": "#F59E0B"},
        "HIGH": {"min_score": 60.1, "max_score": 80.0, "color": "#F97316"},
        "CRITICAL": {"min_score": 80.1, "max_score": 100.0, "color": "#EF4444"}
    }
}


def package_model():
    print("=== PACKAGING MODEL ARTIFACTS INTO `models/risk_engine_v1` ===")

    # Copy XGBoost base model
    shutil.copy(SOURCE_MODELS_DIR / "tuned_xgb_base.joblib", TARGET_VERSION_DIR / "xgboost_model.joblib")
    
    # Save Calibrator
    shutil.copy(SOURCE_MODELS_DIR / "tuned_xgb_calibrated.joblib", TARGET_VERSION_DIR / "calibrator.pkl")

    # Save schemas and metadata
    with open(TARGET_VERSION_DIR / "feature_schema.json", "w") as f:
        json.dump(FEATURE_SCHEMA, f, indent=2)

    with open(TARGET_VERSION_DIR / "threshold.json", "w") as f:
        json.dump(THRESHOLD_CONFIG, f, indent=2)

    with open(TARGET_VERSION_DIR / "model_metadata.json", "w") as f:
        json.dump(MODEL_METADATA, f, indent=2)

    print(f"Successfully packaged model version 1 into `{TARGET_VERSION_DIR}`:")
    for path in TARGET_VERSION_DIR.glob("*"):
        print(f"  • {path.name}")


if __name__ == "__main__":
    package_model()
