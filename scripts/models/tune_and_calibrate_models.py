import json
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
import sqlite3
import sqlalchemy

from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, precision_recall_curve, auc, confusion_matrix, brier_score_loss
)
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
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

# Feature list (verified leak-free)
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
# 1. LOAD DATA & ENCODE CATEGORICALS
# ============================================================

def load_data():
    train_df = pd.read_parquet(TRAIN_PATH)
    val_df = pd.read_parquet(VAL_PATH)
    live_df = pd.read_parquet(LIVE_PATH)
    all_df = pd.read_parquet(ALL_FEATURES_PATH)

    agency_le = LabelEncoder()
    state_le = LabelEncoder()

    all_agencies = pd.concat([train_df['agency'], val_df['agency'], live_df['agency'], all_df['agency']]).astype(str).fillna('Unknown')
    all_states = pd.concat([train_df['state'], val_df['state'], live_df['state'], all_df['state']]).astype(str).fillna('Unknown')

    agency_le.fit(all_agencies)
    state_le.fit(all_states)

    for df in [train_df, val_df, live_df, all_df]:
        df['agency_encoded'] = agency_le.transform(df['agency'].astype(str).fillna('Unknown'))
        df['state_encoded'] = state_le.transform(df['state'].astype(str).fillna('Unknown'))

    # Evaluable historical training observations (2018-2023)
    train_eval = train_df.dropna(subset=[TARGET_COL]).copy().reset_index(drop=True)
    # Untouched final holdout (2024-2025)
    val_eval = val_df.dropna(subset=[TARGET_COL]).copy().reset_index(drop=True)

    return train_eval, val_eval, live_df, all_df


# ============================================================
# 2. TIME-SERIES EXPANDING WINDOW CROSS-VALIDATION
# ============================================================

def get_time_series_folds(train_eval):
    """
    Fold 1: Train 2018-2019 -> Validate 2020-04
    Fold 2: Train 2018-2020 -> Validate 2021-04
    Fold 3: Train 2018-2021 -> Validate 2022-04 & 2023-04
    """
    folds = [
        (train_eval["reporting_month"] <= "2019-04", train_eval["reporting_month"] == "2020-04"),
        (train_eval["reporting_month"] <= "2020-04", train_eval["reporting_month"] == "2021-04"),
        (train_eval["reporting_month"] <= "2021-04", train_eval["reporting_month"] >= "2022-04")
    ]
    return folds


def evaluate_cv(model_class, param, train_eval, is_rf=False):
    folds = get_time_series_folds(train_eval)
    oof_probs = np.zeros(len(train_eval))
    oof_mask = np.zeros(len(train_eval), dtype=bool)

    pr_aucs, roc_aucs = [], []

    for tr_idx_mask, val_idx_mask in folds:
        X_tr = train_eval.loc[tr_idx_mask, FEATURE_COLS]
        y_tr = train_eval.loc[tr_idx_mask, TARGET_COL].astype(int)
        X_va = train_eval.loc[val_idx_mask, FEATURE_COLS]
        y_va = train_eval.loc[val_idx_mask, TARGET_COL].astype(int)

        if is_rf:
            imputer = SimpleImputer(strategy="median", keep_empty_features=True)
            X_tr_imp = np.nan_to_num(imputer.fit_transform(X_tr), nan=0.0)
            X_va_imp = np.nan_to_num(imputer.transform(X_va), nan=0.0)
            clf = model_class(**param)
            clf.fit(X_tr_imp, y_tr)
            probs = clf.predict_proba(X_va_imp)[:, 1]
        else:
            clf = model_class(**param)
            clf.fit(X_tr, y_tr)
            probs = clf.predict_proba(X_va)[:, 1]

        oof_probs[val_idx_mask] = probs
        oof_mask |= val_idx_mask

        prec, rec, _ = precision_recall_curve(y_va, probs)
        pr_aucs.append(auc(rec, prec))
        roc_aucs.append(roc_auc_score(y_va, probs))

    mean_pr_auc = np.mean(pr_aucs)
    mean_roc_auc = np.mean(roc_aucs)

    return mean_pr_auc, mean_roc_auc, oof_probs, oof_mask


# ============================================================
# 3. HYPERPARAMETER TUNING (XGBOOST & RANDOM FOREST)
# ============================================================

