import json
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
import sqlite3
import sqlalchemy
import shap
from sklearn.preprocessing import LabelEncoder

# ============================================================
# PATHS
# ============================================================

DATA_DIR = Path("processed/features")
ALL_FEATURES_PATH = DATA_DIR / "ml_features.parquet"
MODELS_DIR = Path("models")

FEATURE_COLS = [
    'original_cost', 'revised_cost', 'anticipated_cost', 'cumulative_expenditure',
    'physical_progress', 'original_delay_months', 'revised_delay_months',
    'milestones_achieved', 'milestones_total', 'months_elapsed',
    'months_originally_planned', 'months_remaining', 'cost_expansion_ratio',
    'expenditure_ratio', 'expenditure_progress_gap', 'delay_months',
    'schedule_slippage_ratio', 'milestone_rate', 'progress_velocity',
    'agency_encoded', 'state_encoded'
]

# Readable Feature Name Mappings for UI and LLM Prompt Context
FEATURE_DISPLAY_NAMES = {
    'cost_expansion_ratio': 'Cost Expansion Ratio',
    'schedule_slippage_ratio': 'Schedule Slippage Ratio',
    'delay_months': 'Project Delay (Months)',
    'expenditure_ratio': 'Expenditure Ratio',
    'expenditure_progress_gap': 'Expenditure vs Progress Gap',
    'progress_velocity': 'Physical Progress Velocity',
    'months_remaining': 'Months Remaining',
    'months_elapsed': 'Months Elapsed',
    'months_originally_planned': 'Originally Planned Duration',
    'original_cost': 'Original Project Cost',
    'anticipated_cost': 'Anticipated Project Cost',
    'cumulative_expenditure': 'Cumulative Expenditure',
    'physical_progress': 'Physical Progress (%)',
    'milestone_rate': 'Milestone Completion Rate',
    'milestones_achieved': 'Milestones Achieved',
    'milestones_total': 'Total Milestones Scheduled',
    'original_delay_months': 'Original Delay (Months)',
    'revised_delay_months': 'Revised Delay (Months)',
    'agency_encoded': 'Implementing Agency Baseline Risk',
    'state_encoded': 'State Location Baseline Risk'
}


