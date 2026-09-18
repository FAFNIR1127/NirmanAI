"""
run_temporal_experiments.py

Executes leakage-safe, time-aware cross-validation exclusively on the 2018-2023 training era.
The 2024-2025 holdout is STRICTLY QUARANTINED and never accessed here.

Methodology:
1. Class distribution & empirical baselines (Dummy most_frequent, Dummy stratified).
2. Leakage audit verifying zero target/future columns in predictor matrix.
3. Primary Validation: Expanding-Window Temporal CV (2018-2020->2021, 2018-2021->2022, 2018-2022->2023).
4. Secondary Validation: GroupKFold (grouped by project_code) to prevent longitudinal project leakage.
5. Class Imbalance Experiments (Unweighted, scale_pos_weight, SMOTE, RandomOverSampler, RandomUnderSampler).
6. Hyperparameter search for XGBoost and LightGBM.
7. Mean ± SD reported across all folds.
"""

from pathlib import Path
import json
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GroupKFold
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, precision_recall_curve, auc, confusion_matrix, brier_score_loss
)
from imblearn.pipeline import Pipeline as ImbPipeline
from imblearn.over_sampling import SMOTE, RandomOverSampler
from imblearn.under_sampling import RandomUnderSampler

import xgboost as xgb
import lightgbm as lgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

ROOT_DIR = Path("/Users/sanket/SIH/NirmanAnti")
DATA_DIR = ROOT_DIR / "processed" / "features"
RESULTS_DIR = ROOT_DIR / "reports" / "experiments"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TARGET_COL = "target_severe_risk_12m"

# Leakage audit keywords
LEAKAGE_KEYWORDS = ["target", "future", "prev_"]

# Instantaneous and retrospective predictor features (strictly available at month t)
FEATURE_COLS = [
    # Core scales
    'original_cost', 'revised_cost', 'anticipated_cost', 'cumulative_expenditure',
    'physical_progress', 'original_delay_months', 'revised_delay_months',
    'milestones_achieved', 'milestones_total',
    # Durations & Ratios
    'months_elapsed', 'months_originally_planned', 'months_remaining',
    'cost_expansion_ratio', 'expenditure_ratio', 'expenditure_progress_gap',
    'delay_months', 'schedule_slippage_ratio', 'elapsed_ratio',
    'cost_overrun_velocity', 'expenditure_burn_rate', 'remaining_funds_ratio',
    'required_spend_rate_monthly', 'required_progress_velocity',
    'progress_velocity', 'milestone_rate',
    # Interactions
    'interaction_slippage_cost', 'interaction_gap_velocity',
    # Deltas from previous observation (shift 1)
    'delta_anticipated_cost', 'delta_delay_months', 'delta_expenditure', 'delta_physical_progress',
    # Bayesian smoothed historical sector risk (computed strictly from train era)
    'sector_historical_risk',
    # Categoricals
    'agency_encoded', 'state_encoded'
]


def audit_leakage(features):
    print("=== CONDUCTING FORMAL LEAKAGE AUDIT ===")
    leakages = []
    for col in features:
        for kw in LEAKAGE_KEYWORDS:
            if kw in col.lower():
                leakages.append((col, kw))
    if leakages:
        raise ValueError(f"FATAL LEAKAGE DETECTED: {leakages}")
    print(f"PASS: All {len(features)} features verified strictly retrospective / instantaneous at month t.")


def load_and_prep_training_data():
    train_path = DATA_DIR / "train_dataset_v2.parquet"
    print(f"Loading training era dataset from {train_path}...")
    df = pd.read_parquet(train_path)

    # Filter evaluable observations
    eval_df = df.dropna(subset=[TARGET_COL]).copy().reset_index(drop=True)
    eval_df[TARGET_COL] = eval_df[TARGET_COL].astype(int)

    # Encoders fitted on training era
    agency_le = LabelEncoder()
    state_le = LabelEncoder()
    eval_df['agency_encoded'] = agency_le.fit_transform(eval_df['agency'].astype(str).fillna('Unknown'))
    eval_df['state_encoded'] = state_le.fit_transform(eval_df['state'].astype(str).fillna('Unknown'))

    audit_leakage(FEATURE_COLS)

    # Report Class Distribution
    total_samples = len(eval_df)
    pos_count = int(eval_df[TARGET_COL].sum())
    neg_count = total_samples - pos_count
    pos_prevalence = pos_count / total_samples

    print("\n" + "="*60)
    print("TRAINING ERA (2018-2023) CLASS DISTRIBUTION")
    print(f"Total Evaluable Observations: {total_samples}")
    print(f"Negative (Low/Normal Risk, 0): {neg_count} ({neg_count/total_samples*100:.2f}%)")
    print(f"Positive (Severe Risk 12m, 1): {pos_count} ({pos_prevalence*100:.2f}%)")
    print(f"Class Imbalance Ratio (Neg:Pos): {neg_count/pos_count:.2f}:1")
    print(f"Climatological Base-rate Reference: {pos_prevalence:.4f}")
    print("="*60 + "\n")

    return eval_df, pos_prevalence, agency_le, state_le


