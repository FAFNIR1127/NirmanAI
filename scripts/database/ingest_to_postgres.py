import os
import sqlite3
from dotenv import load_dotenv
from pathlib import Path
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

load_dotenv()

# ============================================================
# PATHS
# ============================================================

LONGITUDINAL_PARQUET = Path("processed/normalized/longitudinal_projects.parquet")
FEATURES_PARQUET = Path("processed/features/ml_features.parquet")
SCHEMA_SQL = Path("database/schema.sql")
SQLITE_DB = Path("database/nirman.db")

DB_USER = os.getenv("DB_USER", os.getenv("USER", "postgres"))
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "nirman_db")


# ============================================================
# GET DATABASE ENGINE
# ============================================================

def get_db_engine():
    candidate_urls = []
    if os.getenv("DB_PASSWORD"):
        candidate_urls.append(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    else:
        candidate_urls.append(f"postgresql://postgres:hulk@{DB_HOST}:{DB_PORT}/{DB_NAME}")
        candidate_urls.append(f"postgresql://{os.getenv('USER', 'sanket')}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
        candidate_urls.append(f"postgresql://postgres@{DB_HOST}:{DB_PORT}/{DB_NAME}")

    for url in candidate_urls:
        try:
            engine = create_engine(url, connect_args={"connect_timeout": 2})
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"Connected to PostgreSQL database '{DB_NAME}' using {url}")
            return engine, "postgresql"
        except Exception:
            continue

    print(f"Could not connect to PostgreSQL. Using local relational database at {SQLITE_DB}")
    SQLITE_DB.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{SQLITE_DB}")
    return engine, "sqlite"


# ============================================================
# INGESTION PIPELINE
# ============================================================

KNOWN_NAME_FALLBACKS = {
    "N06000294": "SAONER-III EXPN UG MINE 1.54",
    "N18000419": "Transmission System Strengthening at Davanagere for Integration of RE",
    "N18000422": "Eastern Region Expansion Scheme-44 [ERES-44]",
    "N24002237": "Construction of 2 lane Barpeta Bypass on NH-427",
}


def run_ingestion():
    if not LONGITUDINAL_PARQUET.exists() or not FEATURES_PARQUET.exists():
        raise FileNotFoundError("Input parquet files not found.")

    engine, db_type = get_db_engine()

    df_long = pd.read_parquet(LONGITUDINAL_PARQUET)
    df_feat = pd.read_parquet(FEATURES_PARQUET)

    def first_non_null(s):
        valid = s.dropna()
        valid = valid[valid.astype(str).str.strip() != ""]
        valid = valid[valid.astype(str).str.strip() != "None"]
        return valid.iloc[0] if not valid.empty else None

    # Group by project_code
    project_rows = []
    for code, group in df_long.groupby("project_code"):
        p_name = first_non_null(group["project_name"])
        if not p_name:
            p_name = KNOWN_NAME_FALLBACKS.get(code, f"Infrastructure Project {code}")

        p_agency = first_non_null(group["agency"])
        p_state = first_non_null(group["state"])
        p_approval = first_non_null(group["approval_date"])
        p_cost = first_non_null(group["original_cost"])

        project_rows.append({
            "project_code": code,
            "project_name": p_name,
            "agency": p_agency,
            "state": p_state,
            "approval_date": p_approval,
            "original_cost": p_cost,
        })

    df_projects = pd.DataFrame(project_rows)

    # 2. Observations Table
    df_obs = df_long[[
        "project_code", "reporting_month", "revised_cost", "anticipated_cost",
        "cumulative_expenditure", "physical_progress", "original_doc", "revised_doc",
        "anticipated_doc", "original_delay_months", "revised_delay_months",
        "milestones_achieved", "milestones_total", "source_file"
    ]].copy()

    # 3. Features Table
    df_features = df_feat[[
        "project_code", "reporting_month", "months_elapsed", "months_originally_planned",
        "months_remaining", "cost_expansion_ratio", "expenditure_ratio",
        "expenditure_progress_gap", "schedule_slippage_ratio", "progress_velocity",
        "target_cost_overrun_12m", "target_time_overrun_12m", "target_severe_risk_12m"
    ]].copy()

    # Write tables to database
    with engine.begin() as conn:
        if db_type == "postgresql":
            conn.execute(text("DROP TABLE IF EXISTS risk_scores CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS project_features CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS project_observations CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS projects CASCADE;"))

            if SCHEMA_SQL.exists():
                with SCHEMA_SQL.open("r", encoding="utf-8") as f:
                    conn.execute(text(f.read()))

            df_projects.to_sql("projects", con=conn, if_exists="append", index=False)
            df_obs.to_sql("project_observations", con=conn, if_exists="append", index=False)
            df_features.to_sql("project_features", con=conn, if_exists="append", index=False)
        else:
            df_projects.to_sql("projects", con=conn, if_exists="replace", index=False)
            df_obs.to_sql("project_observations", con=conn, if_exists="replace", index=False)
            df_features.to_sql("project_features", con=conn, if_exists="replace", index=False)

    print("=" * 100)
    print("DATABASE INGESTION COMPLETED SUCCESSFULLY")
    print("=" * 100)
    print(f"Target Database Engine     : {db_type.upper()}")
    print(f"Master Projects Loaded     : {len(df_projects):,} rows")
    print(f"Observations Loaded        : {len(df_obs):,} rows")
    print(f"Features Loaded            : {len(df_features):,} rows")

    # Sanity verification
    conn_raw = sqlite3.connect(SQLITE_DB) if db_type == "sqlite" else engine.connect()
    try:
        missing_count = pd.read_sql_query(
            "SELECT COUNT(*) AS cnt FROM projects WHERE project_name IS NULL OR TRIM(project_name) = ''",
            conn_raw
        )["cnt"].iloc[0]
        print(f"Validation: Missing project names in master table = {missing_count}")
    finally:
        if db_type == "sqlite":
            conn_raw.close()
        else:
            conn_raw.close()

    return engine


if __name__ == "__main__":
    run_ingestion()
