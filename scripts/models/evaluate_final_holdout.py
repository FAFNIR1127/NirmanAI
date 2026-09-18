"""
evaluate_final_holdout.py

Phase 4: Final Locked Evaluation & Publication-Grade Scientific Artifacts.
The 2024-2025 holdout is evaluated ONCE with all models and thresholds locked.

Outputs:
1. Holdout PR Curve, ROC Curve, Calibration Reliability Curve (matplotlib PNGs).
2. Brier Score, Brier Skill Score, Confusion Matrices.
3. Tree SHAP Analysis: Global summary, Top Risk Drivers & Protective Factors.
4. Comprehensive Error Analysis (Dissected by Sector, Cost Tier, and Project Age).
5. Temporal Stability Breakdown (2024 vs 2025).
"""

from pathlib import Path
import json
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, precision_recall_curve, auc, average_precision_score, roc_curve,
    confusion_matrix, brier_score_loss
)
import shap

ROOT_DIR = Path("/Users/sanket/SIH/NirmanAnti")
DATA_DIR = ROOT_DIR / "processed" / "features"
MODELS_DIR = ROOT_DIR / "models"
VERSION_DIR = MODELS_DIR / "risk_engine_v2"
FIGURES_DIR = ROOT_DIR / "reports" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR = ROOT_DIR / "reports" / "model_evaluation"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

TARGET_COL = "target_severe_risk_12m"


def load_holdout_and_models():
    holdout_path = DATA_DIR / "val_holdout_v2.parquet"
    print(f"Loading final locked holdout from {holdout_path}...")
    df = pd.read_parquet(holdout_path)
    eval_df = df.dropna(subset=[TARGET_COL]).copy().reset_index(drop=True)
    eval_df[TARGET_COL] = eval_df[TARGET_COL].astype(int)

    # Load frozen schema and encoders
    with open(VERSION_DIR / "feature_schema.json") as f:
        schema = json.load(f)
    feature_cols = schema["feature_columns"]

    with open(VERSION_DIR / "threshold_config.json") as f:
        th_config = json.load(f)
    op_threshold = th_config["operational_threshold"]

    agency_le = joblib.load(VERSION_DIR / "agency_encoder.joblib")
    state_le = joblib.load(VERSION_DIR / "state_encoder.joblib")
    imputer = joblib.load(VERSION_DIR / "imputer.joblib")
    base_model = joblib.load(VERSION_DIR / "xgboost_base.joblib")
    calibrator = joblib.load(VERSION_DIR / "calibrator.joblib")

    # Encode test data safely (unknown categories map to unknown or 0)
    known_agencies = set(agency_le.classes_)
    known_states = set(state_le.classes_)
    eval_df["agency_clean"] = eval_df["agency"].astype(str).apply(lambda x: x if x in known_agencies else "Unknown")
    eval_df["state_clean"] = eval_df["state"].astype(str).apply(lambda x: x if x in known_states else "Unknown")
    eval_df["agency_encoded"] = agency_le.transform(eval_df["agency_clean"])
    eval_df["state_encoded"] = state_le.transform(eval_df["state_clean"])

    X_test = eval_df[feature_cols]
    y_test = eval_df[TARGET_COL]

    X_test_imp = imputer.transform(X_test)
    X_test_df = pd.DataFrame(X_test_imp, columns=feature_cols)

    return eval_df, X_test, X_test_df, y_test, feature_cols, op_threshold, base_model, calibrator