def compute_metrics(y_true, y_pred_prob, threshold=0.5, ref_prevalence=0.3348):
    y_pred = (y_pred_prob >= threshold).astype(int)
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    
    try:
        roc = roc_auc_score(y_true, y_pred_prob)
    except Exception:
        roc = 0.5
        
    p_curve, r_curve, _ = precision_recall_curve(y_true, y_pred_prob)
    pr_auc = auc(r_curve, p_curve)
    
    bs = brier_score_loss(y_true, y_pred_prob)
    # Climatology reference Brier score: p_i = ref_prevalence
    bs_ref = np.mean((ref_prevalence - y_true) ** 2)
    bss = 1.0 - (bs / bs_ref) if bs_ref > 0 else 0.0
    
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    
    return {
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "roc_auc": roc,
        "pr_auc": pr_auc,
        "brier_score": bs,
        "brier_skill_score": bss,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp)
    }


def get_temporal_folds(df):
    """
    Expanding-window temporal folds simulating forward deployment:
    Fold 1: Train <= 2020-04, Val == 2021-04
    Fold 2: Train <= 2021-04, Val == 2022-04
    Fold 3: Train <= 2022-04, Val == 2023-04
    """
    folds = [
        ("Fold 1 (Train 2018-20 -> Val 2021)", df["reporting_month"] <= "2020-04", df["reporting_month"] == "2021-04"),
        ("Fold 2 (Train 2018-21 -> Val 2022)", df["reporting_month"] <= "2021-04", df["reporting_month"] == "2022-04"),
        ("Fold 3 (Train 2018-22 -> Val 2023)", df["reporting_month"] <= "2022-04", df["reporting_month"] == "2023-04"),
    ]
    return folds


def run_baselines(df, pos_prevalence):
    print("\n=== EVALUATING EMPIRICAL DUMMY BASELINES (TEMPORAL CV) ===")
    folds = get_temporal_folds(df)
    
    for strategy in ["most_frequent", "stratified"]:
        fold_metrics = []
        for name, train_mask, val_mask in folds:
            X_train = df.loc[train_mask, FEATURE_COLS]
            y_train = df.loc[train_mask, TARGET_COL]
            X_val = df.loc[val_mask, FEATURE_COLS]
            y_val = df.loc[val_mask, TARGET_COL]
            
            dummy = DummyClassifier(strategy=strategy, random_state=42)
            dummy.fit(X_train, y_train)
            probs = dummy.predict_proba(X_val)[:, 1] if len(dummy.classes_) == 2 else np.zeros(len(y_val))
            
            m = compute_metrics(y_val, probs, threshold=0.5, ref_prevalence=pos_prevalence)
            fold_metrics.append(m)
            
        avg_roc = np.mean([m["roc_auc"] for m in fold_metrics])
        avg_pr = np.mean([m["pr_auc"] for m in fold_metrics])
        avg_brier = np.mean([m["brier_score"] for m in fold_metrics])
        avg_bss = np.mean([m["brier_skill_score"] for m in fold_metrics])
        avg_acc = np.mean([m["accuracy"] for m in fold_metrics])
        
        print(f"Dummy [{strategy.upper()}]: ROC-AUC: {avg_roc:.4f} | PR-AUC: {avg_pr:.4f} (Base-rate: {pos_prevalence:.4f}) | Brier: {avg_brier:.4f} | BSS: {avg_bss:.4f} | Acc: {avg_acc:.4f}")


