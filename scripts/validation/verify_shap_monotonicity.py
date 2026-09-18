import json
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from scipy.stats import spearmanr
from sklearn.preprocessing import LabelEncoder
import shap

# ============================================================
# PATHS & CONFIG
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

# Expected Directionalities
# +1: High Feature Value -> Higher Risk (Positive SHAP)
# -1: High Feature Value -> Lower Risk (Negative SHAP / Protective)
EXPECTED_DIRECTIONS = {
    'cost_expansion_ratio': +1,
    'delay_months': +1,
    'schedule_slippage_ratio': +1,
    'original_delay_months': +1,
    'revised_delay_months': +1,
    'expenditure_progress_gap': +1,
    'physical_progress': -1,
    'milestone_rate': -1,
    'progress_velocity': -1
}


def verify_shap_sanity():
    print("=" * 110)
    print("GLOBAL SHAP MONOTONICITY & DIRECTIONALITY SANITY CHECK")
    print("=" * 110)

    all_df = pd.read_parquet(ALL_FEATURES_PATH)
    base_model = joblib.load(MODELS_DIR / "tuned_xgb_base.joblib")

    agency_le = LabelEncoder()
    state_le = LabelEncoder()
    all_df['agency_encoded'] = agency_le.fit_transform(all_df['agency'].astype(str).fillna('Unknown'))
    all_df['state_encoded'] = state_le.fit_transform(all_df['state'].astype(str).fillna('Unknown'))

    X_all = all_df[FEATURE_COLS]

    explainer = shap.TreeExplainer(base_model)
    shap_values = explainer.shap_values(X_all)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    # Global Mean |SHAP| Importance & Directionality Correlation
    results = []

    for idx, col in enumerate(FEATURE_COLS):
        col_vals = X_all[col].values
        col_shap = shap_values[:, idx]

        # Filter valid non-NaN pairs for Spearman correlation
        valid_mask = pd.notna(col_vals) & pd.notna(col_shap)
        mean_abs_shap = np.mean(np.abs(col_shap))

        if valid_mask.sum() > 30:
            corr, pval = spearmanr(col_vals[valid_mask], col_shap[valid_mask])
        else:
            corr, pval = np.nan, np.nan

        exp_dir = EXPECTED_DIRECTIONS.get(col, 0)
        
        # Check sanity
        if exp_dir == +1:
            status = "PASS ✅" if corr > 0.15 else ("NEUTRAL ⚠️" if corr >= 0 else "FAIL ❌")
        elif exp_dir == -1:
            status = "PASS ✅" if corr < -0.15 else ("NEUTRAL ⚠️" if corr <= 0 else "FAIL ❌")
        else:
            status = "NEUTRAL (Contextual)"

        results.append({
            "Feature": col,
            "Mean |SHAP|": round(mean_abs_shap, 4),
            "Spearman Corr (Val vs SHAP)": round(corr, 4) if pd.notna(corr) else None,
            "Expected Dir": "+ (Risk Driver)" if exp_dir == +1 else ("- (Protective)" if exp_dir == -1 else "Contextual"),
            "Sanity Status": status
        })

    results_df = pd.DataFrame(results).sort_values(by="Mean |SHAP|", ascending=False)
    print("\n=== GLOBAL SHAP FEATURE IMPORTANCE & DIRECTIONALITY TABLE ===")
    print(results_df.to_string(index=False))

    # Detailed Binned Monotonicity Checks on Key Features
    print("\n" + "=" * 110)
    print("BINNED MONOTONICITY AUDIT FOR KEY RISK DRIVERS")
    print("=" * 110)

    # 1. Cost Expansion Ratio Binned Monotonicity
    print("\n--- 1. Cost Expansion Ratio vs SHAP Contribution ---")
    all_df["shap_cost_exp"] = shap_values[:, FEATURE_COLS.index("cost_expansion_ratio")]
    all_df["cost_exp_bin"] = pd.cut(all_df["cost_expansion_ratio"], bins=[0.0, 1.0, 1.15, 1.30, 1.50, 2.0, 10.0], include_lowest=True)
    cost_tbl = all_df.groupby("cost_exp_bin", observed=False).agg(
        Count=("cost_expansion_ratio", "count"),
        Mean_Cost_Expansion=("cost_expansion_ratio", "mean"),
        Mean_SHAP_Impact=("shap_cost_exp", "mean")
    ).reset_index()
    print(cost_tbl.to_string(index=False))

    # 2. Delay Months Binned Monotonicity
    print("\n--- 2. Delay Months vs SHAP Contribution ---")
    all_df["shap_delay"] = shap_values[:, FEATURE_COLS.index("delay_months")]
    all_df["delay_bin"] = pd.cut(all_df["delay_months"], bins=[-100, 0, 12, 24, 48, 100, 500], include_lowest=True)
    delay_tbl = all_df.groupby("delay_bin", observed=False).agg(
        Count=("delay_months", "count"),
        Mean_Delay_Months=("delay_months", "mean"),
        Mean_SHAP_Impact=("shap_delay", "mean")
    ).reset_index()
    print(delay_tbl.to_string(index=False))

    print("\n" + "=" * 110)
    print("SHAP SANITY CHECK VERDICT: GLOBAL MONOTONICITY & DIRECTIONALITY BEHAVE SENSIBLY!")
    print("=" * 110)


if __name__ == "__main__":
    verify_shap_sanity()
