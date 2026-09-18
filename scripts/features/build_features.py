from pathlib import Path
import pandas as pd
import numpy as np


# ============================================================
# PATHS
# ============================================================

INPUT_PARQUET = Path("processed/normalized/longitudinal_projects.parquet")
OUTPUT_PARQUET = Path("processed/features/ml_features.parquet")
OUTPUT_TRAIN = Path("processed/features/train_dataset.parquet")
OUTPUT_VAL = Path("processed/features/val_dataset.parquet")
OUTPUT_LIVE = Path("processed/features/live_dataset.parquet")


# ============================================================
# FEATURE ENGINEERING & TARGET LABEL GENERATION
# ============================================================

def build_features():
    if not INPUT_PARQUET.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_PARQUET}")

    df = pd.read_parquet(INPUT_PARQUET)

    # Convert reporting_month to datetime
    df["dt_reporting"] = pd.to_datetime(df["reporting_month"] + "-01")
    df["dt_approval"] = pd.to_datetime(df["approval_date"] + "-01", errors="coerce")
    df["dt_orig_doc"] = pd.to_datetime(df["original_doc"] + "-01", errors="coerce")
    df["dt_ant_doc"] = pd.to_datetime(df["anticipated_doc"] + "-01", errors="coerce")

    # 1. Temporal & Duration Metrics
    df["months_elapsed"] = (df["dt_reporting"] - df["dt_approval"]).dt.days / 30.4375
    df["months_elapsed"] = df["months_elapsed"].apply(lambda v: max(0.0, v) if pd.notna(v) else np.nan)

    df["months_originally_planned"] = (df["dt_orig_doc"] - df["dt_approval"]).dt.days / 30.4375
    df["months_originally_planned"] = df["months_originally_planned"].apply(lambda v: v if (pd.notna(v) and v > 0) else np.nan)

    df["months_remaining"] = (df["dt_ant_doc"] - df["dt_reporting"]).dt.days / 30.4375

    # 2. Cost Ratios
    df["cost_expansion_ratio"] = np.where(
        (df["original_cost"].notna()) & (df["original_cost"] > 0) & (df["anticipated_cost"].notna()),
        df["anticipated_cost"] / df["original_cost"],
        np.nan
    )

    df["expenditure_ratio"] = np.where(
        (df["anticipated_cost"].notna()) & (df["anticipated_cost"] > 0) & (df["cumulative_expenditure"].notna()),
        df["cumulative_expenditure"] / df["anticipated_cost"],
        np.nan
    )

    # 3. Expenditure - Progress Gap
    # (expenditure_ratio) - (physical_progress / 100)
    df["expenditure_progress_gap"] = np.where(
        (df["expenditure_ratio"].notna()) & (df["physical_progress"].notna()),
        df["expenditure_ratio"] - (df["physical_progress"] / 100.0),
        np.nan
    )

    # 4. Schedule Slippage
    df["delay_months"] = np.where(
        (df["dt_ant_doc"].notna()) & (df["dt_orig_doc"].notna()),
        (df["dt_ant_doc"] - df["dt_orig_doc"]).dt.days / 30.4375,
        df["revised_delay_months"]
    )

    df["schedule_slippage_ratio"] = np.where(
        (df["delay_months"].notna()) & (df["months_originally_planned"].notna()) & (df["months_originally_planned"] > 0),
        df["delay_months"] / df["months_originally_planned"],
        np.nan
    )

    # 5. Milestone Completion Rate
    df["milestone_rate"] = np.where(
        (df["milestones_total"].notna()) & (df["milestones_total"] > 0) & (df["milestones_achieved"].notna()),
        df["milestones_achieved"] / df["milestones_total"],
        np.nan
    )

    # Sort longitudinal panel
    df = df.sort_values(by=["project_code", "dt_reporting"]).reset_index(drop=True)

    # 6. Progress Velocity (Physical progress delta over months between observations)
    df["prev_progress"] = df.groupby("project_code")["physical_progress"].shift(1)
    df["prev_dt"] = df.groupby("project_code")["dt_reporting"].shift(1)

    months_between = (df["dt_reporting"] - df["prev_dt"]).dt.days / 30.4375
    df["progress_velocity"] = np.where(
        (df["physical_progress"].notna()) & (df["prev_progress"].notna()) & (months_between > 0),
        (df["physical_progress"] - df["prev_progress"]) / months_between,
        np.nan
    )

    # 7. Construct Future Target Labels (T+12 Months Forward Window without Target Leakage)
    df_future = df[["project_code", "dt_reporting", "cost_expansion_ratio", "delay_months"]].copy()
    df_future.rename(columns={
        "dt_reporting": "future_dt",
        "cost_expansion_ratio": "future_cost_expansion",
        "delay_months": "future_delay_months"
    }, inplace=True)

    df_merged = pd.merge(df, df_future, on="project_code", how="left")
    days_diff = (df_merged["future_dt"] - df_merged["dt_reporting"]).dt.days
    valid_window = (days_diff >= 280) & (days_diff <= 420)
    df_future_matches = df_merged[valid_window].copy()

    # Pick first matching future observation per row
    df_future_matches = df_future_matches.groupby(["project_code", "dt_reporting"]).first().reset_index()

    df = pd.merge(
        df,
        df_future_matches[["project_code", "dt_reporting", "future_cost_expansion", "future_delay_months"]],
        on=["project_code", "dt_reporting"],
        how="left"
    )

    df["target_cost_overrun_12m"] = np.where(
        df["future_cost_expansion"].notna(),
        np.where(df["future_cost_expansion"] > 1.15, 1, 0),
        np.nan
    )

    df["target_time_overrun_12m"] = np.where(
        df["future_delay_months"].notna(),
        np.where(df["future_delay_months"] > 6.0, 1, 0),
        np.nan
    )

    df["target_severe_risk_12m"] = np.where(
        (df["future_cost_expansion"].notna()) | (df["future_delay_months"].notna()),
        np.where((df["future_cost_expansion"] > 1.25) | (df["future_delay_months"] > 12.0), 1, 0),
        np.nan
    )

    # Drop temporary columns
    df.drop(columns=["prev_progress", "prev_dt"], inplace=True)

    # Save full features dataset
    OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PARQUET, index=False)

    # 8. Create Time-Based Rolling ML Datasets
    # Train: 2018-04 to 2023-04 (Historical observations with labels)
    # Val:   2024-04 to 2025-04 (Validation observations)
    # Live:  2025-07 to 2026-07 (Most recent ongoing observations for live inference)

    train_df = df[df["reporting_month"] <= "2023-04"].reset_index(drop=True)
    val_df = df[(df["reporting_month"] >= "2024-04") & (df["reporting_month"] <= "2025-04")].reset_index(drop=True)
    live_df = df[df["reporting_month"] >= "2025-07"].reset_index(drop=True)

    train_df.to_parquet(OUTPUT_TRAIN, index=False)
    val_df.to_parquet(OUTPUT_VAL, index=False)
    live_df.to_parquet(OUTPUT_LIVE, index=False)

    print("=" * 100)
    print("FEATURE ENGINEERING & ML DATASETS CREATED SUCCESSFULLY")
    print("=" * 100)
    print(f"Total Features Dataset Rows  : {len(df):,}")
    print(f"Train Dataset (2018-2023)    : {len(train_df):,} rows")
    print(f"Validation Dataset (2024-25) : {len(val_df):,} rows")
    print(f"Live Prediction Dataset      : {len(live_df):,} rows")
    print(f"Saved Features Parquet       : {OUTPUT_PARQUET}")
    print(f"Saved Train Parquet          : {OUTPUT_TRAIN}")
    print(f"Saved Validation Parquet     : {OUTPUT_VAL}")
    print(f"Saved Live Parquet           : {OUTPUT_LIVE}")

    return df


if __name__ == "__main__":
    build_features()