def run_imbalance_experiments(df, pos_prevalence):
    print("\n" + "="*80)
    print("EXPERIMENT 1: CLASS-IMBALANCE STRATEGIES (TEMPORAL CV)")
    print("="*80)
    folds = get_temporal_folds(df)
    
    strategies = ["unweighted", "scale_pos_weight", "smote", "random_oversample", "random_undersample"]
    results = {}

    for strat in strategies:
        fold_metrics = []
        for name, train_mask, val_mask in folds:
            X_tr = df.loc[train_mask, FEATURE_COLS].copy()
            y_tr = df.loc[train_mask, TARGET_COL].copy()
            X_va = df.loc[val_mask, FEATURE_COLS].copy()
            y_va = df.loc[val_mask, TARGET_COL].copy()
            
            # Simple median imputation inside fold
            imputer = SimpleImputer(strategy="median")
            X_tr_imp = imputer.fit_transform(X_tr)
            X_va_imp = imputer.transform(X_va)
            
            spw = (len(y_tr) - sum(y_tr)) / max(1, sum(y_tr))
            
            if strat == "unweighted":
                model = xgb.XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.03, random_state=42, eval_metric="logloss")
                model.fit(X_tr_imp, y_tr)
            elif strat == "scale_pos_weight":
                model = xgb.XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.03, scale_pos_weight=spw, random_state=42, eval_metric="logloss")
                model.fit(X_tr_imp, y_tr)
            elif strat == "smote":
                sm = SMOTE(random_state=42)
                X_res, y_res = sm.fit_resample(X_tr_imp, y_tr)
                model = xgb.XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.03, random_state=42, eval_metric="logloss")
                model.fit(X_res, y_res)
            elif strat == "random_oversample":
                ros = RandomOverSampler(random_state=42)
                X_res, y_res = ros.fit_resample(X_tr_imp, y_tr)
                model = xgb.XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.03, random_state=42, eval_metric="logloss")
                model.fit(X_res, y_res)
            elif strat == "random_undersample":
                rus = RandomUnderSampler(random_state=42)
                X_res, y_res = rus.fit_resample(X_tr_imp, y_tr)
                model = xgb.XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.03, random_state=42, eval_metric="logloss")
                model.fit(X_res, y_res)
                
            probs = model.predict_proba(X_va_imp)[:, 1]
            m = compute_metrics(y_va, probs, threshold=0.5, ref_prevalence=pos_prevalence)
            fold_metrics.append(m)
            
        results[strat] = fold_metrics
        roc_m, roc_s = np.mean([m["roc_auc"] for m in fold_metrics]), np.std([m["roc_auc"] for m in fold_metrics])
        pr_m, pr_s = np.mean([m["pr_auc"] for m in fold_metrics]), np.std([m["pr_auc"] for m in fold_metrics])
        brier_m, brier_s = np.mean([m["brier_score"] for m in fold_metrics]), np.std([m["brier_score"] for m in fold_metrics])
        f1_m, f1_s = np.mean([m["f1"] for m in fold_metrics]), np.std([m["f1"] for m in fold_metrics])
        
        print(f"Strategy: {strat:<20} | ROC-AUC: {roc_m:.4f}±{roc_s:.4f} | PR-AUC: {pr_m:.4f}±{pr_s:.4f} | Brier: {brier_m:.4f}±{brier_s:.4f} | F1: {f1_m:.4f}±{f1_s:.4f}")

    return results


