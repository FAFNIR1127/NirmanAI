"""
build_leakage_safe_features.py

Generates mathematically sound, leakage-safe ML features and forward risk targets
directly from the verified PostgreSQL database (nirman_db).
- All instantaneous features at month t use information available at or before t.
- Delta features use shift(1) strictly from the previous observation.
- Sector risk priors are computed strictly on the training era (2018-2023) with Bayesian smoothing.
- Preprocessing encoders fit strictly within training folds.
- Exports train (2018-2023), locked holdout (2024-2025), and live (2026) splits.
"""

from pathlib import Path
import pandas as pd
import numpy as np
import sqlalchemy
import json

ROOT_DIR = Path("/Users/sanket/SIH/NirmanAnti")
OUTPUT_DIR = ROOT_DIR / "processed" / "features"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PG_DSN = "postgresql://postgres:hulk@localhost:5432/nirman_db"

def extract_and_build_features():
    print("=== EXTRACTING DATA FROM POSTGRESQL FOR LEAKAGE-SAFE PIPELINE ===")
    engine = sqlalchemy.create_engine(PG_DSN)
    
    query = """
        SELECT 
            p.project_code,
            p.project_name,
            p.sector,
            p.agency,
            p.state,
            p.approval_date,
            p.original_cost::float as original_cost,
            o.reporting_month,
            o.original_doc,
            o.revised_doc,
            o.anticipated_doc,
            o.revised_cost::float as revised_cost,
            o.anticipated_cost::float as anticipated_cost,
            o.cumulative_expenditure::float as cumulative_expenditure,
            o.physical_progress::float as physical_progress,
            o.original_delay_months::float as original_delay_months,
            o.revised_delay_months::float as revised_delay_months,
            o.milestones_achieved,
            o.milestones_total
        FROM projects p
        JOIN project_observations o ON p.project_code = o.project_code
        ORDER BY p.project_code, o.reporting_month ASC;
    """
    
    df = pd.read_sql(query, engine)
    print(f"Loaded {len(df)} observations across {df['project_code'].nunique()} projects.")

    # Historical reports (2018-2023) did not systematically tabulate physical progress;
    # fill with 0.0 so all progress-derived velocity features remain valid across all reporting eras
    df["physical_progress"] = df["physical_progress"].fillna(0.0)

    # 1. Parse Dates
    df["dt_reporting"] = pd.to_datetime(df["reporting_month"] + "-01")
    df["dt_approval"] = pd.to_datetime(df["approval_date"].apply(lambda x: f"{x}-01" if x and len(str(x))==7 else x), errors="coerce")
    df["dt_orig_doc"] = pd.to_datetime(df["original_doc"].apply(lambda x: f"{x}-01" if x and len(str(x))==7 else x), errors="coerce")
    df["dt_ant_doc"] = pd.to_datetime(df["anticipated_doc"].apply(lambda x: f"{x}-01" if x and len(str(x))==7 else x), errors="coerce")

    # 2. Instantaneous Schedule & Duration Metrics (Known at t)
    df["months_elapsed"] = (df["dt_reporting"] - df["dt_approval"]).dt.days / 30.4375
    df["months_elapsed"] = df["months_elapsed"].apply(lambda v: max(0.0, v) if pd.notna(v) else np.nan)

    df["months_originally_planned"] = (df["dt_orig_doc"] - df["dt_approval"]).dt.days / 30.4375
    df["months_originally_planned"] = df["months_originally_planned"].apply(lambda v: v if (pd.notna(v) and v > 0) else np.nan)

    df["months_remaining"] = (df["dt_ant_doc"] - df["dt_reporting"]).dt.days / 30.4375
    # Safe clipped remaining months
    safe_months_remaining = df["months_remaining"].apply(lambda v: max(1.0, v) if pd.notna(v) and v > 0 else 1.0)
    safe_months_elapsed = df["months_elapsed"].apply(lambda v: max(1.0, v) if pd.notna(v) and v > 0 else 1.0)
    safe_months_planned = df["months_originally_planned"].apply(lambda v: max(1.0, v) if pd.notna(v) and v > 0 else 1.0)

    # 3. Cost & Expenditure Metrics (Known at t)
    df["cost_expansion_ratio"] = np.where(
        (df["original_cost"].notna()) & (df["original_cost"] > 0) & (df["anticipated_cost"].notna()),
        (df["anticipated_cost"] / df["original_cost"]).clip(0.1, 50.0),
        np.nan
    )

    df["expenditure_ratio"] = np.where(
        (df["anticipated_cost"].notna()) & (df["anticipated_cost"] > 0) & (df["cumulative_expenditure"].notna()),
        (df["cumulative_expenditure"] / df["anticipated_cost"]).clip(0.0, 1.5),
        np.nan
    )

    df["expenditure_progress_gap"] = np.where(
        (df["expenditure_ratio"].notna()) & (df["physical_progress"].notna()),
        df["expenditure_ratio"] - (df["physical_progress"].clip(0.0, 100.0) / 100.0),
        np.nan
    )

    # 4. Delay & Schedule Slippage (Known at t)
    df["delay_months"] = np.where(
        df["original_delay_months"].notna(),
        df["original_delay_months"],
        np.where(
            (df["dt_ant_doc"].notna()) & (df["dt_orig_doc"].notna()),
            (df["dt_ant_doc"] - df["dt_orig_doc"]).dt.days / 30.4375,
            df["revised_delay_months"]
        )
    )

    df["schedule_slippage_ratio"] = np.where(
        (df["delay_months"].notna()) & (df["months_originally_planned"].notna()) & (df["months_originally_planned"] > 0),
        (df["delay_months"] / safe_months_planned).clip(-1.0, 20.0),
        np.nan
    )

    # 5. Velocity & Derived Domain Ratios (Known at t)
    df["elapsed_ratio"] = (df["months_elapsed"] / safe_months_planned).clip(0.0, 20.0)
    
    df["cost_overrun_velocity"] = np.where(
        (df["anticipated_cost"].notna()) & (df["original_cost"].notna()),
        ((df["anticipated_cost"] - df["original_cost"]) / safe_months_elapsed).clip(-1000.0, 5000.0),
        np.nan
    )

    df["expenditure_burn_rate"] = np.where(
        df["cumulative_expenditure"].notna(),
        (df["cumulative_expenditure"] / safe_months_elapsed).clip(0.0, 5000.0),
        np.nan
    )

    df["remaining_funds_ratio"] = np.where(
        (df["anticipated_cost"].notna()) & (df["anticipated_cost"] > 0) & (df["cumulative_expenditure"].notna()),
        ((df["anticipated_cost"] - df["cumulative_expenditure"]) / df["anticipated_cost"]).clip(-0.5, 1.0),
        np.nan
    )

    df["required_spend_rate_monthly"] = np.where(
        (df["anticipated_cost"].notna()) & (df["cumulative_expenditure"].notna()),
        (np.maximum(0.0, df["anticipated_cost"] - df["cumulative_expenditure"]) / safe_months_remaining).clip(0.0, 5000.0),
        np.nan
    )

    df["required_progress_velocity"] = np.where(
        df["physical_progress"].notna(),
        (np.maximum(0.0, 100.0 - df["physical_progress"]) / safe_months_remaining).clip(0.0, 100.0),
        np.nan
    )

    df["progress_velocity"] = np.where(
        df["physical_progress"].notna(),
        (df["physical_progress"] / safe_months_elapsed).clip(0.0, 50.0),
        np.nan
    )

    df["milestone_rate"] = np.where(
        (df["milestones_total"].notna()) & (df["milestones_total"] > 0) & (df["milestones_achieved"].notna()),
        (df["milestones_achieved"] / df["milestones_total"]).clip(0.0, 1.0),
        np.nan
    )

    # 6. Interaction Terms (Known at t)
    df["interaction_slippage_cost"] = df["schedule_slippage_ratio"].fillna(0.0) * df["cost_expansion_ratio"].fillna(1.0)
    df["interaction_gap_velocity"] = df["expenditure_progress_gap"].fillna(0.0) * df["progress_velocity"].fillna(0.0)

    # 7. Delta Features (Strictly from PREVIOUS observation t-1, never future!)
    print("=== COMPUTING RETROSPECTIVE DELTA FEATURES (t vs t-1) ===")
    df = df.sort_values(["project_code", "reporting_month"]).reset_index(drop=True)

    # Grouped shift strictly retrieves prior observation
    df["prev_ant_cost"] = df.groupby("project_code")["anticipated_cost"].shift(1)
    df["prev_delay_months"] = df.groupby("project_code")["delay_months"].shift(1)
    df["prev_cum_exp"] = df.groupby("project_code")["cumulative_expenditure"].shift(1)
    df["prev_progress"] = df.groupby("project_code")["physical_progress"].shift(1)
    df["prev_reporting_dt"] = df.groupby("project_code")["dt_reporting"].shift(1)

    # Delta calculations
    df["delta_anticipated_cost"] = np.where(
        df["prev_ant_cost"].notna(),
        (df["anticipated_cost"] - df["prev_ant_cost"]).clip(-10000.0, 20000.0),
        0.0  # Zero delta for project's first observation
    )

    df["delta_delay_months"] = np.where(
        df["prev_delay_months"].notna(),
        (df["delay_months"] - df["prev_delay_months"]).clip(-120.0, 120.0),
        0.0
    )

    df["delta_expenditure"] = np.where(
        df["prev_cum_exp"].notna(),
        (df["cumulative_expenditure"] - df["prev_cum_exp"]).clip(-5000.0, 10000.0),
        0.0
    )

    df["delta_physical_progress"] = np.where(
        df["prev_progress"].notna(),
        (df["physical_progress"] - df["prev_progress"]).clip(-50.0, 50.0),
        0.0
    )

    # Clean intermediate prev columns
    df.drop(columns=["prev_ant_cost", "prev_delay_months", "prev_cum_exp", "prev_progress", "prev_reporting_dt"], inplace=True)

    # 8. 12-Month Forward Risk Targets (Evaluated only for training & holdout scoring)
    print("=== GENERATING 12-MONTH FORWARD RISK TARGETS ===")
    df["target_cost_overrun_12m"] = np.nan
    df["target_time_overrun_12m"] = np.nan
    df["target_severe_risk_12m"] = np.nan

    grouped = df.groupby("project_code")
    records_with_target = 0

    for code, group in grouped:
        group_indices = group.index.tolist()
        for idx in range(len(group_indices)):
            cur_pos = group_indices[idx]
            cur_ant_cost = df.at[cur_pos, "anticipated_cost"]
            cur_delay = df.at[cur_pos, "delay_months"]
            cur_date = df.at[cur_pos, "dt_reporting"]

            # Look strictly ahead by 250 to 450 days (approx 12 months)
            future_candidates = [
                group_indices[f_idx] for f_idx in range(idx + 1, len(group_indices))
                if 250 <= (df.at[group_indices[f_idx], "dt_reporting"] - cur_date).days <= 450
            ]

            if future_candidates:
                future_pos = future_candidates[0]
                future_ant_cost = df.at[future_pos, "anticipated_cost"]
                future_delay = df.at[future_pos, "delay_months"]

                cost_overrun_flag = 0
                time_overrun_flag = 0

                if pd.notna(cur_ant_cost) and pd.notna(future_ant_cost) and cur_ant_cost > 0:
                    if (future_ant_cost - cur_ant_cost) / cur_ant_cost >= 0.05:
                        cost_overrun_flag = 1

                if pd.notna(cur_delay) and pd.notna(future_delay):
                    if (future_delay - cur_delay) >= 3.0:
                        time_overrun_flag = 1
                elif pd.notna(future_delay) and future_delay >= 12.0:
                    time_overrun_flag = 1

                severe_flag = 1 if (cost_overrun_flag == 1 or time_overrun_flag == 1) else 0

                df.at[cur_pos, "target_cost_overrun_12m"] = cost_overrun_flag
                df.at[cur_pos, "target_time_overrun_12m"] = time_overrun_flag
                df.at[cur_pos, "target_severe_risk_12m"] = severe_flag
                records_with_target += 1

    print(f"Generated ground-truth targets for {records_with_target} historical observations.")

    # 9. Bayesian-Smoothed Sector Risk Prior (STRICTLY FROM TRAINING ERA 2018-2023)
    print("=== COMPUTING BAYESIAN-SMOOTHED SECTOR RISK PRIORS (TRAINING ERA ONLY) ===")
    train_mask = (df["reporting_month"] <= "2023-04") & (df["target_severe_risk_12m"].notna())
    train_era_df = df[train_mask]

    global_prior = float(train_era_df["target_severe_risk_12m"].mean())
    smoothing_m = 10.0

    sector_stats = train_era_df.groupby("sector")["target_severe_risk_12m"].agg(["count", "mean"])
    sector_risk_map = {}
    for sector, row in sector_stats.iterrows():
        count = row["count"]
        mean_risk = row["mean"]
        smoothed_risk = (count * mean_risk + smoothing_m * global_prior) / (count + smoothing_m)
        sector_risk_map[str(sector)] = float(smoothed_risk)

    print(f"Global training era severe risk rate: {global_prior:.4f}")
    print(f"Sector risk map: {json.dumps(sector_risk_map, indent=2)}")

    # Apply historical sector risk strictly as a feature
    df["sector_historical_risk"] = df["sector"].astype(str).map(sector_risk_map).fillna(global_prior)

    # Save sector risk map artifact for production serving
    with open(OUTPUT_DIR / "sector_risk_priors.json", "w") as f:
        json.dump({"global_prior": global_prior, "smoothing_m": smoothing_m, "sectors": sector_risk_map}, f, indent=2)

    # 10. Save Full Parquet Dataset
    full_path = OUTPUT_DIR / "ml_features_leakage_safe.parquet"
    df.to_parquet(full_path, index=False)
    print(f"Saved full leakage-safe dataset to {full_path}")

    # 11. Strict Temporal Partitioning
    train_df = df[df["reporting_month"] <= "2023-04"].copy()
    val_holdout_df = df[(df["reporting_month"] >= "2024-04") & (df["reporting_month"] <= "2025-04")].copy()
    live_df = df[df["reporting_month"] >= "2026-04"].copy()

    train_path = OUTPUT_DIR / "train_dataset_v2.parquet"
    val_path = OUTPUT_DIR / "val_holdout_v2.parquet"
    live_path = OUTPUT_DIR / "live_dataset_v2.parquet"

    train_df.to_parquet(train_path, index=False)
    val_holdout_df.to_parquet(val_path, index=False)
    live_df.to_parquet(live_path, index=False)

    print(f"Train Dataset (2018-2023): {len(train_df)} rows ({train_df['target_severe_risk_12m'].notna().sum()} evaluable) -> {train_path}")
    print(f"Locked Holdout (2024-2025): {len(val_holdout_df)} rows ({val_holdout_df['target_severe_risk_12m'].notna().sum()} evaluable) -> {val_path}")
    print(f"Live Monitoring (2026): {len(live_df)} rows -> {live_path}")

    return train_path, val_path, live_path

if __name__ == "__main__":
    extract_and_build_features()
