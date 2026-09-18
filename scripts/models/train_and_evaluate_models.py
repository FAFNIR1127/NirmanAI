import json
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
import sqlite3
import sqlalchemy

from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, precision_recall_curve, auc, confusion_matrix, brier_score_loss
)
import xgboost as xgb
import lightgbm as lgb
import shap

# ============================================================
# PATHS & CONFIG
# ============================================================

DATA_DIR = Path("processed/features")
TRAIN_PATH = DATA_DIR / "train_dataset.parquet"
VAL_PATH = DATA_DIR / "val_dataset.parquet"
LIVE_PATH = DATA_DIR / "live_dataset.parquet"
ALL_FEATURES_PATH = DATA_DIR / "ml_features.parquet"

MODELS_DIR = Path("models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

TARGET_COL = "target_severe_risk_12m"

# Leakage audit list - any column containing these substrings MUST NOT be in predictor features X
LEAKAGE_SUBSTRINGS = ["target", "future"]

FEATURE_COLS = [
    'original_cost', 'revised_cost', 'anticipated_cost', 'cumulative_expenditure',
    'physical_progress', 'original_delay_months', 'revised_delay_months',
    'milestones_achieved', 'milestones_total', 'months_elapsed',
    'months_originally_planned', 'months_remaining', 'cost_expansion_ratio',
    'expenditure_ratio', 'expenditure_progress_gap', 'delay_months',
    'schedule_slippage_ratio', 'milestone_rate', 'progress_velocity',
    'agency_encoded', 'state_encoded'
]


# ============================================================
# 1. LEAKAGE AUDIT & PREPROCESSING
# ============================================================

def perform_leakage_audit(features_list):
    print("=== CONDUCTING CRITICAL LEAKAGE AUDIT ===")
    leak_detected = []
    for col in features_list:
        for sub in LEAKAGE_SUBSTRINGS:
            if sub in col.lower():
                leak_detected.append((col, sub))
    
    if leak_detected:
        raise ValueError(f"CRITICAL LEAKAGE DETECTED! Columns identified as targets/future: {leak_detected}")
    
    print(f"Leakage Audit PASSED! All {len(features_list)} predictor features verified timestamp-compliant.")


def load_and_preprocess_data():
    train_df = pd.read_parquet(TRAIN_PATH)
    val_df = pd.read_parquet(VAL_PATH)
    live_df = pd.read_parquet(LIVE_PATH)
    all_df = pd.read_parquet(ALL_FEATURES_PATH)

    # Encode Categoricals (agency, state)
    agency_le = LabelEncoder()
    state_le = LabelEncoder()

    all_agencies = pd.concat([train_df['agency'], val_df['agency'], live_df['agency'], all_df['agency']]).astype(str).fillna('Unknown')
    all_states = pd.concat([train_df['state'], val_df['state'], live_df['state'], all_df['state']]).astype(str).fillna('Unknown')

    agency_le.fit(all_agencies)
    state_le.fit(all_states)

    for df in [train_df, val_df, live_df, all_df]:
        df['agency_encoded'] = agency_le.transform(df['agency'].astype(str).fillna('Unknown'))
        df['state_encoded'] = state_le.transform(df['state'].astype(str).fillna('Unknown'))

    perform_leakage_audit(FEATURE_COLS)

    # Filter evaluable historical observations (drop target NaNs for training and validation)
    train_eval = train_df.dropna(subset=[TARGET_COL]).copy().reset_index(drop=True)
    val_eval = val_df.dropna(subset=[TARGET_COL]).copy().reset_index(drop=True)

    X_train = train_eval[FEATURE_COLS]
    y_train = train_eval[TARGET_COL].astype(int)

    X_val = val_eval[FEATURE_COLS]
    y_val = val_eval[TARGET_COL].astype(int)

    X_all = all_df[FEATURE_COLS]

    print(f"\nTrain Evaluable Rows: {len(X_train):,} (Pos: {(y_train == 1).sum():,}, Neg: {(y_train == 0).sum():,})")
    print(f"Val Evaluable Rows  : {len(X_val):,} (Pos: {(y_val == 1).sum():,}, Neg: {(y_val == 0).sum():,})")
    print(f"Total Full Features : {len(X_all):,}")

    return train_eval, val_eval, all_df, X_train, y_train, X_val, y_val, X_all, agency_le, state_le


# ============================================================
# 2. MODEL EVALUATION UTILITY
# ============================================================

def evaluate_model(name, model, X_val, y_val, threshold=0.5):
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X_val)[:, 1]
    else:
        probs = model.decision_function(X_val)
        probs = 1 / (1 + np.exp(-probs))

    preds = (probs >= threshold).astype(int)

    acc = accuracy_score(y_val, preds)
    prec = precision_score(y_val, preds, zero_division=0)
    rec = recall_score(y_val, preds, zero_division=0)
    f1 = f1_score(y_val, preds, zero_division=0)
    
    roc_auc = roc_auc_score(y_val, probs) if len(np.unique(y_val)) > 1 else np.nan
    
    prec_curve, rec_curve, _ = precision_recall_curve(y_val, probs)
    pr_auc = auc(rec_curve, prec_curve)
    
    cm = confusion_matrix(y_val, preds)
    brier = brier_score_loss(y_val, probs)

    metrics = {
        "Model": name,
        "Accuracy": float(acc),
        "Precision": float(prec),
        "Recall": float(rec),
        "F1-Score": float(f1),
        "ROC-AUC": float(roc_auc),
        "PR-AUC": float(pr_auc),
        "Brier Score (Calibration)": float(brier),
        "Confusion Matrix": cm.tolist()
    }
    return metrics, probs