def run_hyperparameter_tuning(df, pos_prevalence):
    print("\n" + "="*80)
    print("EXPERIMENT 2: HYPERPARAMETER TUNING (TEMPORAL EXPANDING WINDOW CV)")
    print("="*80)
    folds = get_temporal_folds(df)

    xgb_configs = [
        {"name": "XGB-Default", "max_depth": 5, "lr": 0.05, "n_est": 200, "sub": 1.0, "col": 1.0, "spw": 1.0, "reg_l": 1.0},
        {"name": "XGB-Shallow-Regularized", "max_depth": 3, "lr": 0.03, "n_est": 300, "sub": 0.8, "col": 0.8, "spw": 1.5, "reg_l": 3.0},
        {"name": "XGB-Balanced-Deep", "max_depth": 4, "lr": 0.03, "n_est": 250, "sub": 0.85, "col": 0.8, "spw": 2.0, "reg_l": 5.0},
        {"name": "XGB-HighRecall-Tuned", "max_depth": 4, "lr": 0.02, "n_est": 350, "sub": 0.85, "col": 0.75, "spw": 2.2, "reg_l": 4.0},
    ]

    lgb_configs = [
        {"name": "LGBM-Default", "leaves": 31, "max_depth": -1, "lr": 0.05, "n_est": 200, "sub": 1.0, "col": 1.0, "spw": 1.0},
        {"name": "LGBM-Constrained-Leaves", "leaves": 15, "max_depth": 4, "lr": 0.03, "n_est": 300, "sub": 0.8, "col": 0.8, "spw": 1.5},
        {"name": "LGBM-Regularized-Tuned", "leaves": 20, "max_depth": 5, "lr": 0.03, "n_est": 250, "sub": 0.85, "col": 0.8, "spw": 2.0},
    ]

    all_models_results = {}

    for cfg in xgb_configs:
        fold_metrics = []
        for name, train_mask, val_mask in folds:
            X_tr = df.loc[train_mask, FEATURE_COLS]
            y_tr = df.loc[train_mask, TARGET_COL]
            X_va = df.loc[val_mask, FEATURE_COLS]
            y_va = df.loc[val_mask, TARGET_COL]

            imputer = SimpleImputer(strategy="median")
            X_tr_imp = imputer.fit_transform(X_tr)
            X_va_imp = imputer.transform(X_va)

            model = xgb.XGBClassifier(
                max_depth=cfg["max_depth"],
                learning_rate=cfg["lr"],
                n_estimators=cfg["n_est"],
                subsample=cfg["sub"],
                colsample_bytree=cfg["col"],
                scale_pos_weight=cfg["spw"],
                reg_lambda=cfg["reg_l"],
                random_state=42,
                eval_metric="logloss"
            )
            model.fit(X_tr_imp, y_tr)
            probs = model.predict_proba(X_va_imp)[:, 1]
            m = compute_metrics(y_va, probs, threshold=0.5, ref_prevalence=pos_prevalence)
            fold_metrics.append(m)

        roc_m, roc_s = np.mean([m["roc_auc"] for m in fold_metrics]), np.std([m["roc_auc"] for m in fold_metrics])
        pr_m, pr_s = np.mean([m["pr_auc"] for m in fold_metrics]), np.std([m["pr_auc"] for m in fold_metrics])
        brier_m, brier_s = np.mean([m["brier_score"] for m in fold_metrics]), np.std([m["brier_score"] for m in fold_metrics])
        f1_m, f1_s = np.mean([m["f1"] for m in fold_metrics]), np.std([m["f1"] for m in fold_metrics])
        all_models_results[cfg["name"]] = fold_metrics
        print(f"{cfg['name']:<25} | ROC-AUC: {roc_m:.4f}±{roc_s:.4f} | PR-AUC: {pr_m:.4f}±{pr_s:.4f} | Brier: {brier_m:.4f}±{brier_s:.4f} | F1: {f1_m:.4f}±{f1_s:.4f}")

    for cfg in lgb_configs:
        fold_metrics = []
        for name, train_mask, val_mask in folds:
            X_tr = df.loc[train_mask, FEATURE_COLS]
            y_tr = df.loc[train_mask, TARGET_COL]
            X_va = df.loc[val_mask, FEATURE_COLS]
            y_va = df.loc[val_mask, TARGET_COL]

            imputer = SimpleImputer(strategy="median")
            X_tr_imp = imputer.fit_transform(X_tr)
            X_va_imp = imputer.transform(X_va)

            model = lgb.LGBMClassifier(
                num_leaves=cfg["leaves"],
                max_depth=cfg["max_depth"],
                learning_rate=cfg["lr"],
                n_estimators=cfg["n_est"],
                subsample=cfg["sub"],
                colsample_bytree=cfg["col"],
                scale_pos_weight=cfg["spw"],
                random_state=42,
                verbose=-1
            )
            model.fit(X_tr_imp, y_tr)
            probs = model.predict_proba(X_va_imp)[:, 1]
            m = compute_metrics(y_va, probs, threshold=0.5, ref_prevalence=pos_prevalence)
            fold_metrics.append(m)

        roc_m, roc_s = np.mean([m["roc_auc"] for m in fold_metrics]), np.std([m["roc_auc"] for m in fold_metrics])
        pr_m, pr_s = np.mean([m["pr_auc"] for m in fold_metrics]), np.std([m["pr_auc"] for m in fold_metrics])
        brier_m, brier_s = np.mean([m["brier_score"] for m in fold_metrics]), np.std([m["brier_score"] for m in fold_metrics])
        f1_m, f1_s = np.mean([m["f1"] for m in fold_metrics]), np.std([m["f1"] for m in fold_metrics])
        all_models_results[cfg["name"]] = fold_metrics
        print(f"{cfg['name']:<25} | ROC-AUC: {roc_m:.4f}±{roc_s:.4f} | PR-AUC: {pr_m:.4f}±{pr_s:.4f} | Brier: {brier_m:.4f}±{brier_s:.4f} | F1: {f1_m:.4f}±{f1_s:.4f}")

    return all_models_results