def run_evaluation():
    print("=== PHASE 4: FINAL EVALUATION ON LOCKED 2024-2025 HOLDOUT ===")
    eval_df, X_test, X_test_df, y_test, feature_cols, op_threshold, base_model, calibrator = load_holdout_and_models()

    total_test = len(y_test)
    pos_test = int(y_test.sum())
    neg_test = total_test - pos_test
    test_prevalence = pos_test / total_test

    print(f"Locked Holdout Sample: {total_test} total ({pos_test} positive: {test_prevalence*100:.2f}%, {neg_test} negative)")

    # 1. Predictions
    raw_probs = base_model.predict_proba(X_test_df)[:, 1]
    cal_probs = calibrator.predict_proba(X_test_df)[:, 1]

    # 2. Holdout Metrics
    roc = roc_auc_score(y_test, cal_probs)
    p_arr, r_arr, _ = precision_recall_curve(y_test, cal_probs)
    pr_auc = average_precision_score(y_test, cal_probs)
    brier = brier_score_loss(y_test, cal_probs)
    brier_ref = np.mean((test_prevalence - y_test) ** 2)
    bss = 1.0 - (brier / brier_ref)

    # Operational decision metrics (at op_threshold=0.28)
    preds_op = (cal_probs >= op_threshold).astype(int)
    acc_op = accuracy_score(y_test, preds_op)
    prec_op = precision_score(y_test, preds_op, zero_division=0)
    rec_op = recall_score(y_test, preds_op, zero_division=0)
    f1_op = f1_score(y_test, preds_op, zero_division=0)
    cm_op = confusion_matrix(y_test, preds_op)
    tn_op, fp_op, fn_op, tp_op = cm_op.ravel()

    # Default decision metrics (at 0.50)
    preds_50 = (cal_probs >= 0.50).astype(int)
    prec_50 = precision_score(y_test, preds_50, zero_division=0)
    rec_50 = recall_score(y_test, preds_50, zero_division=0)
    f1_50 = f1_score(y_test, preds_50, zero_division=0)
    cm_50 = confusion_matrix(y_test, preds_50)
    tn_50, fp_50, fn_50, tp_50 = cm_50.ravel()

    print("\n" + "="*70)
    print("FINAL SCIENTIFIC METRICS (LOCKED 2024-2025 HOLDOUT)")
    print("="*70)
    print(f"ROC-AUC:                         {roc:.4f}")
    print(f"PR-AUC:                          {pr_auc:.4f} (Base-rate prevalence: {test_prevalence:.4f})")
    print(f"Brier Score:                     {brier:.4f}")
    print(f"Brier Skill Score (vs base-rate):{bss:.4f}")
    print(f"\nOperational Threshold ({op_threshold:.2f}):")
    print(f"  Accuracy:                      {acc_op*100:.2f}%")
    print(f"  Precision:                     {prec_op*100:.2f}%")
    print(f"  Recall (Severe Risk Caught):   {rec_op*100:.2f}% (TP: {tp_op}, FN: {fn_op})")
    print(f"  F1-Score:                      {f1_op:.4f}")
    print(f"  Confusion Matrix:              TN={tn_op}, FP={fp_op}, FN={fn_op}, TP={tp_op}")
    print(f"\nDefault Threshold (0.50):")
    print(f"  Precision:                     {prec_50*100:.2f}%")
    print(f"  Recall:                        {rec_50*100:.2f}% (TP: {tp_50}, FN: {fn_50})")
    print(f"  F1-Score:                      {f1_50:.4f}")
    print(f"  Confusion Matrix:              TN={tn_50}, FP={fp_50}, FN={fn_50}, TP={tp_50}")
    print("="*70 + "\n")

    # 3. Generate Publication-Grade Matplotlib Visualizations
    # Figure 1: ROC Curve
    fpr, tpr, _ = roc_curve(y_test, cal_probs)
    plt.figure(figsize=(7, 6))
    plt.plot(fpr, tpr, color="#2563eb", lw=2.5, label=f"Calibrated XGBoost (AUC = {roc:.4f})")
    plt.plot([0, 1], [0, 1], color="#94a3b8", lw=1.5, linestyle="--", label="Chance Diagonal (AUC = 0.5000)")
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("False Positive Rate (1 - Specificity)", fontsize=11, fontweight="bold")
    plt.ylabel("True Positive Rate (Recall / Sensitivity)", fontsize=11, fontweight="bold")
    plt.title("Receiver Operating Characteristic (ROC) Curve - 2024-2025 Holdout", fontsize=12, fontweight="bold", pad=12)
    plt.legend(loc="lower right", frameon=True)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    roc_fig_path = FIGURES_DIR / "roc_curve_holdout.png"
    plt.savefig(roc_fig_path, dpi=300)
    plt.close()
    print(f"Saved ROC Curve figure to {roc_fig_path}")

    # Figure 2: Precision-Recall Curve
    plt.figure(figsize=(7, 6))
    plt.plot(r_arr, p_arr, color="#10b981", lw=2.5, label=f"Calibrated XGBoost (PR-AUC = {pr_auc:.4f})")
    plt.axhline(y=test_prevalence, color="#ef4444", lw=1.5, linestyle="--", label=f"No-Skill Climatology Base Rate ({test_prevalence:.4f})")
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("Recall", fontsize=11, fontweight="bold")
    plt.ylabel("Precision", fontsize=11, fontweight="bold")
    plt.title("Precision-Recall (PR) Curve - 2024-2025 Holdout", fontsize=12, fontweight="bold", pad=12)
    plt.legend(loc="upper right", frameon=True)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    pr_fig_path = FIGURES_DIR / "pr_curve_holdout.png"
    plt.savefig(pr_fig_path, dpi=300)
    plt.close()
    print(f"Saved PR Curve figure to {pr_fig_path}")

    # Figure 3: Calibration Reliability Diagram
    prob_true_raw, prob_pred_raw = calibration_curve(y_test, raw_probs, n_bins=10)
    prob_true_cal, prob_pred_cal = calibration_curve(y_test, cal_probs, n_bins=10)
    plt.figure(figsize=(7, 6))
    plt.plot([0, 1], [0, 1], color="#94a3b8", lw=1.5, linestyle="--", label="Perfect Calibration")
    plt.plot(prob_pred_raw, prob_true_raw, "s-", color="#f59e0b", lw=2, label="Uncalibrated XGBoost")
    plt.plot(prob_pred_cal, prob_true_cal, "o-", color="#8b5cf6", lw=2.5, label=f"Isotonic Calibrated (Brier={brier:.4f})")
    plt.xlabel("Mean Predicted Probability", fontsize=11, fontweight="bold")
    plt.ylabel("Fraction of Positives (True Frequency)", fontsize=11, fontweight="bold")
    plt.title("Reliability Diagram (Probability Calibration Curve)", fontsize=12, fontweight="bold", pad=12)
    plt.legend(loc="lower right", frameon=True)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    cal_fig_path = FIGURES_DIR / "calibration_curve_holdout.png"
    plt.savefig(cal_fig_path, dpi=300)
    plt.close()
    print(f"Saved Calibration Curve figure to {cal_fig_path}")

    # 4. SHAP Tree Explanations
    print("\nComputing Tree SHAP explainers on holdout...")
    explainer = shap.TreeExplainer(base_model)
    shap_values = explainer.shap_values(X_test_df)

    # Summary plot
    plt.figure(figsize=(10, 8))
    shap.summary_plot(shap_values, X_test_df, feature_names=feature_cols, show=False, max_display=15)
    plt.title("SHAP Feature Importance & Attribution Distribution", fontsize=13, fontweight="bold", pad=12)
    plt.tight_layout()
    shap_fig_path = FIGURES_DIR / "shap_summary_holdout.png"
    plt.savefig(shap_fig_path, dpi=300)
    plt.close()
    print(f"Saved SHAP Summary figure to {shap_fig_path}")

    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    shap_ranking = sorted(zip(feature_cols, mean_abs_shap), key=lambda x: x[1], reverse=True)

    # 5. Granular Error Analysis
    eval_df["predicted_prob"] = cal_probs
    eval_df["predicted_class"] = preds_op
    eval_df["true_class"] = y_test

    eval_df["error_type"] = "TN"
    eval_df.loc[(eval_df["true_class"] == 0) & (eval_df["predicted_class"] == 1), "error_type"] = "FP"
    eval_df.loc[(eval_df["true_class"] == 1) & (eval_df["predicted_class"] == 0), "error_type"] = "FN"
    eval_df.loc[(eval_df["true_class"] == 1) & (eval_df["predicted_class"] == 1), "error_type"] = "TP"

    # Dissect by Sector
    sector_breakdown = eval_df.groupby("sector").agg(
        total=("project_code", "count"),
        tp=("error_type", lambda x: (x == "TP").sum()),
        fp=("error_type", lambda x: (x == "FP").sum()),
        fn=("error_type", lambda x: (x == "FN").sum()),
        tn=("error_type", lambda x: (x == "TN").sum()),
        recall=("error_type", lambda x: (x == "TP").sum() / max(1, ((x == "TP") | (x == "FN")).sum())),
        precision=("error_type", lambda x: (x == "TP").sum() / max(1, ((x == "TP") | (x == "FP")).sum()))
    ).reset_index().to_dict(orient="records")

    # Dissect by Project Cost Tier
    eval_df["cost_tier"] = pd.cut(
        eval_df["original_cost"],
        bins=[-np.inf, 500, 5000, np.inf],
        labels=["Small (<₹500 Cr)", "Medium (₹500-5000 Cr)", "Mega (>₹5000 Cr)"]
    )
    cost_breakdown = eval_df.groupby("cost_tier", observed=False).agg(
        total=("project_code", "count"),
        tp=("error_type", lambda x: (x == "TP").sum()),
        fp=("error_type", lambda x: (x == "FP").sum()),
        fn=("error_type", lambda x: (x == "FN").sum()),
        tn=("error_type", lambda x: (x == "TN").sum()),
        recall=("error_type", lambda x: (x == "TP").sum() / max(1, ((x == "TP") | (x == "FN")).sum())),
        precision=("error_type", lambda x: (x == "TP").sum() / max(1, ((x == "TP") | (x == "FP")).sum()))
    ).reset_index().to_dict(orient="records")

    # 6. Temporal Stability Breakdown (2024 vs 2025)
    temporal_stability = []
    for month in sorted(eval_df["reporting_month"].unique()):
        sub = eval_df[eval_df["reporting_month"] == month]
        if sub[TARGET_COL].nunique() > 1:
            m_roc = roc_auc_score(sub[TARGET_COL], sub["predicted_prob"])
            p_sub, r_sub, _ = precision_recall_curve(sub[TARGET_COL], sub["predicted_prob"])
            m_pr = auc(r_sub, p_sub)
        else:
            m_roc, m_pr = 0.5, float(sub[TARGET_COL].mean())
        temporal_stability.append({
            "reporting_month": month,
            "observations": len(sub),
            "positive_rate": float(sub[TARGET_COL].mean()),
            "roc_auc": float(m_roc),
            "pr_auc": float(m_pr)
        })

    # Save comprehensive metrics JSON
    evaluation_report = {
        "evaluation_period": "2024-04 to 2025-04 (Locked Holdout)",
        "sample_size": total_test,
        "positive_count": pos_test,
        "negative_count": neg_test,
        "test_prevalence": test_prevalence,
        "operational_threshold": op_threshold,
        "metrics": {
            "roc_auc": float(roc),
            "pr_auc": float(pr_auc),
            "brier_score": float(brier),
            "brier_skill_score": float(bss),
            "operational": {
                "accuracy": float(acc_op),
                "precision": float(prec_op),
                "recall": float(rec_op),
                "f1": float(f1_op),
                "tn": int(tn_op),
                "fp": int(fp_op),
                "fn": int(fn_op),
                "tp": int(tp_op)
            },
            "default_50": {
                "precision": float(prec_50),
                "recall": float(rec_50),
                "f1": float(f1_50),
                "tn": int(tn_50),
                "fp": int(fp_50),
                "fn": int(fn_50),
                "tp": int(tp_50)
            }
        },
        "shap_feature_importance_top15": [{"feature": f, "importance": float(imp)} for f, imp in shap_ranking[:15]],
        "sector_breakdown": sector_breakdown,
        "cost_tier_breakdown": cost_breakdown,
        "temporal_stability": temporal_stability
    }

    report_path = REPORTS_DIR / "final_holdout_evaluation_report.json"
    with open(report_path, "w") as f:
        json.dump(evaluation_report, f, indent=2)

    print(f"\nFinal Scientific Evaluation Report saved to {report_path}")
    return evaluation_report

if __name__ == "__main__":
    run_evaluation()