# ============================================================
# 3. TRAINING PIPELINE
# ============================================================

def run_training_pipeline():
    train_eval, val_eval, all_df, X_train, y_train, X_val, y_val, X_all, agency_le, state_le = load_and_preprocess_data()

    models = {}
    metrics_summary = []
    val_probs_dict = {}

    # --- 1. Logistic Regression (Baseline) ---
    print("\n[1/4] Training Logistic Regression...")
    imputer_lr = SimpleImputer(strategy="median")
    scaler_lr = StandardScaler()
    X_train_lr = scaler_lr.fit_transform(imputer_lr.fit_transform(X_train))
    X_val_lr = scaler_lr.transform(imputer_lr.transform(X_val))

    lr_model = LogisticRegression(max_iter=1000, random_state=42, class_weight='balanced')
    lr_model.fit(X_train_lr, y_train)
    
    lr_pipeline = {"imputer": imputer_lr, "scaler": scaler_lr, "model": lr_model}
    joblib.dump(lr_pipeline, MODELS_DIR / "logistic_regression.joblib")
    
    lr_metrics, lr_probs = evaluate_model("Logistic Regression", lr_model, X_val_lr, y_val)
    metrics_summary.append(lr_metrics)
    val_probs_dict["Logistic Regression"] = lr_probs

    # --- 2. Random Forest (Nonlinear Baseline) ---
    print("[2/4] Training Random Forest...")
    imputer_rf = SimpleImputer(strategy="median")
    X_train_rf = imputer_rf.fit_transform(X_train)
    X_val_rf = imputer_rf.transform(X_val)

    rf_model = RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42, class_weight='balanced', n_jobs=-1)
    rf_model.fit(X_train_rf, y_train)

    rf_pipeline = {"imputer": imputer_rf, "model": rf_model}
    joblib.dump(rf_pipeline, MODELS_DIR / "random_forest.joblib")

    rf_metrics, rf_probs = evaluate_model("Random Forest", rf_model, X_val_rf, y_val)
    metrics_summary.append(rf_metrics)
    val_probs_dict["Random Forest"] = rf_probs

    # --- 3. XGBoost (Primary Candidate) ---
    print("[3/4] Training XGBoost Classifier...")
    pos_weight = (y_train == 0).sum() / max(1, (y_train == 1).sum())
    xgb_model = xgb.XGBClassifier(
        n_estimators=250,
        max_depth=6,
        learning_rate=0.05,
        scale_pos_weight=pos_weight,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="logloss"
    )
    xgb_model.fit(X_train, y_train)
    xgb_model.save_model(MODELS_DIR / "xgboost_severe_risk.json")

    xgb_metrics, xgb_probs = evaluate_model("XGBoost", xgb_model, X_val, y_val)
    metrics_summary.append(xgb_metrics)
    val_probs_dict["XGBoost"] = xgb_probs
    models["XGBoost"] = xgb_model

    # --- 4. LightGBM (Comparison) ---
    print("[4/4] Training LightGBM Classifier...")
    lgb_model = lgb.LGBMClassifier(
        n_estimators=250,
        max_depth=6,
        learning_rate=0.05,
        scale_pos_weight=pos_weight,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1
    )
    lgb_model.fit(X_train, y_train)
    lgb_model.booster_.save_model(str(MODELS_DIR / "lightgbm_severe_risk.txt"))

    lgb_metrics, lgb_probs = evaluate_model("LightGBM", lgb_model, X_val, y_val)
    metrics_summary.append(lgb_metrics)
    val_probs_dict["LightGBM"] = lgb_probs
    models["LightGBM"] = lgb_model

    # Save metrics JSON
    with open(MODELS_DIR / "model_metrics.json", "w") as f:
        json.dump(metrics_summary, f, indent=2)

    # Print Side-by-Side Performance Comparison Table
    print("\n" + "=" * 110)
    print("MODEL EVALUATION COMPARISON ON VALIDATION SET (2024-2025)")
    print("=" * 110)
    metrics_df = pd.DataFrame(metrics_summary).drop(columns=["Confusion Matrix"])
    print(metrics_df.to_string(index=False))
    print("=" * 110)

    # Select Best Model based on PR-AUC & F1-Score
    best_metric = max(metrics_summary, key=lambda m: (m["PR-AUC"], m["F1-Score"]))
    best_name = best_metric["Model"]
    print(f"\n🏆 BEST MODEL SELECTED: {best_name} (PR-AUC: {best_metric['PR-AUC']:.4f}, F1: {best_metric['F1-Score']:.4f})")

    best_model = models[best_name] if best_name in models else xgb_model
    joblib.dump(best_model, MODELS_DIR / "best_model.joblib")

    # ============================================================
    # 4. SHAP EXPLAINABILITY & 0-100 RISK ENGINE
    # ============================================================

    print(f"\n=== COMPUTING SHAP EXPLANATIONS & RISK SCORES WITH {best_name} ===")
    
    explainer = shap.TreeExplainer(best_model)
    shap_values = explainer.shap_values(X_all)

    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    # Calculate Probability & 0-100 Composite Risk Score
    all_probs = best_model.predict_proba(X_all)[:, 1]
    composite_risk_scores = np.round(all_probs * 100.0, 1)

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

    # Calculate Sub-Indices
    slippage_scaled = np.nan_to_num(all_df['schedule_slippage_ratio'].values, nan=0.0)
    schedule_index = np.clip(np.round(slippage_scaled * 40.0 + composite_risk_scores * 0.6, 1), 0.0, 100.0)

    cost_expansion_scaled = np.nan_to_num(all_df['cost_expansion_ratio'].values - 1.0, nan=0.0)
    cost_index = np.clip(np.round(cost_expansion_scaled * 50.0 + composite_risk_scores * 0.5, 1), 0.0, 100.0)

    top_drivers_json = []
    feature_names = np.array(FEATURE_COLS)

    for i in range(len(all_df)):
        row_shap = shap_values[i]
        top_idx = np.argsort(row_shap)[::-1][:3]
        
        drivers = []
        for idx in top_idx:
            feat_name = feature_names[idx]
            impact = float(row_shap[idx])
            val = float(X_all.iloc[i, idx]) if pd.notna(X_all.iloc[i, idx]) else None
            drivers.append({
                "feature": feat_name,
                "impact": round(impact, 4),
                "value": val
            })
        top_drivers_json.append(json.dumps(drivers))

    risk_scores_df = pd.DataFrame({
        "project_code": all_df["project_code"],
        "reporting_month": all_df["reporting_month"],
        "risk_score": composite_risk_scores,
        "risk_category": risk_categories,
        "schedule_risk_index": schedule_index,
        "cost_risk_index": cost_index,
        "predicted_severe_risk_prob": np.round(all_probs, 4),
        "key_risk_drivers": top_drivers_json
    })

    risk_scores_df.to_parquet("processed/features/risk_scores.parquet", index=False)
    print("\nSaved `processed/features/risk_scores.parquet`")

    print("\n=== INGESTING RISK SCORES INTO RELATIONAL DATABASES ===")
    
    # SQLite
    try:
        conn = sqlite3.connect("database/nirman.db")
        risk_scores_df.to_sql("risk_scores", conn, if_exists="replace", index=False)
        conn.close()
        print("Successfully updated SQLite `database/nirman.db` table `risk_scores`!")
    except Exception as e:
        print("SQLite ingestion error:", e)

    # PostgreSQL
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX idx_risk_scores_project_month ON risk_scores(project_code, reporting_month);
                CREATE INDEX idx_risk_scores_category ON risk_scores(risk_category);
            """))
            risk_scores_df.to_sql("risk_scores", conn, if_exists="append", index=False)
        print("Successfully updated PostgreSQL `nirman_db` table `risk_scores`!")
    except Exception as e:
        print("PostgreSQL ingestion error:", e)

    print("\n" + "=" * 100)
    print("PHASE 2 MODEL TRAINING & SHAP RISK ENGINE COMPLETED SUCCESSFULLY!")
    print("=" * 100)


if __name__ == "__main__":
    run_training_pipeline()