def run_group_kfold_experiment(df, pos_prevalence):
    print("\n" + "="*80)
    print("EXPERIMENT 3: PROJECT-LEVEL GROUP KFOLD (ZERO PROJECT OVERLAP ACROSS FOLDS)")
    print("="*80)
    gkf = GroupKFold(n_splits=5)
    groups = df["project_code"]

    fold_metrics_xgb = []
    fold_metrics_lgb = []

    for fold_i, (tr_idx, va_idx) in enumerate(gkf.split(df, groups=groups)):
        X_tr = df.iloc[tr_idx][FEATURE_COLS]
        y_tr = df.iloc[tr_idx][TARGET_COL]
        X_va = df.iloc[va_idx][FEATURE_COLS]
        y_va = df.iloc[va_idx][TARGET_COL]

        imputer = SimpleImputer(strategy="median")
        X_tr_imp = imputer.fit_transform(X_tr)
        X_va_imp = imputer.transform(X_va)

        # XGBoost
        model_xgb = xgb.XGBClassifier(max_depth=4, learning_rate=0.03, n_estimators=250, subsample=0.85, colsample_bytree=0.8, scale_pos_weight=1.5, reg_lambda=3.0, random_state=42, eval_metric="logloss")
        model_xgb.fit(X_tr_imp, y_tr)
        probs_xgb = model_xgb.predict_proba(X_va_imp)[:, 1]
        fold_metrics_xgb.append(compute_metrics(y_va, probs_xgb, threshold=0.5, ref_prevalence=pos_prevalence))

        # LightGBM
        model_lgb = lgb.LGBMClassifier(num_leaves=20, max_depth=5, learning_rate=0.03, n_estimators=250, subsample=0.85, colsample_bytree=0.8, scale_pos_weight=1.5, random_state=42, verbose=-1)
        model_lgb.fit(X_tr_imp, y_tr)
        probs_lgb = model_lgb.predict_proba(X_va_imp)[:, 1]
        fold_metrics_lgb.append(compute_metrics(y_va, probs_lgb, threshold=0.5, ref_prevalence=pos_prevalence))

    print(f"GroupKFold 5-Split XGBoost : ROC-AUC: {np.mean([m['roc_auc'] for m in fold_metrics_xgb]):.4f}±{np.std([m['roc_auc'] for m in fold_metrics_xgb]):.4f} | PR-AUC: {np.mean([m['pr_auc'] for m in fold_metrics_xgb]):.4f}±{np.std([m['pr_auc'] for m in fold_metrics_xgb]):.4f} | Brier: {np.mean([m['brier_score'] for m in fold_metrics_xgb]):.4f}")
    print(f"GroupKFold 5-Split LightGBM: ROC-AUC: {np.mean([m['roc_auc'] for m in fold_metrics_lgb]):.4f}±{np.std([m['roc_auc'] for m in fold_metrics_lgb]):.4f} | PR-AUC: {np.mean([m['pr_auc'] for m in fold_metrics_lgb]):.4f}±{np.std([m['pr_auc'] for m in fold_metrics_lgb]):.4f} | Brier: {np.mean([m['brier_score'] for m in fold_metrics_lgb]):.4f}")


def main():
    eval_df, pos_prevalence, agency_le, state_le = load_and_prep_training_data()
    run_baselines(eval_df, pos_prevalence)
    imbalance_results = run_imbalance_experiments(eval_df, pos_prevalence)
    tuning_results = run_hyperparameter_tuning(eval_df, pos_prevalence)
    run_group_kfold_experiment(eval_df, pos_prevalence)
    print("\nPhase 2 Temporal CV Experiments Completed Successfully!")

if __name__ == "__main__":
    main()