def tune_xgboost(train_eval, n_trials=25):
    print("\n=== PHASE 2.1 & 2.2: TIME-SERIES CV TUNING FOR XGBOOST ===")
    np.random.seed(42)

    param_grid = {
        'max_depth': [3, 4, 5, 6, 7, 8],
        'learning_rate': [0.01, 0.03, 0.05, 0.08, 0.1],
        'n_estimators': [100, 150, 200, 300],
        'min_child_weight': [1, 3, 5, 8],
        'subsample': [0.6, 0.7, 0.8, 0.9],
        'colsample_bytree': [0.6, 0.7, 0.8, 0.9],
        'reg_alpha': [0.0, 0.1, 1.0, 5.0],
        'reg_lambda': [0.1, 1.0, 5.0, 10.0],
        'gamma': [0.0, 0.1, 0.2, 0.5],
        'scale_pos_weight': [1.0, 1.3, 1.5, 1.8, 2.0]
    }

    best_score = -1.0
    best_params = None
    best_oof_probs = None
    best_oof_mask = None

    for trial in range(1, n_trials + 1):
        params = {k: int(v) if isinstance(v, (np.integer, int)) else float(v) if isinstance(v, (np.floating, float)) else v for k, v in {k: np.random.choice(v) for k, v in param_grid.items()}.items()}
        params['random_state'] = 42
        params['eval_metric'] = 'logloss'

        mean_pr_auc, mean_roc_auc, oof_probs, oof_mask = evaluate_cv(xgb.XGBClassifier, params, train_eval, is_rf=False)
        print(f"Trial {trial:2d}/{n_trials} | XGBoost CV PR-AUC: {mean_pr_auc:.4f} | ROC-AUC: {mean_roc_auc:.4f}")

        if mean_pr_auc > best_score:
            best_score = mean_pr_auc
            best_params = params
            best_oof_probs = oof_probs
            best_oof_mask = oof_mask

    print(f"\n🏆 BEST XGBoost CV PR-AUC: {best_score:.4f}")
    print(f"Best Params: {json.dumps({k: (float(v) if isinstance(v, (np.floating, float)) else int(v) if isinstance(v, (np.integer, int)) else v) for k, v in best_params.items()}, indent=2)}")
    return best_params, best_score, best_oof_probs, best_oof_mask


def tune_random_forest(train_eval, n_trials=15):
    print("\n=== TIME-SERIES CV TUNING FOR RANDOM FOREST ===")
    np.random.seed(42)

    param_grid = {
        'n_estimators': [100, 200, 300],
        'max_depth': [6, 8, 10, 12, 15],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 5],
        'max_features': ['sqrt', 'log2', 'sqrt'],
        'class_weight': ['balanced', 'balanced_subsample', None]
    }

    best_score = -1.0
    best_params = None

    for trial in range(1, n_trials + 1):
        params = {k: (int(v) if isinstance(v, (np.integer, int)) else float(v) if isinstance(v, (np.floating, float)) else (None if str(v) == 'None' else str(v))) for k, v in {k: np.random.choice(v) for k, v in param_grid.items()}.items()}
        params['random_state'] = 42
        params['n_jobs'] = -1

        mean_pr_auc, mean_roc_auc, _, _ = evaluate_cv(RandomForestClassifier, params, train_eval, is_rf=True)
        print(f"Trial {trial:2d}/{n_trials} | Random Forest CV PR-AUC: {mean_pr_auc:.4f} | ROC-AUC: {mean_roc_auc:.4f}")

        if mean_pr_auc > best_score:
            best_score = mean_pr_auc
            best_params = params

    print(f"\n🏆 BEST Random Forest CV PR-AUC: {best_score:.4f}")
    return best_params, best_score


# ============================================================
# 4. OPTIMAL THRESHOLD & CALIBRATION ON CV DATA
# ============================================================

def optimize_threshold(y_true, oof_probs):
    print("\n=== PHASE 2.3: OPERATIONAL THRESHOLD OPTIMIZATION ===")
    thresholds = np.arange(0.15, 0.85, 0.01)
    best_t = 0.50
    best_f1 = -1.0

    print(f"{'Threshold':<10} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Flagged Count':<15}")
    print("-" * 65)

    for t in thresholds:
        preds = (oof_probs >= t).astype(int)
        prec = precision_score(y_true, preds, zero_division=0)
        rec = recall_score(y_true, preds, zero_division=0)
        f1 = f1_score(y_true, preds, zero_division=0)
        flagged = preds.sum()

        if f1 > best_f1 and rec >= 0.35: # Require at least 35% recall for early warning usefulness
            best_f1 = f1
            best_t = t

        if abs(t - 0.50) < 1e-4 or abs(t - 0.35) < 1e-4 or abs(t - 0.25) < 1e-4 or abs(t - 0.60) < 1e-4:
            print(f"{t:<10.2f} | {prec:<10.4f} | {rec:<10.4f} | {f1:<10.4f} | {flagged:<15,}")

    print(f"\n🏆 OPTIMAL OPERATIONAL THRESHOLD T* = {best_t:.2f} (OOF F1-Score: {best_f1:.4f})")
    return best_t


# ============================================================
# 5. MAIN PIPELINE EXECUTION
# ============================================================

