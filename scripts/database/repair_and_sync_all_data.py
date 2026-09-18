#!/usr/bin/env python3
"""
scripts/database/repair_and_sync_all_data.py

Reconciles and repairs all project data directly against official MoSPI Flash Reports:
1. Fixes corrupted original_cost in `projects` table from verified July 2026 data.
2. Fixes 2025-04 observations from verified april_2025_clean_lookup.json (including N30000042).
3. Fixes 2026-04 highway chainages from verified april_2026_clean_lookup.json.
4. Re-computes features and risk scores for updated observations.
5. Syncs the clean data into SQLite (database/nirman.db) fallback with serialized JSON.
"""

import json
import logging
from pathlib import Path
import pandas as pd
import numpy as np
import sqlalchemy
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("repair_data")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
from backend.app.config import DATABASE_URL, FALLBACK_SQLITE_PATH
from backend.app.services.analytics_service import get_db_engine

def run_repair():
    engine = get_db_engine()
    log.info(f"Connected to database: {engine.url}")

    # Load clean lookups
    july_path = BASE_DIR / "processed" / "extracted" / "july_2026_all_ongoing.json"
    apr26_path = BASE_DIR / "processed" / "extracted" / "april_2026_clean_lookup.json"
    apr25_path = BASE_DIR / "processed" / "extracted" / "april_2025_clean_lookup.json"

    with open(july_path) as f:
        july_map = {r["project_code"]: r for r in json.load(f) if r.get("project_code")}

    with open(apr26_path) as f:
        apr26_map = json.load(f)

    with open(apr25_path) as f:
        apr25_map = json.load(f)

    genuine_mega_projects = {'N22000463', 'N22000346', '705728', '705237', 'N16000513', '220100133'}

    with engine.begin() as conn:
        # =====================================================================
        # STEP 1: Fix projects table corrupted original_cost
        # =====================================================================
        log.info("Step 1: Repairing corrupted original_cost in projects table...")
        fixed_p_count = 0

        for code, r in july_map.items():
            true_orig = r.get("original_cost_crore")
            if true_orig and float(true_orig) > 0 and code not in genuine_mega_projects:
                row = conn.execute(text("SELECT original_cost FROM projects WHERE project_code = :c"), {"c": code}).fetchone()
                if row and row[0] is not None:
                    curr = float(row[0])
                    if curr > float(true_orig) * 3 and curr > 5000:
                        log.info(f"  Fixing project {code}: {curr} -> {true_orig}")
                        conn.execute(
                            text("UPDATE projects SET original_cost = :cost WHERE project_code = :c"),
                            {"cost": float(true_orig), "c": code}
                        )
                        fixed_p_count += 1

        for code, r in apr26_map.items():
            true_orig = r.get("orig_cost")
            if true_orig and float(true_orig) > 0 and code not in genuine_mega_projects:
                row = conn.execute(text("SELECT original_cost FROM projects WHERE project_code = :c"), {"c": code}).fetchone()
                if row and row[0] is not None:
                    curr = float(row[0])
                    if curr > float(true_orig) * 3 and curr > 5000:
                        log.info(f"  Fixing project {code} from Apr26: {curr} -> {true_orig}")
                        conn.execute(
                            text("UPDATE projects SET original_cost = :cost WHERE project_code = :c"),
                            {"cost": float(true_orig), "c": code}
                        )
                        fixed_p_count += 1

        for code, r in apr25_map.items():
            true_orig = r.get("orig_cost")
            if true_orig and float(true_orig) > 0 and code not in genuine_mega_projects:
                row = conn.execute(text("SELECT original_cost FROM projects WHERE project_code = :c"), {"c": code}).fetchone()
                if row and row[0] is not None:
                    curr = float(row[0])
                    if curr > float(true_orig) * 3 and curr > 5000:
                        log.info(f"  Fixing project {code} from Apr25: {curr} -> {true_orig}")
                        conn.execute(
                            text("UPDATE projects SET original_cost = :cost WHERE project_code = :c"),
                            {"cost": float(true_orig), "c": code}
                        )
                        fixed_p_count += 1

        log.info(f"Step 1 Complete: {fixed_p_count} projects repaired in projects table.")

        # =====================================================================
        # STEP 2: Fix 2025-04 observations from verified april_2025_clean_lookup
        # =====================================================================
        log.info("Step 2: Repairing 2025-04 observations from verified April 2025 data...")
        fixed_25_count = 0
        for code, clean in apr25_map.items():
            clean_ant = clean.get("anticipated_cost")
            clean_rev = clean.get("revised_cost")
            clean_exp = clean.get("expenditure")
            clean_prog = clean.get("progress")

            obs = conn.execute(
                text("SELECT anticipated_cost FROM project_observations WHERE project_code = :c AND reporting_month = '2025-04'"),
                {"c": code}
            ).fetchone()

            if obs and obs[0] is not None:
                curr_ant = float(obs[0])
                if clean_ant and (curr_ant > float(clean_ant) * 3 and curr_ant > 10000 and code not in genuine_mega_projects):
                    conn.execute(text("""
                        UPDATE project_observations
                        SET anticipated_cost = :ant,
                            revised_cost = COALESCE(:rev, revised_cost),
                            cumulative_expenditure = COALESCE(:exp, cumulative_expenditure),
                            physical_progress = COALESCE(:prog, physical_progress)
                        WHERE project_code = :c AND reporting_month = '2025-04'
                    """), {
                        "ant": clean_ant, "rev": clean_rev, "exp": clean_exp, "prog": clean_prog, "c": code
                    })
                    fixed_25_count += 1

        log.info(f"Step 2 Complete: {fixed_25_count} observations repaired in 2025-04.")

        # =====================================================================
        # STEP 3: Fix 2026-04 observations from verified april_2026_clean_lookup
        # =====================================================================
        log.info("Step 3: Repairing 2026-04 observations from verified April 2026 data...")
        fixed_26_count = 0
        for code, clean in apr26_map.items():
            clean_ant = clean.get("anticipated_cost")
            clean_rev = clean.get("revised_cost")
            clean_exp = clean.get("expenditure")
            clean_prog = clean.get("progress")

            obs = conn.execute(
                text("SELECT anticipated_cost FROM project_observations WHERE project_code = :c AND reporting_month = '2026-04'"),
                {"c": code}
            ).fetchone()

            if obs and obs[0] is not None:
                curr_ant = float(obs[0])
                if clean_ant and (curr_ant > float(clean_ant) * 2 and curr_ant > 5000 and code not in genuine_mega_projects):
                    conn.execute(text("""
                        UPDATE project_observations
                        SET anticipated_cost = :ant,
                            revised_cost = COALESCE(:rev, revised_cost),
                            cumulative_expenditure = COALESCE(:exp, cumulative_expenditure),
                            physical_progress = COALESCE(:prog, physical_progress)
                        WHERE project_code = :c AND reporting_month = '2026-04'
                    """), {
                        "ant": clean_ant, "rev": clean_rev, "exp": clean_exp, "prog": clean_prog, "c": code
                    })
                    fixed_26_count += 1

        log.info(f"Step 3 Complete: {fixed_26_count} observations repaired in 2026-04.")

        # =====================================================================
        # STEP 4: Re-compute project_features & risk_scores for affected rows
        # =====================================================================
        log.info("Step 4: Recomputing project_features & risk_scores...")
        conn.execute(text("""
            UPDATE project_features pf
            SET cost_expansion_ratio = CASE 
                    WHEN p.original_cost > 0 THEN po.anticipated_cost / p.original_cost
                    ELSE 1.0 
                END,
                expenditure_ratio = CASE 
                    WHEN p.original_cost > 0 AND po.cumulative_expenditure IS NOT NULL THEN 
                        po.cumulative_expenditure / p.original_cost
                    ELSE 0.0 
                END,
                expenditure_progress_gap = CASE 
                    WHEN p.original_cost > 0 AND po.physical_progress IS NOT NULL AND po.cumulative_expenditure IS NOT NULL THEN 
                        ((po.cumulative_expenditure / p.original_cost) * 100.0) - po.physical_progress
                    ELSE 0.0 
                END
            FROM project_observations po
            JOIN projects p ON po.project_code = p.project_code
            WHERE pf.project_code = po.project_code 
              AND pf.reporting_month = po.reporting_month
              AND po.reporting_month IN ('2025-04', '2026-04', '2026-07')
        """))

        conn.execute(text("""
            UPDATE risk_scores rs
            SET risk_score = CASE
                    WHEN pf.cost_expansion_ratio <= 1.05 THEN 22.5
                    WHEN pf.cost_expansion_ratio <= 1.25 THEN 42.0
                    ELSE LEAST(95.0, pf.cost_expansion_ratio * 35.0)
                END,
                risk_category = CASE
                    WHEN pf.cost_expansion_ratio <= 1.05 THEN 'LOW'
                    WHEN pf.cost_expansion_ratio <= 1.25 THEN 'MODERATE'
                    WHEN pf.cost_expansion_ratio <= 1.50 THEN 'HIGH'
                    ELSE 'CRITICAL'
                END
            FROM project_features pf
            WHERE rs.project_code = pf.project_code
              AND rs.reporting_month = pf.reporting_month
              AND rs.reporting_month IN ('2025-04', '2026-04')
              AND pf.cost_expansion_ratio < 2.0
              AND rs.risk_category = 'CRITICAL'
        """))
        log.info("Step 4 Complete: Features and risk scores recalibrated.")

    # =====================================================================
    # STEP 5: Sync to SQLite (database/nirman.db) fallback
    # =====================================================================
    log.info(f"Step 5: Syncing clean tables to SQLite ({FALLBACK_SQLITE_PATH})...")
    sqlite_engine = sqlalchemy.create_engine(f"sqlite:///{FALLBACK_SQLITE_PATH}")

    tables_to_sync = ["projects", "project_observations", "project_features", "risk_scores"]
    for t in tables_to_sync:
        log.info(f"  Syncing table {t}...")
        df_pg = pd.read_sql(f"SELECT * FROM {t}", engine)
        # Ensure json/dict/list columns are converted to string for SQLite
        for col in df_pg.columns:
            if df_pg[col].dtype == 'object':
                df_pg[col] = df_pg[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)
        df_pg.to_sql(t, sqlite_engine, if_exists="replace", index=False)
        log.info(f"    Synced {len(df_pg)} rows for {t}")

    log.info("=" * 70)
    log.info("DATA AUDIT & REPAIR COMPLETE: ALL 5 STEPS SUCCEEDED!")
    log.info("=" * 70)

if __name__ == "__main__":
    run_repair()
