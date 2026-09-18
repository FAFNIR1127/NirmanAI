"""
calibrate_and_optimize_threshold.py

Executes Phase 3:
1. Fits the selected champion model on the training era (2018-2023).
2. Performs 5-fold probability calibration (Platt Sigmoid vs Isotonic Regression) strictly on training data.
3. Generates the reliability curve and compares Brier score and Brier Skill Score.
4. Sweeps operational decision thresholds tau in [0.10, 0.70] and computes:
   - Precision, Recall, F1, False Negatives, False Positives
   - Operational Cost: Cost = 5 * FN + 1 * FP
5. Saves the locked model, calibrator, threshold config, and feature schema.
"""

from pathlib import Path
import json
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import joblib
from sklearn.preprocessing import LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, precision_recall_curve, auc, confusion_matrix, brier_score_loss
)
import xgboost as xgb

ROOT_DIR = Path("/Users/sanket/SIH/NirmanAnti")
DATA_DIR = ROOT_DIR / "processed" / "features"
MODELS_DIR = ROOT_DIR / "models"
VERSION_DIR = MODELS_DIR / "risk_engine_v2"
VERSION_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR = ROOT_DIR / "reports" / "model_evaluation"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

TARGET_COL = "target_severe_risk_12m"

FEATURE_COLS = [
    'original_cost', 'revised_cost', 'anticipated_cost', 'cumulative_expenditure',
    'physical_progress', 'original_delay_months', 'revised_delay_months',
    'milestones_achieved', 'milestones_total',
    'months_elapsed', 'months_originally_planned', 'months_remaining',
    'cost_expansion_ratio', 'expenditure_ratio', 'expenditure_progress_gap',
    'delay_months', 'schedule_slippage_ratio', 'elapsed_ratio',
    'cost_overrun_velocity', 'expenditure_burn_rate', 'remaining_funds_ratio',
    'required_spend_rate_monthly', 'required_progress_velocity',
    'progress_velocity', 'milestone_rate',
    'interaction_slippage_cost', 'interaction_gap_velocity',
    'delta_anticipated_cost', 'delta_delay_months', 'delta_expenditure', 'delta_physical_progress',
    'sector_historical_risk',
    'agency_encoded', 'state_encoded'
]


def load_train_data():
    train_path = DATA_DIR / "train_dataset_v2.parquet"
    df = pd.read_parquet(train_path)
    eval_df = df.dropna(subset=[TARGET_COL]).copy().reset_index(drop=True)
    eval_df[TARGET_COL] = eval_df[TARGET_COL].astype(int)

    agency_le = LabelEncoder()
    state_le = LabelEncoder()
    agency_classes = sorted(list(set(eval_df['agency'].astype(str).tolist() + ['Unknown'])))
    state_classes = sorted(list(set(eval_df['state'].astype(str).tolist() + ['Unknown'])))
    agency_le.fit(agency_classes)
    state_le.fit(state_classes)
    eval_df['agency_encoded'] = agency_le.transform(eval_df['agency'].astype(str).fillna('Unknown'))
    eval_df['state_encoded'] = state_le.transform(eval_df['state'].astype(str).fillna('Unknown'))

    # Save encoders
    joblib.dump(agency_le, VERSION_DIR / "agency_encoder.joblib")
    joblib.dump(state_le, VERSION_DIR / "state_encoder.joblib")

    X = eval_df[FEATURE_COLS]
    y = eval_df[TARGET_COL]
    return X, y, eval_df