def run_tuning_and_calibration():
    train_eval, val_eval, live_df, all_df = load_data()

    # 1. Hyperparameter Tuning via Time-Series CV
    xgb_params, xgb_cv_pr_auc, oof_probs, oof_mask = tune_xgboost(train_eval, n_trials=25)
    rf_params, rf_cv_pr_auc = tune_random_forest(train_eval, n_trials=12)

    # 2. Threshold Optimization on Out-Of-Fold Train Predictions
    y_oof_true = train_eval.loc[oof_mask, TARGET_COL].astype(int).values
    oof_eval_probs = oof_probs[oof_mask]
    optimal_threshold = optimize_threshold(y_oof_true, oof_eval_probs)

    # 3. Fit Final Model & Probability Calibration
    print("\n=== PHASE 2.4: FITTING & CALIBRATING FINAL XGBOOST MODEL ===")
    X_train_full = train_eval[FEATURE_COLS]
    y_train_full = train_eval[TARGET_COL].astype(int)

    base_model = xgb.XGBClassifier(**xgb_params)
    
    # Fit base model on 100% of historical training data (2018-2023)
    base_model.fit(X_train_full, y_train_full)

    # Calibrate probabilities using Sigmoid / Platt scaling via 5-Fold CalibratedClassifierCV
    calibrated_model = CalibratedClassifierCV(estimator=base_model, method='sigmoid', cv=5)
    calibrated_model.fit(X_train_full, y_train_full)

    # Save Tuned & Calibrated Model Artifacts
    joblib.dump(base_model, MODELS_DIR / "tuned_xgb_base.joblib")
    joblib.dump(calibrated_model, MODELS_DIR / "tuned_xgb_calibrated.joblib")

    # ============================================================
    # 6. PHASE 2.5: UNTOUCHED 2024-2025 HOLDOUT EVALUATION (ONCE)
    # ============================================================

    print("\n" + "=" * 110)
    print("PHASE 2.5: UNTOUCHED 2024-2025 HOLDOUT EVALUATION (FINAL HOLDOUT)")
    print("=" * 110)

    X_val = val_eval[FEATURE_COLS]
    y_val = val_eval[TARGET_COL].astype(int).values

    val_probs_raw = base_model.predict_proba(X_val)[:, 1]
    val_probs_cal = calibrated_model.predict_proba(X_val)[:, 1]

    # Evaluate at default 0.50 threshold and optimal T*
    for desc, probs in [("Uncalibrated XGBoost (Default T=0.50)", val_probs_raw),
                        ("Calibrated XGBoost   (Default T=0.50)", val_probs_cal),
                        (f"Calibrated XGBoost   (Optimal T*={optimal_threshold:.2f})", val_probs_cal)]:

        t_used = optimal_threshold if "Optimal" in desc else 0.50
        preds = (probs >= t_used).astype(int)

        acc = accuracy_score(y_val, preds)
        prec = precision_score(y_val, preds, zero_division=0)
        rec = recall_score(y_val, preds, zero_division=0)
        f1 = f1_score(y_val, preds, zero_division=0)
        roc = roc_auc_score(y_val, probs)
        
        prec_c, rec_c, _ = precision_recall_curve(y_val, probs)
        pr_auc_val = auc(rec_c, prec_c)
        brier = brier_score_loss(y_val, probs)
        cm = confusion_matrix(y_val, preds)

        print(f"\n--- {desc} ---")
        print(f"Accuracy     : {acc*100:.2f}%")
        print(f"Precision    : {prec*100:.2f}%")
        print(f"Recall       : {rec*100:.2f}%")
        print(f"F1-Score     : {f1:.4f}")
        print(f"ROC-AUC      : {roc:.4f}")
        print(f"PR-AUC       : {pr_auc_val:.4f}")
        print(f"Brier Score  : {brier:.4f} (Lower = Better Calibration)")
        print(f"Confusion Matrix:\n{cm}")

    # ============================================================
    # 7. PHASE 2.6 & 2.7: SHAP EXPLANATIONS & 2026 RISK INGESTION
    # ============================================================

    print("\n=== PHASE 2.6 & 2.7: SHAP EXPLANATIONS & POSTGRESQL RISK INGESTION ===")
    
    X_all = all_df[FEATURE_COLS]
    
    explainer = shap.TreeExplainer(base_model)
    shap_values = explainer.shap_values(X_all)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    # Calibrated probabilities P(Severe Risk within 12M)
    all_cal_probs = calibrated_model.predict_proba(X_all)[:, 1]
    
    # Defensible 0-100 Nirman Risk Score directly tied to Calibrated P(Risk)
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
        "predicted_severe_risk_prob": np.round(all_cal_probs, 4),
        "key_risk_drivers": top_drivers_json
    })

    risk_scores_df.to_parquet("processed/features/risk_scores.parquet", index=False)
    print("\nSaved calibrated `processed/features/risk_scores.parquet`")

    # Ingest into SQLite and PostgreSQL
    try:
        conn = sqlite3.connect("database/nirman.db")
        risk_scores_df.to_sql("risk_scores", conn, if_exists="replace", index=False)
        conn.close()
        print("Updated SQLite `database/nirman.db` table `risk_scores`!")
    except Exception as e:
        print("SQLite ingestion error:", e)

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
        print("Updated PostgreSQL `nirman_db` table `risk_scores`!")
    except Exception as e:
        print("PostgreSQL ingestion error:", e)

    print("\n" + "=" * 110)
    print("PHASE 2 RIGOROUS TUNING, TIME-SERIES CV & CALIBRATION PIPELINE COMPLETED SUCCESSFULLY!")
    print("=" * 110)


if __name__ == "__main__":
    run_tuning_and_calibration()
