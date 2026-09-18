"""
update_database_risk_scores_v2.py

Generates calibrated risk scores and SHAP drivers across all 16,650 project observations
using the newly trained Risk Engine v2 and updates both PostgreSQL and SQLite.
"""

from pathlib import Path
import json
import pandas as pd
import numpy as np
import joblib
import sqlalchemy
import sqlite3
import shap

ROOT_DIR = Path("/Users/sanket/SIH/NirmanAnti")
DATA_DIR = ROOT_DIR / "processed" / "features"
VERSION_DIR = ROOT_DIR / "models" / "risk_engine_v2"
SQLITE_PATH = ROOT_DIR / "database" / "nirman.db"
PG_DSN = "postgresql://postgres:hulk@localhost:5432/nirman_db"

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


def run_update():
    print("=== INGESTING RISK ENGINE V2 PREDICTIONS INTO DATABASE ===")
    full_path = DATA_DIR / "ml_features_leakage_safe.parquet"
    df = pd.read_parquet(full_path)
    print(f"Loaded {len(df)} total project observations.")

    with open(VERSION_DIR / "feature_schema.json") as f:
        schema = json.load(f)
    feature_cols = schema["feature_columns"]

    agency_le = joblib.load(VERSION_DIR / "agency_encoder.joblib")
    state_le = joblib.load(VERSION_DIR / "state_encoder.joblib")
    imputer = joblib.load(VERSION_DIR / "imputer.joblib")
    base_model = joblib.load(VERSION_DIR / "xgboost_base.joblib")
    calibrator = joblib.load(VERSION_DIR / "calibrator.joblib")

    # Encode
    known_agencies = set(agency_le.classes_)
    known_states = set(state_le.classes_)
    df["agency_clean"] = df["agency"].astype(str).apply(lambda x: x if x in known_agencies else "Unknown")
    df["state_clean"] = df["state"].astype(str).apply(lambda x: x if x in known_states else "Unknown")
    df["agency_encoded"] = agency_le.transform(df["agency_clean"])
    df["state_encoded"] = state_le.transform(df["state_clean"])

    X = df[feature_cols]
    X_imp = imputer.transform(X)
    X_df = pd.DataFrame(X_imp, columns=feature_cols)

    # Predict
    print("Computing calibrated probabilities...")
    cal_probs = calibrator.predict_proba(X_df)[:, 1]

    print("Computing Tree SHAP drivers across all observations...")
    explainer = shap.TreeExplainer(base_model)
    shap_matrix = explainer.shap_values(X_df)

    print("Formatting drivers...")
    combined_drivers_json = []
    for i in range(len(df)):
        s_row = shap_matrix[i]
        items = sorted(zip(feature_cols, s_row), key=lambda x: x[1], reverse=True)
        pos = [
            {"feature": f, "attribution": round(float(v), 4), "impact": f"{FEATURE_LABEL_MAP.get(f, f)} (+{float(v):.3f})"}
            for f, v in items if v > 0
        ][:3]
        combined_drivers_json.append(json.dumps(pos))

    df["predicted_severe_risk_prob"] = np.round(cal_probs, 4)
    df["risk_score"] = (cal_probs * 100.0).round(1)
    df["risk_category"] = np.where(cal_probs >= 0.45, "HIGH", np.where(cal_probs >= 0.25, "MODERATE", "LOW"))
    df["cost_risk_index"] = ((df["cost_expansion_ratio"].fillna(1.0).clip(1.0, 5.0) - 1.0) / 4.0 * 100.0).round(2)
    df["schedule_risk_index"] = ((df["schedule_slippage_ratio"].fillna(0.0).clip(0.0, 5.0)) / 5.0 * 100.0).round(2)

    records = pd.DataFrame({
        "project_code": df["project_code"],
        "reporting_month": df["reporting_month"],
        "risk_score": df["risk_score"],
        "risk_category": df["risk_category"],
        "schedule_risk_index": df["schedule_risk_index"],
        "cost_risk_index": df["cost_risk_index"],
        "predicted_severe_risk_prob": df["predicted_severe_risk_prob"],
        "key_risk_drivers": combined_drivers_json
    })

    # Save to parquet for reference
    records.to_parquet(DATA_DIR / "risk_scores.parquet", index=False)

    # Ingest into SQLite
    print("Writing to SQLite database/nirman.db...")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    records.to_sql("risk_scores", sqlite_conn, if_exists="replace", index=False)
    sqlite_conn.commit()
    sqlite_conn.close()
    print("SQLite risk_scores updated successfully.")

    # Ingest to PostgreSQL
    print("Writing to PostgreSQL nirman_db...")
    pg_engine = sqlalchemy.create_engine(PG_DSN)
    with pg_engine.begin() as conn:
        conn.execute(sqlalchemy.text("DROP TABLE IF EXISTS risk_scores CASCADE;"))
        conn.execute(sqlalchemy.text("""
            CREATE TABLE risk_scores (
                id SERIAL PRIMARY KEY,
                project_code VARCHAR(50) NOT NULL REFERENCES projects(project_code) ON DELETE CASCADE,
                reporting_month VARCHAR(10) NOT NULL,
                risk_score NUMERIC(5,2),
                risk_category VARCHAR(20),
                schedule_risk_index NUMERIC(5,2),
                cost_risk_index NUMERIC(5,2),
                predicted_severe_risk_prob NUMERIC(6,4),
                key_risk_drivers JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX idx_risk_scores_project_month ON risk_scores(project_code, reporting_month);
            CREATE INDEX idx_risk_scores_category ON risk_scores(risk_category);
        """))
        records.to_sql("risk_scores", conn, if_exists="append", index=False)
    print("PostgreSQL risk_scores updated successfully.")


if __name__ == "__main__":
    run_update()
