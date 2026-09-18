import json
from pathlib import Path
import pandas as pd
import numpy as np
import joblib

from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, precision_recall_curve, auc, confusion_matrix, brier_score_loss
)
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier

# ============================================================
# PATHS
# ============================================================

DATA_DIR = Path("processed/features")
TRAIN_PATH = DATA_DIR / "train_dataset.parquet"
VAL_PATH = DATA_DIR / "val_dataset.parquet"
ALL_FEATURES_PATH = DATA_DIR / "ml_features.parquet"

MODELS_DIR = Path("models")
TARGET_COL = "target_severe_risk_12m"

FEATURE_COLS = [
    'original_cost', 'revised_cost', 'anticipated_cost', 'cumulative_expenditure',
    'physical_progress', 'original_delay_months', 'revised_delay_months',
    'milestones_achieved', 'milestones_total', 'months_elapsed',
    'months_originally_planned', 'months_remaining', 'cost_expansion_ratio',
    'expenditure_ratio', 'expenditure_progress_gap', 'delay_months',
    'schedule_slippage_ratio', 'milestone_rate', 'progress_velocity',
    'agency_encoded', 'state_encoded'
]


def load_data():
    train_df = pd.read_parquet(TRAIN_PATH)
    val_df = pd.read_parquet(VAL_PATH)
    all_df = pd.read_parquet(ALL_FEATURES_PATH)

    agency_le = LabelEncoder()
    state_le = LabelEncoder()

    all_agencies = pd.concat([train_df['agency'], val_df['agency'], all_df['agency']]).astype(str).fillna('Unknown')
    all_states = pd.concat([train_df['state'], val_df['state'], all_df['state']]).astype(str).fillna('Unknown')

    agency_le.fit(all_agencies)
    state_le.fit(all_states)

    for df in [train_df, val_df, all_df]:
        df['agency_encoded'] = agency_le.transform(df['agency'].astype(str).fillna('Unknown'))
        df['state_encoded'] = state_le.transform(df['state'].astype(str).fillna('Unknown'))

    train_eval = train_df.dropna(subset=[TARGET_COL]).copy().reset_index(drop=True)
    val_eval = val_df.dropna(subset=[TARGET_COL]).copy().reset_index(drop=True)

    return train_eval, val_eval, all_df