def build_shap_risk_engine():
    all_df = pd.read_parquet(ALL_FEATURES_PATH)
    base_model = joblib.load(MODELS_DIR / "tuned_xgb_base.joblib")
    calibrated_model = joblib.load(MODELS_DIR / "tuned_xgb_calibrated.joblib")

    # Encode categoricals
    agency_le = LabelEncoder()
    state_le = LabelEncoder()
    all_df['agency_encoded'] = agency_le.fit_transform(all_df['agency'].astype(str).fillna('Unknown'))
    all_df['state_encoded'] = state_le.fit_transform(all_df['state'].astype(str).fillna('Unknown'))

    X_all = all_df[FEATURE_COLS]

    # Calculate TreeSHAP values
    explainer = shap.TreeExplainer(base_model)
    shap_values = explainer.shap_values(X_all)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    # Calibrated probabilities P(Severe Risk within 12M)
    all_cal_probs = calibrated_model.predict_proba(X_all)[:, 1]
    composite_risk_scores = np.round(all_cal_probs * 100.0, 1)

    def assign_risk_category(score):
        if score <= 30.0:
            return "LOW"
        elif score <= 60.0:
            return "MODERATE"
        elif score <= 80.0:
            return "HIGH"
        else:
            return "CRITICAL"

    risk_categories = [assign_risk_category(s) for s in composite_risk_scores]

    # Sub-indices
    slippage_scaled = np.nan_to_num(all_df['schedule_slippage_ratio'].values, nan=0.0)
    schedule_index = np.clip(np.round(slippage_scaled * 30.0 + composite_risk_scores * 0.7, 1), 0.0, 100.0)

    cost_expansion_scaled = np.nan_to_num(all_df['cost_expansion_ratio'].values - 1.0, nan=0.0)
    cost_index = np.clip(np.round(cost_expansion_scaled * 40.0 + composite_risk_scores * 0.6, 1), 0.0, 100.0)

    top_drivers_list = []
    protective_factors_list = []

    for i in range(len(all_df)):
        row_shap = shap_values[i]

        # 1. Top Risk Drivers (Highest Positive SHAP Values -> Pushing Risk Up)
        pos_indices = np.where(row_shap > 0)[0]
        pos_sorted = pos_indices[np.argsort(row_shap[pos_indices])[::-1]] if len(pos_indices) > 0 else np.argsort(row_shap)[::-1][:3]
        
        drivers = []
        for idx in pos_sorted[:3]:
            feat_name = FEATURE_COLS[idx]
            disp_name = FEATURE_DISPLAY_NAMES.get(feat_name, feat_name)
            impact_score = round(float(row_shap[idx] * 100.0), 1) # Scaled to points
            raw_val = float(X_all.iloc[i, idx]) if pd.notna(X_all.iloc[i, idx]) else None
            drivers.append({
                "feature_name": disp_name,
                "feature_code": feat_name,
                "points_added": f"+{impact_score:.1f}",
                "value": raw_val
            })
        top_drivers_list.append(json.dumps(drivers))

        # 2. Protective Factors (Lowest Negative SHAP Values -> Pulling Risk Down)
        neg_indices = np.where(row_shap < 0)[0]
        neg_sorted = neg_indices[np.argsort(row_shap[neg_indices])] if len(neg_indices) > 0 else []
        
        protective = []
        for idx in neg_sorted[:3]:
            feat_name = FEATURE_COLS[idx]
            disp_name = FEATURE_DISPLAY_NAMES.get(feat_name, feat_name)
            impact_score = round(float(abs(row_shap[idx]) * 100.0), 1) # Scaled to points
            raw_val = float(X_all.iloc[i, idx]) if pd.notna(X_all.iloc[i, idx]) else None
            protective.append({
                "feature_name": disp_name,
                "feature_code": feat_name,
                "points_reduced": f"-{impact_score:.1f}",
                "value": raw_val
            })
        protective_factors_list.append(json.dumps(protective))

    risk_scores_df = pd.DataFrame({
        "project_code": all_df["project_code"],
        "reporting_month": all_df["reporting_month"],
        "risk_score": composite_risk_scores,
        "risk_category": risk_categories,
        "schedule_risk_index": schedule_index,
        "cost_risk_index": cost_index,
        "predicted_severe_risk_prob": np.round(all_cal_probs, 4),
        "key_risk_drivers": top_drivers_list,
        "protective_factors": protective_factors_list
    })

    # Save to Parquet
    risk_scores_df.to_parquet("processed/features/risk_scores.parquet", index=False)
    print("Saved `processed/features/risk_scores.parquet` with drivers & protective factors!")

    # Ingest into SQLite
    try:
        conn = sqlite3.connect("database/nirman.db")
        risk_scores_df.to_sql("risk_scores", conn, if_exists="replace", index=False)
        conn.close()
        print("Updated SQLite `database/nirman.db` table `risk_scores`!")
    except Exception as e:
        print("SQLite ingestion error:", e)

    # Ingest into PostgreSQL
    try:
        engine = sqlalchemy.create_engine("postgresql://postgres:hulk@localhost:5432/nirman_db")
        with engine.begin() as conn:
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
                    protective_factors JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX idx_risk_scores_project_month ON risk_scores(project_code, reporting_month);
                CREATE INDEX idx_risk_scores_category ON risk_scores(risk_category);
            """))
            risk_scores_df.to_sql("risk_scores", conn, if_exists="append", index=False)
        print("Updated PostgreSQL `nirman_db` table `risk_scores`!")
    except Exception as e:
        print("PostgreSQL ingestion error:", e)

    print("\n" + "=" * 100)
    print("SHAP RISK ENGINE & PROTECTIVE FACTORS INGESTION COMPLETED SUCCESSFULLY!")
    print("=" * 100)


if __name__ == "__main__":
    build_shap_risk_engine()
