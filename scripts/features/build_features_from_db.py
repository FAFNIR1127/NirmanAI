"""
build_features_from_db.py

Generates ML features and 12-month forward risk targets directly from the verified
PostgreSQL database (nirman_db). Exports train, validation, and live splits.
"""

from pathlib import Path
import pandas as pd
import numpy as np
import psycopg2
import sqlalchemy

ROOT_DIR = Path("/Users/sanket/SIH/NirmanAnti")
OUTPUT_DIR = ROOT_DIR / "processed" / "features"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PG_DSN = "postgresql://postgres:hulk@localhost:5432/nirman_db"

def extract_and_engineer_features():
    print("=== EXTRACTING VERIFIED DATA FROM POSTGRESQL ===")
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
    
    # 1. Parse Dates
    df["dt_reporting"] = pd.to_datetime(df["reporting_month"] + "-01")
    df["dt_approval"] = pd.to_datetime(df["approval_date"].apply(lambda x: f"{x}-01" if x and len(str(x))==7 else x), errors="coerce")
    df["dt_orig_doc"] = pd.to_datetime(df["original_doc"].apply(lambda x: f"{x}-01" if x and len(str(x))==7 else x), errors="coerce")
    df["dt_ant_doc"] = pd.to_datetime(df["anticipated_doc"].apply(lambda x: f"{x}-01" if x and len(str(x))==7 else x), errors="coerce")

    # 2. Duration & Schedule Metrics
    df["months_elapsed"] = (df["dt_reporting"] - df["dt_approval"]).dt.days / 30.4375
    df["months_elapsed"] = df["months_elapsed"].apply(lambda v: max(0.0, v) if pd.notna(v) else np.nan)

    df["months_originally_planned"] = (df["dt_orig_doc"] - df["dt_approval"]).dt.days / 30.4375
    df["months_originally_planned"] = df["months_originally_planned"].apply(lambda v: v if (pd.notna(v) and v > 0) else np.nan)

    df["months_remaining"] = (df["dt_ant_doc"] - df["dt_reporting"]).dt.days / 30.4375

    # 3. Cost Metrics
    df["cost_expansion_ratio"] = np.where(
        (df["original_cost"].notna()) & (df["original_cost"] > 0) & (df["anticipated_cost"].notna()),
        df["anticipated_cost"] / df["original_cost"],
        np.nan
    )
    # Clip extreme ratio outliers for ML stability
    df["cost_expansion_ratio"] = df["cost_expansion_ratio"].clip(0.1, 50.0)

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

    # 4. Delay & Schedule Slippage
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
        (df["delay_months"] / df["months_originally_planned"]).clip(-1.0, 20.0),
        np.nan
    )

    # 5. Milestone & Velocity Metrics
    df["milestone_rate"] = np.where(
        (df["milestones_total"].notna()) & (df["milestones_total"] > 0) & (df["milestones_achieved"].notna()),
        (df["milestones_achieved"] / df["milestones_total"]).clip(0.0, 1.0),
        np.nan
    )

    df["progress_velocity"] = np.where(
        (df["physical_progress"].notna()) & (df["months_elapsed"].notna()) & (df["months_elapsed"] > 0),
        (df["physical_progress"] / df["months_elapsed"]).clip(0.0, 20.0),
        np.nan
    )

    # 6. Target Generation (12-Month Forward Lookahead)
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

            # Find observation closest to 12 months in the future
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

    # Save full features dataset
    full_path = OUTPUT_DIR / "ml_features.parquet"
    df.to_parquet(full_path, index=False)
    print(f"Saved full feature dataset to {full_path}")

    # 7. Temporal Split
    # Train: 2018-04 to 2023-04
    train_df = df[df["reporting_month"] <= "2023-04"].copy()
    # Val: 2024-04 to 2025-04
    val_df = df[(df["reporting_month"] >= "2024-04") & (df["reporting_month"] <= "2025-04")].copy()
    # Live: 2026-04 and 2026-07
    live_df = df[df["reporting_month"] >= "2026-04"].copy()

    train_path = OUTPUT_DIR / "train_dataset.parquet"
    val_path = OUTPUT_DIR / "val_dataset.parquet"
    live_path = OUTPUT_DIR / "live_dataset.parquet"

    train_df.to_parquet(train_path, index=False)
    val_df.to_parquet(val_path, index=False)
    live_df.to_parquet(live_path, index=False)

    print(f"Train dataset ({len(train_df)} rows) saved to {train_path}")
    print(f"Validation dataset ({len(val_df)} rows) saved to {val_path}")
    print(f"Live dataset ({len(live_df)} rows) saved to {live_path}")

    return train_path, val_path, live_path

if __name__ == "__main__":
    extract_and_engineer_features()
