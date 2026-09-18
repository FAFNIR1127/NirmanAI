"""
analyze_temporal_drift.py

Calculates Population Stability Index (PSI), Kolmogorov-Smirnov (KS) test,
distribution shift, and SHAP directionality between:
- Training Era (2018-2023)
- Locked Holdout (2024-2025)
- Live Dataset (2026)
"""

from pathlib import Path
import json
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from scipy import stats
import joblib

ROOT_DIR = Path("/Users/sanket/SIH/NirmanAnti")
DATA_DIR = ROOT_DIR / "processed" / "features"
VERSION_DIR = ROOT_DIR / "models" / "risk_engine_v2"
REPORTS_DIR = ROOT_DIR / "reports" / "model_evaluation"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def calculate_psi(expected, actual, num_buckets=10):
    """
    Computes Population Stability Index (PSI) between expected (train) and actual (holdout).
    """
    # Remove NaNs
    exp_clean = expected.dropna()
    act_clean = actual.dropna()

    if len(exp_clean) == 0 or len(act_clean) == 0:
        return np.nan

    # Determine quantile bins on expected
    percentiles = np.linspace(0, 100, num_buckets + 1)
    try:
        bins = np.percentile(exp_clean, percentiles)
        bins = np.unique(bins)
        if len(bins) < 2:
            return 0.0
    except Exception:
        return np.nan

    # Add bounds
    bins[0] = -np.inf
    bins[-1] = np.inf

    exp_counts, _ = np.histogram(exp_clean, bins=bins)
    act_counts, _ = np.histogram(act_clean, bins=bins)

    exp_pct = np.maximum(exp_counts / len(exp_clean), 1e-4)
    act_pct = np.maximum(act_counts / len(act_clean), 1e-4)

    psi_val = np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct))
    return float(psi_val)