def run_diagnostics():
    train_eval, val_eval, all_df = load_data()

    X_tr = train_eval[FEATURE_COLS]
    y_tr = train_eval[TARGET_COL].astype(int).values

    X_va = val_eval[FEATURE_COLS]
    y_va = val_eval[TARGET_COL].astype(int).values

    print("=" * 110)
    print("PHASE 2.8 — MODEL VALIDATION & ROBUSTNESS DIAGNOSTICS")
    print("=" * 110)

    # ------------------------------------------------------------
    # 1. BASELINE COMPARISONS (ON HOLDOUT 2024-2025)
    # ------------------------------------------------------------
    print("\n=== 1. BASELINE COMPARISON ON HOLDOUT (2024-2025) ===")
    
    # Dummy Prior Baseline
    dummy = DummyClassifier(strategy="prior")
    dummy.fit(X_tr, y_tr)
    dummy_probs = dummy.predict_proba(X_va)[:, 1]
    dummy_prec, dummy_rec, _ = precision_recall_curve(y_va, dummy_probs)
    dummy_pr_auc = auc(dummy_rec, dummy_prec)
    dummy_roc_auc = roc_auc_score(y_va, dummy_probs)
    dummy_brier = brier_score_loss(y_va, dummy_probs)

    # Simple Logistic Regression Baseline
    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    scaler = StandardScaler()
    X_tr_lr = scaler.fit_transform(np.nan_to_num(imputer.fit_transform(X_tr), nan=0.0))
    X_va_lr = scaler.transform(np.nan_to_num(imputer.transform(X_va), nan=0.0))
    
    lr = LogisticRegression(max_iter=1000, random_state=42, class_weight='balanced')
    lr.fit(X_tr_lr, y_tr)
    lr_probs = lr.predict_proba(X_va_lr)[:, 1]
    lr_prec, lr_rec, _ = precision_recall_curve(y_va, lr_probs)
    lr_pr_auc = auc(lr_rec, lr_prec)
    lr_roc_auc = roc_auc_score(y_va, lr_probs)
    lr_brier = brier_score_loss(y_va, lr_probs)

    # Load Calibrated XGBoost Model
    calibrated_xgb = joblib.load(MODELS_DIR / "tuned_xgb_calibrated.joblib")
    xgb_probs = calibrated_xgb.predict_proba(X_va)[:, 1]
    xgb_prec, xgb_rec, _ = precision_recall_curve(y_va, xgb_probs)
    xgb_pr_auc = auc(xgb_rec, xgb_prec)
    xgb_roc_auc = roc_auc_score(y_va, xgb_probs)
    xgb_brier = brier_score_loss(y_va, xgb_probs)

    baseline_df = pd.DataFrame([
        {"Model": "Dummy Prior (Prevalence)", "PR-AUC": dummy_pr_auc, "ROC-AUC": dummy_roc_auc, "Brier Score": dummy_brier},
        {"Model": "Logistic Regression (Baseline)", "PR-AUC": lr_pr_auc, "ROC-AUC": lr_roc_auc, "Brier Score": lr_brier},
        {"Model": "Calibrated XGBoost (Tuned)", "PR-AUC": xgb_pr_auc, "ROC-AUC": xgb_roc_auc, "Brier Score": xgb_brier}
    ])
    print(baseline_df.to_string(index=False))

    # ------------------------------------------------------------
    # 2. INVESTIGATE CV -> HOLDOUT PERFORMANCE DROP
    # ------------------------------------------------------------
    print("\n=== 2. ROOT CAUSE INVESTIGATION: CV -> HOLDOUT PERFORMANCE DROP ===")
    
    tr_prev = y_tr.mean()
    va_prev = y_va.mean()

    print(f"Target Prevalence in Train (2018-2023)  : {tr_prev*100:.2f}% ({y_tr.sum():,} / {len(y_tr):,})")
    print(f"Target Prevalence in Holdout (2024-2025): {va_prev*100:.2f}% ({y_va.sum():,} / {len(y_va):,})")
    print(f"Prevalence Shift Ratio                 : {va_prev / tr_prev:.2f}x (Holdout has {((va_prev/tr_prev)-1)*100:.1f}% lower target prevalence!)")

    print("\n* Impact of Prevalence Shift on PR-AUC *")
    print(f"  Random Classifier Baseline in Train  : {tr_prev:.4f}")
    print(f"  Random Classifier Baseline in Holdout: {va_prev:.4f}")
    print(f"  CV PR-AUC Lift Over Random Baseline  : {0.7658 / tr_prev:.2f}x")
    print(f"  Holdout PR-AUC Lift Over Baseline    : {xgb_pr_auc / va_prev:.2f}x")

    print("\n* Feature Availability & Missingness Shift *")
    feat_shift = []
    for col in FEATURE_COLS:
        tr_na = X_tr[col].isna().mean() * 100
        va_na = X_va[col].isna().mean() * 100
        tr_mean = X_tr[col].mean()
        va_mean = X_va[col].mean()
        feat_shift.append({
            "Feature": col,
            "Train NaN %": round(tr_na, 1),
            "Holdout NaN %": round(va_na, 1),
            "Train Mean": round(tr_mean, 3) if pd.notna(tr_mean) else None,
            "Holdout Mean": round(va_mean, 3) if pd.notna(va_mean) else None
        })
    shift_df = pd.DataFrame(feat_shift)
    print(shift_df[(shift_df["Train NaN %"] != shift_df["Holdout NaN %"]) | (shift_df["Train Mean"] != shift_df["Holdout Mean"])].to_string(index=False))

    # ------------------------------------------------------------
    # 3. CHECK CALIBRATION BY TIME PERIOD
    # ------------------------------------------------------------
    print("\n=== 3. CALIBRATION BY TIME PERIOD (PREDICTED PROB VS ACTUAL EVENT FREQ) ===")
    
    # Train OOF vs Holdout Calibration Bins
    train_cal_probs = calibrated_xgb.predict_proba(X_tr)[:, 1]
    
    bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

    def get_calibration_table(y_true, probs, dataset_name):
        df_cal = pd.DataFrame({"y": y_true, "p": probs})
        df_cal["bin"] = pd.cut(df_cal["p"], bins=bins, include_lowest=True)
        grouped = df_cal.groupby("bin", observed=False).agg(
            Count=("y", "count"),
            Mean_Pred_Prob=("p", "mean"),
            Actual_Freq=("y", "mean")
        ).reset_index()
        grouped["Dataset"] = dataset_name
        return grouped

    train_cal_tbl = get_calibration_table(y_tr, train_cal_probs, "Train (2018-2023)")
    val_cal_tbl = get_calibration_table(y_va, xgb_probs, "Holdout (2024-2025)")

    print("\n--- Calibration Table: Train (2018-2023) ---")
    print(train_cal_tbl.to_string(index=False))

    print("\n--- Calibration Table: Holdout (2024-2025) ---")
    print(val_cal_tbl.to_string(index=False))

    # ------------------------------------------------------------
    # 4. THRESHOLD STABILITY ANALYSIS AROUND T* = 0.28
    # ------------------------------------------------------------
    print("\n=== 4. THRESHOLD STABILITY ANALYSIS ON HOLDOUT (2024-2025) ===")
    
    t_list = [0.20, 0.22, 0.25, 0.28, 0.30, 0.35, 0.40, 0.50]
    thresh_results = []

    for t in t_list:
        preds = (xgb_probs >= t).astype(int)
        acc = accuracy_score(y_va, preds)
        prec = precision_score(y_va, preds, zero_division=0)
        rec = recall_score(y_va, preds, zero_division=0)
        f1 = f1_score(y_va, preds, zero_division=0)
        flagged = preds.sum()

        thresh_results.append({
            "Threshold (T)": f"{t:.2f}" + (" (Optimal T*)" if t == 0.28 else ""),
            "Accuracy": f"{acc*100:.2f}%",
            "Precision": f"{prec*100:.2f}%",
            "Recall": f"{rec*100:.2f}%",
            "F1-Score": f"{f1:.4f}",
            "Flagged Count": f"{flagged:,}"
        })

    thresh_df = pd.DataFrame(thresh_results)
    print(thresh_df.to_string(index=False))
    print("=" * 110)


if __name__ == "__main__":
    run_diagnostics()