def train_calibrate_and_optimize():
    print("=== PHASE 3: TRAINING-ERA CALIBRATION & THRESHOLD OPTIMIZATION ===")
    X_train, y_train, train_df = load_train_data()
    pos_prevalence = float(y_train.mean())

    # 1. Median Imputer
    imputer = SimpleImputer(strategy="median")
    X_train_imp = imputer.fit_transform(X_train)
    X_train_df = pd.DataFrame(X_train_imp, columns=FEATURE_COLS)
    joblib.dump(imputer, VERSION_DIR / "imputer.joblib")

    # 2. Champion Base Estimator (Tuned XGBoost)
    base_xgb = xgb.XGBClassifier(
        max_depth=4,
        learning_rate=0.02,
        n_estimators=350,
        subsample=0.85,
        colsample_bytree=0.75,
        scale_pos_weight=2.2,
        reg_lambda=4.0,
        random_state=42,
        eval_metric="logloss"
    )

    # 3. Probability Calibration (5-fold Sigmoid Platt Scaling vs Isotonic)
    print("\nFitting 5-fold Sigmoid Platt Calibrator on 2018-2023 training era...")
    calibrator_sigmoid = CalibratedClassifierCV(estimator=base_xgb, method="sigmoid", cv=5)
    calibrator_sigmoid.fit(X_train_df, y_train)

    print("Fitting 5-fold Isotonic Calibrator on 2018-2023 training era...")
    calibrator_isotonic = CalibratedClassifierCV(estimator=base_xgb, method="isotonic", cv=5)
    calibrator_isotonic.fit(X_train_df, y_train)

    # In-sample OOF Calibration metrics
    probs_sig = calibrator_sigmoid.predict_proba(X_train_df)[:, 1]
    probs_iso = calibrator_isotonic.predict_proba(X_train_df)[:, 1]

    brier_sig = brier_score_loss(y_train, probs_sig)
    brier_iso = brier_score_loss(y_train, probs_iso)
    brier_ref = np.mean((pos_prevalence - y_train) ** 2)
    bss_sig = 1.0 - (brier_sig / brier_ref)
    bss_iso = 1.0 - (brier_iso / brier_ref)

    print(f"Sigmoid Platt Brier Score: {brier_sig:.4f} (Brier Skill Score: {bss_sig:.4f})")
    print(f"Isotonic Calib Brier Score: {brier_iso:.4f} (Brier Skill Score: {bss_iso:.4f})")

    # Select winning calibrator
    chosen_calibrator = calibrator_sigmoid if brier_sig <= brier_iso else calibrator_isotonic
    chosen_method = "sigmoid" if brier_sig <= brier_iso else "isotonic"
    chosen_probs = probs_sig if brier_sig <= brier_iso else probs_iso
    print(f"Selected Champion Calibrator: {chosen_method.upper()} Scaling")

    # 4. Threshold Optimization Sweep on Calibrated Probabilities
    print("\n" + "="*85)
    print("OPERATIONAL THRESHOLD OPTIMIZATION SWEEP (TRAINING ERA)")
    print("="*85)
    thresholds = [0.10, 0.15, 0.20, 0.25, 0.28, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70]
    sweep_results = []

    best_f1 = -1.0
    f1_threshold = 0.5
    best_cost = float("inf")
    cost_threshold = 0.5
    best_youden = -1.0
    youden_threshold = 0.5

    header = f"{'Threshold':<10} | {'Precision':<10} | {'Recall':<10} | {'F1':<8} | {'FP':<6} | {'FN':<6} | {'Cost (5FN+1FP)':<15}"
    print(header)
    print("-" * len(header))

    for th in thresholds:
        preds = (chosen_probs >= th).astype(int)
        p = precision_score(y_train, preds, zero_division=0)
        r = recall_score(y_train, preds, zero_division=0)
        f1 = f1_score(y_train, preds, zero_division=0)
        cm = confusion_matrix(y_train, preds)
        tn, fp, fn, tp = cm.ravel()
        cost = 5 * fn + 1 * fp
        youden = (tp / (tp + fn)) - (fp / (fp + tn)) if (tp + fn) > 0 and (fp + tn) > 0 else 0

        sweep_results.append({
            "threshold": th,
            "precision": float(p),
            "recall": float(r),
            "f1": float(f1),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "operational_cost": int(cost),
            "youden_j": float(youden)
        })

        print(f"{th:<10.2f} | {p:<10.4f} | {r:<10.4f} | {f1:<8.4f} | {fp:<6} | {fn:<6} | {cost:<15}")

        if f1 > best_f1:
            best_f1 = f1
            f1_threshold = th
        if cost < best_cost:
            best_cost = cost
            cost_threshold = th
        if youden > best_youden:
            best_youden = youden
            youden_threshold = th

    print("\n--- THRESHOLD DECISION SUMMARY ---")
    print(f"F1-Optimal Threshold:           {f1_threshold:.2f} (F1: {best_f1:.4f})")
    print(f"Youden's J Optimal Threshold:   {youden_threshold:.2f} (J: {best_youden:.4f})")
    print(f"Operational Cost-Min Threshold: {cost_threshold:.2f} (Cost: {best_cost})")

    # We select cost_threshold (or 0.28 for high-recall infrastructure risk alerting)
    operational_threshold = cost_threshold

    # 5. Fit stand-alone base model for SHAP tree explanations
    base_xgb.fit(X_train_df, y_train)

    # 6. Save locked artifacts in models/risk_engine_v2/ and models/
    joblib.dump(base_xgb, VERSION_DIR / "xgboost_base.joblib")
    joblib.dump(chosen_calibrator, VERSION_DIR / "calibrator.joblib")
    
    threshold_meta = {
        "operational_threshold": operational_threshold,
        "f1_optimal_threshold": f1_threshold,
        "youden_optimal_threshold": youden_threshold,
        "cost_penalty_ratio": "5FN + 1FP",
        "threshold_sweep_table": sweep_results
    }
    with open(VERSION_DIR / "threshold_config.json", "w") as f:
        json.dump(threshold_meta, f, indent=2)

    with open(VERSION_DIR / "feature_schema.json", "w") as f:
        json.dump({
            "feature_columns": FEATURE_COLS,
            "num_features": len(FEATURE_COLS),
            "target_column": TARGET_COL,
            "base_prevalence": pos_prevalence,
            "calibration_method": chosen_method
        }, f, indent=2)

    with open(REPORTS_DIR / "threshold_optimization_table.json", "w") as f:
        json.dump(sweep_results, f, indent=2)

    print(f"\nAll training-era artifacts locked in {VERSION_DIR}")
    return VERSION_DIR, operational_threshold

if __name__ == "__main__":
    train_calibrate_and_optimize()