def run_drift_analysis():
    print("=" * 80)
    print("TEMPORAL POPULATION & FEATURE DRIFT ANALYSIS (2018-2023 vs 2024-2025)")
    print("=" * 80)

    train_path = DATA_DIR / "train_dataset_v2.parquet"
    val_path = DATA_DIR / "val_holdout_v2.parquet"

    train_df = pd.read_parquet(train_path)
    val_df = pd.read_parquet(val_path)

    with open(VERSION_DIR / "feature_schema.json") as f:
        schema = json.load(f)
    feature_cols = schema["feature_columns"]

    key_features = [
        "original_cost", "anticipated_cost", "cumulative_expenditure", "physical_progress",
        "delay_months", "cost_expansion_ratio", "schedule_slippage_ratio", "expenditure_ratio",
        "elapsed_ratio", "cost_overrun_velocity", "expenditure_burn_rate", "remaining_funds_ratio",
        "required_spend_rate_monthly", "required_progress_velocity", "delta_expenditure",
        "sector_historical_risk"
    ]

    drift_results = []
    print(f"{'Feature':<28} | {'PSI':<8} | {'Drift Status':<15} | {'KS Stat':<8} | {'p-value':<9} | {'Train Mean':<12} | {'Holdout Mean':<12}")
    print("-" * 105)

    for feat in key_features:
        tr_s = train_df[feat].dropna()
        va_s = val_df[feat].dropna()

        psi = calculate_psi(tr_s, va_s, num_buckets=10)
        ks_stat, p_val = stats.ks_2samp(tr_s, va_s) if len(tr_s) > 0 and len(va_s) > 0 else (np.nan, np.nan)
        tr_m = tr_s.mean() if len(tr_s) > 0 else np.nan
        va_m = va_s.mean() if len(va_s) > 0 else np.nan

        if psi < 0.10:
            status = "Stable (PSI<0.1)"
        elif psi < 0.25:
            status = "Moderate Drift"
        else:
            status = "SIGNIFICANT DRIFT"

        drift_results.append({
            "feature": feat,
            "psi": round(psi, 4) if pd.notna(psi) else None,
            "drift_category": status,
            "ks_statistic": round(float(ks_stat), 4) if pd.notna(ks_stat) else None,
            "ks_p_value": round(float(p_val), 6) if pd.notna(p_val) else None,
            "train_mean": round(float(tr_m), 4) if pd.notna(tr_m) else None,
            "holdout_mean": round(float(va_m), 4) if pd.notna(va_m) else None
        })

        print(f"{feat:<28} | {psi:<8.4f} | {status:<15} | {ks_stat:<8.4f} | {p_val:<9.2e} | {tr_m:<12.2f} | {va_m:<12.2f}")

    # Sector Distribution Drift
    print("\n--- SECTOR COMPOSITION SHIFT (TRAIN vs HOLDOUT) ---")
    tr_sec = train_df["sector"].value_counts(normalize=True) * 100.0
    va_sec = val_df["sector"].value_counts(normalize=True) * 100.0
    all_secs = sorted(set(tr_sec.index).union(set(va_sec.index)))

    print(f"{'Sector':<30} | {'Train 2018-23 (%)':<18} | {'Holdout 2024-25 (%)':<20} | {'Diff (%)':<10}")
    print("-" * 85)
    sector_shifts = []
    for s in all_secs:
        tp = tr_sec.get(s, 0.0)
        vp = va_sec.get(s, 0.0)
        diff = vp - tp
        sector_shifts.append({"sector": s, "train_pct": round(tp, 2), "holdout_pct": round(vp, 2), "diff": round(diff, 2)})
        print(f"{s:<30} | {tp:<18.2f} | {vp:<20.2f} | {diff:<+10.2f}")

    # SHAP Directionality Analysis on Holdout
    print("\n--- RIGOROUS SHAP ATTRIBUTION DIRECTIONALITY ---")
    base_model = joblib.load(VERSION_DIR / "xgboost_base.joblib")
    imputer = joblib.load(VERSION_DIR / "imputer.joblib")

    # Load holdout evaluable samples
    eval_ho = val_df.dropna(subset=["target_severe_risk_12m"]).copy().reset_index(drop=True)
    agency_le = joblib.load(VERSION_DIR / "agency_encoder.joblib")
    state_le = joblib.load(VERSION_DIR / "state_encoder.joblib")
    eval_ho["agency_clean"] = eval_ho["agency"].astype(str).apply(lambda x: x if x in set(agency_le.classes_) else "Unknown")
    eval_ho["state_clean"] = eval_ho["state"].astype(str).apply(lambda x: x if x in set(state_le.classes_) else "Unknown")
    eval_ho["agency_encoded"] = agency_le.transform(eval_ho["agency_clean"])
    eval_ho["state_encoded"] = state_le.transform(eval_ho["state_clean"])

    X_ho = eval_ho[feature_cols]
    X_ho_imp = imputer.transform(X_ho)
    X_ho_df = pd.DataFrame(X_ho_imp, columns=feature_cols)

    import shap
    explainer = shap.TreeExplainer(base_model)
    shap_vals = explainer.shap_values(X_ho_df)

    shap_directionality = []
    print(f"{'Feature':<28} | {'Mean |SHAP|':<12} | {'Spearman Rho':<14} | {'Empirical Relationship'}")
    print("-" * 80)
    for i, col in enumerate(feature_cols):
        m_abs = float(np.abs(shap_vals[:, i]).mean())
        # Correlation between feature value and SHAP attribution
        rho, p = stats.spearmanr(X_ho_df[col], shap_vals[:, i])
        if pd.isna(rho) or abs(rho) < 0.05:
            rel = "Nonlinear / Neutral"
        elif rho > 0.3:
            rel = "High value strongly increases risk (+)"
        elif rho > 0.05:
            rel = "High value moderately increases risk (+)"
        elif rho < -0.3:
            rel = "High value strongly decreases risk / protective (-)"
        else:
            rel = "High value moderately decreases risk (-)"

        shap_directionality.append({
            "feature": col,
            "mean_abs_shap": round(m_abs, 4),
            "spearman_rho": round(float(rho), 4) if pd.notna(rho) else None,
            "directionality": rel
        })

    # Sort by mean abs shap
    shap_directionality.sort(key=lambda x: x["mean_abs_shap"], reverse=True)
    for row in shap_directionality[:15]:
        print(f"{row['feature']:<28} | {row['mean_abs_shap']:<12.4f} | {str(row['spearman_rho']):<14} | {row['directionality']}")

    # Save comprehensive drift report
    report = {
        "feature_drift_table": drift_results,
        "sector_shifts": sector_shifts,
        "shap_directionality_top15": shap_directionality[:15]
    }
    out_path = REPORTS_DIR / "temporal_drift_and_shap_directionality.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nDrift and Directionality Report saved to {out_path}")


if __name__ == "__main__":
    run_drift_analysis()
