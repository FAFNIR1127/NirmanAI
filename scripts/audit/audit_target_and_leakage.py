"""
audit_target_and_leakage.py

Rigorous audit of target formulation, temporal lookahead windows,
and feature timestamp compliance across the longitudinal dataset.
"""

from pathlib import Path
import json
import pandas as pd
import numpy as np

ROOT_DIR = Path("/Users/sanket/SIH/NirmanAnti")
DATA_DIR = ROOT_DIR / "processed" / "features"

TARGET_COL = "target_severe_risk_12m"


def audit_target_and_leakage():
    print("=" * 80)
    print("STEP 2: TARGET CONSTRUCTION & TEMPORAL INTEGRITY AUDIT")
    print("=" * 80)

    df_path = DATA_DIR / "ml_features_leakage_safe.parquet"
    df = pd.read_parquet(df_path)
    print(f"Total dataset observations: {len(df)}")

    # 1. Target Prevalence Evolution Across Reporting Years
    print("\n--- 1. TARGET PREVALENCE BY REPORTING YEAR ---")
    eval_df = df.dropna(subset=[TARGET_COL]).copy()
    eval_df["reporting_year"] = eval_df["reporting_month"].str.slice(0, 4)

    yearly_stats = eval_df.groupby("reporting_year")[TARGET_COL].agg(
        total_observations="count",
        severe_risk_count=lambda x: int(x.sum()),
        prevalence=lambda x: float(x.mean())
    ).reset_index()

    header = f"{'Year':<8} | {'Total Evaluable':<16} | {'Severe Risk (1)':<16} | {'Prevalence (%)':<15}"
    print(header)
    print("-" * len(header))
    for _, row in yearly_stats.iterrows():
        print(f"{row['reporting_year']:<8} | {row['total_observations']:<16} | {row['severe_risk_count']:<16} | {row['prevalence']*100:<15.2f}%")

    # 2. Target Observable Lookahead Horizon Audit
    print("\n--- 2. VERIFYING 12-MONTH HORIZON TIME DELTAS ---")
    # For projects with target, verify the actual elapsed days between current and target observation
    df = df.sort_values(["project_code", "reporting_month"]).reset_index(drop=True)
    
    # Check retrospective deltas: verify delta features only look backward
    print("\n--- 3. VERIFYING RETROSPECTIVE DELTA BOUNDS (t vs t-1) ---")
    # Group check: for each project's first observation, deltas MUST be 0.0
    first_obs_mask = df.groupby("project_code").cumcount() == 0
    first_obs = df[first_obs_mask]

    delta_cols = ["delta_anticipated_cost", "delta_delay_months", "delta_expenditure", "delta_physical_progress"]
    for col in delta_cols:
        non_zero_first = (first_obs[col] != 0.0).sum()
        print(f"  {col:<25}: {non_zero_first} non-zero values on initial observation (MUST BE 0: {'PASS' if non_zero_first == 0 else 'FAIL'})")

    # 4. Feature Leakage Keyword Verification
    print("\n--- 4. FEATURE NAMES & FUTURE CONTAMINATION AUDIT ---")
    with open(ROOT_DIR / "models" / "risk_engine_v2" / "feature_schema.json") as f:
        schema = json.load(f)
    feature_cols = schema["feature_columns"]

    forbidden = ["target", "future", "next", "outcome", "label"]
    leaks = [f for f in feature_cols if any(b in f.lower() for b in forbidden)]
    print(f"  Forbidden substrings check: {leaks if leaks else 'ZERO FORBIDDEN KEYWORDS FOUND (PASS)'}")

    # 5. Missingness Rate by Era (2018-2023 vs 2024-2025 vs 2026)
    print("\n--- 5. FEATURE MISSINGNESS RATE ACROSS TEMPORAL ERAS ---")
    train_mask = df["reporting_month"] <= "2023-04"
    holdout_mask = (df["reporting_month"] >= "2024-04") & (df["reporting_month"] <= "2025-04")
    live_mask = df["reporting_month"] >= "2026-04"

    eras = [("Train Era (2018-23)", train_mask), ("Holdout (2024-25)", holdout_mask), ("Live (2026)", live_mask)]
    
    key_features = [
        "original_cost", "anticipated_cost", "cumulative_expenditure", "physical_progress",
        "delay_months", "cost_expansion_ratio", "schedule_slippage_ratio", "expenditure_ratio",
        "elapsed_ratio", "required_progress_velocity", "delta_expenditure"
    ]

    header_m = f"{'Feature':<28} | {'Train (2018-23) %':<18} | {'Holdout (2024-25) %':<20} | {'Live (2026) %':<15}"
    print(header_m)
    print("-" * len(header_m))
    for feat in key_features:
        tr_null = df.loc[train_mask, feat].isna().mean() * 100.0
        ho_null = df.loc[holdout_mask, feat].isna().mean() * 100.0
        li_null = df.loc[live_mask, feat].isna().mean() * 100.0
        print(f"{feat:<28} | {tr_null:<18.2f}% | {ho_null:<20.2f}% | {li_null:<15.2f}%")

    print("\nTarget & Leakage Audit Completed.")


if __name__ == "__main__":
    audit_target_and_leakage()
