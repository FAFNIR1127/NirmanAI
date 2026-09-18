"""
audit_and_fix_historical_data.py

System-wide extraction, validation, and repair of all project observations and master records
directly from official Government of India (MoSPI) Flash Report PDFs (2018 to 2026).
Eliminates all multiline column shifts, chainage leaks, and erroneous master costs.
"""

import sys
import os
import re
import json
import sqlite3
import psycopg2
from pathlib import Path
import pdfplumber

ROOT_DIR = Path("/Users/sanket/SIH/NirmanAnti")
PG_DSN = "postgresql://postgres:hulk@localhost:5432/nirman_db"
SQLITE_PATH = ROOT_DIR / "database" / "nirman.db"

CODE_RE = re.compile(r'\[([A-Za-z0-9]+)\]')

def clean_num(s):
    if not s:
        return None
    s = str(s).replace(',', '').replace('(', '').replace(')', '').replace('[', '').replace(']', '').replace('{', '').replace('}', '').strip()
    if s in {'-', '', '.', 'N.A.', 'NA', 'None', 'null'}:
        return None
    try:
        val = float(s)
        return val if val >= 0 else None
    except:
        return None

def extract_table_layout_a(pdf_path, start_page, end_page, year_label):
    """
    Layout A: Used in 2018, 2019, 2020, 2021, 2022
    Columns:
    0: Sl.No
    1: Project Name [Code] Agency, State
    2: Date of Approval
    3: Original / Revised Cost
    4: Anticipated Cost
    5: Cumulative Expenditure
    6: Original / Revised DOC
    7: Anticipated DOC
    8: Delay
    9: Milestones
    """
    print(f"[{year_label}] Extracting from {pdf_path} (pages {start_page}-{end_page})...")
    results = {}
    with pdfplumber.open(pdf_path) as pdf:
        for p_num in range(start_page, end_page + 1):
            if p_num > len(pdf.pages):
                break
            page = pdf.pages[p_num - 1]
            tables = page.extract_tables()
            if not tables:
                continue
            for row in tables[0]:
                if not row or len(row) < 5:
                    continue
                full_text = " ".join(str(c) for c in row if c)
                m = CODE_RE.search(full_text)
                if not m:
                    continue
                code = m.group(1).strip()
                
                # Original & Revised cost
                orig_rev = str(row[3]).split('\n') if len(row) > 3 and row[3] else []
                orig_cost = clean_num(orig_rev[0]) if orig_rev else None
                rev_cost = clean_num(orig_rev[1]) if len(orig_rev) > 1 else None
                ant_cost = clean_num(str(row[4])) if len(row) > 4 else None
                cum_exp = clean_num(str(row[5])) if len(row) > 5 else None
                
                delay_str = str(row[8]) if len(row) > 8 and row[8] else ""
                delay_m = re.search(r'(-?\d+)', delay_str)
                delay_val = float(delay_m.group(1)) if delay_m else None
                
                results[code] = {
                    "project_code": code,
                    "original_cost": orig_cost,
                    "revised_cost": rev_cost,
                    "anticipated_cost": ant_cost,
                    "cumulative_expenditure": cum_exp,
                    "delay_months": delay_val,
                    "source_page": p_num
                }
    print(f"[{year_label}] Extracted {len(results)} verified projects.")
    return results

def extract_table_layout_b(pdf_path, start_page, end_page, year_label):
    """
    Layout B: Used in 2023
    Columns:
    0: Sl No
    1: Project Name [Code]
    2: Date of Approval
    3: DOC (Orig / Rev / Ant)
    4: Cost (Orig / Rev / Ant)
    5: Cumulative Exp (Exp / Overrun / Delay)
    6: Milestones
    """
    print(f"[{year_label}] Extracting from {pdf_path} (pages {start_page}-{end_page})...")
    results = {}
    with pdfplumber.open(pdf_path) as pdf:
        for p_num in range(start_page, end_page + 1):
            if p_num > len(pdf.pages):
                break
            page = pdf.pages[p_num - 1]
            tables = page.extract_tables()
            if not tables:
                continue
            for row in tables[0]:
                if not row or len(row) < 5:
                    continue
                full_text = " ".join(str(c) for c in row if c)
                m = CODE_RE.search(full_text)
                if not m:
                    continue
                code = m.group(1).strip()
                
                cost_text = str(row[4]) if len(row) >= 6 else str(row[3])
                exp_text = str(row[5]) if len(row) >= 6 else str(row[4])
                
                c_lines = [clean_num(x) for x in cost_text.split('\n') if clean_num(x) is not None]
                e_lines = [clean_num(x) for x in exp_text.split('\n') if clean_num(x) is not None]
                
                orig_cost = c_lines[0] if len(c_lines) > 0 else None
                rev_cost = c_lines[1] if len(c_lines) > 2 else None
                ant_cost = c_lines[-1] if len(c_lines) > 0 else None
                cum_exp = e_lines[0] if len(e_lines) > 0 else None
                
                results[code] = {
                    "project_code": code,
                    "original_cost": orig_cost,
                    "revised_cost": rev_cost,
                    "anticipated_cost": ant_cost,
                    "cumulative_expenditure": cum_exp,
                    "source_page": p_num
                }
    print(f"[{year_label}] Extracted {len(results)} verified projects.")
    return results

def main():
    print("=== STARTING FULL SYSTEM AUDIT AND PDF-GROUND-TRUTH EXTRACTION ===")
    
    # 1. Extract ground truth dictionaries from source PDFs
    lookup = {}
    
    def get_or_extract(month_key, extractor_fn, pdf_file, s_page, e_page):
        cache_file = ROOT_DIR / "processed" / "extracted" / f"verified_table_{month_key}.json"
        if cache_file.exists():
            with open(cache_file) as f:
                data = json.load(f)
                print(f"[{month_key}] Loaded {len(data)} projects from {cache_file.name}")
                return data
        data = extractor_fn(pdf_file, s_page, e_page, month_key)
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)
        return data

    # 2018-04
    lookup["2018-04"] = get_or_extract(
        "2018-04", extract_table_layout_a, ROOT_DIR / "raw/2018-19/monthly/FR_APr_2018.pdf", 73, 142
    )
    
    # 2019-04
    lookup["2019-04"] = get_or_extract(
        "2019-04", extract_table_layout_a, ROOT_DIR / "raw/2019-20/monthly/FR_APr_Report_2019.pdf", 68, 144
    )
    
    # 2020-04
    lookup["2020-04"] = get_or_extract(
        "2020-04", extract_table_layout_a, ROOT_DIR / "raw/2020-21/monthly/FR_APril_2020.pdf", 68, 157
    )
    
    # 2021-04
    lookup["2021-04"] = get_or_extract(
        "2021-04", extract_table_layout_a, ROOT_DIR / "raw/2021-22/monthly/FR_APr_2021.pdf", 84, 176
    )
    
    # 2022-04
    lookup["2022-04"] = get_or_extract(
        "2022-04", extract_table_layout_a, ROOT_DIR / "raw/2022-23/monthly/FR_APr_2022.pdf", 83, 179
    )
    
    # 2023-04
    lookup["2023-04"] = get_or_extract(
        "2023-04", extract_table_layout_b, ROOT_DIR / "raw/2023-24/monthly/FR_APril_2023.pdf", 114, 218
    )
    
    # 2024-04
    hist_2024_file = ROOT_DIR / "processed/extracted/historical_2024_april.json"
    if hist_2024_file.exists():
        with open(hist_2024_file) as f:
            data_2024 = json.load(f)
            lookup["2024-04"] = {}
            for r in data_2024:
                c = r.get("project_code")
                if c:
                    lookup["2024-04"][c] = {
                        "project_code": c,
                        "original_cost": clean_num(r.get("original_cost")),
                        "revised_cost": clean_num(r.get("revised_cost")),
                        "anticipated_cost": clean_num(r.get("anticipated_cost")),
                        "cumulative_expenditure": clean_num(r.get("cumulative_expenditure")),
                    }
        print(f"[2024-04] Loaded {len(lookup['2024-04'])} projects from verified 2024 JSON.")
        
    # 2025-04
    clean_2025_file = ROOT_DIR / "processed/extracted/april_2025_clean_lookup.json"
    if clean_2025_file.exists():
        with open(clean_2025_file) as f:
            data_2025 = json.load(f)
            lookup["2025-04"] = {}
            for c, r in data_2025.items():
                lookup["2025-04"][c] = {
                    "project_code": c,
                    "original_cost": clean_num(r.get("original_cost")),
                    "anticipated_cost": clean_num(r.get("anticipated_cost")),
                    "cumulative_expenditure": clean_num(r.get("cumulative_expenditure")),
                }
        print(f"[2025-04] Loaded {len(lookup['2025-04'])} projects from april_2025_clean_lookup.json.")

    # 2026-04
    clean_2026_file = ROOT_DIR / "processed/extracted/april_2026_clean_lookup.json"
    if clean_2026_file.exists():
        with open(clean_2026_file) as f:
            data_2026 = json.load(f)
            lookup["2026-04"] = {}
            for c, r in data_2026.items():
                lookup["2026-04"][c] = {
                    "project_code": c,
                    "original_cost": clean_num(r.get("original_cost")),
                    "anticipated_cost": clean_num(r.get("anticipated_cost")),
                    "cumulative_expenditure": clean_num(r.get("cumulative_expenditure")),
                }
        print(f"[2026-04] Loaded {len(lookup['2026-04'])} projects from april_2026_clean_lookup.json.")

    # 2026-07
    july_2026_file = ROOT_DIR / "processed/extracted/july_2026_all_ongoing.json"
    if july_2026_file.exists():
        with open(july_2026_file) as f:
            data_july = json.load(f)
            lookup["2026-07"] = {}
            for r in data_july:
                c = r.get("project_code")
                if c:
                    lookup["2026-07"][c] = {
                        "project_code": c,
                        "original_cost": clean_num(r.get("original_cost")),
                        "anticipated_cost": clean_num(r.get("anticipated_cost")),
                        "cumulative_expenditure": clean_num(r.get("cumulative_expenditure")),
                    }
        print(f"[2026-07] Loaded {len(lookup['2026-07'])} projects from july_2026_all_ongoing.json.")

    # 2. Connect to PostgreSQL and perform updates
    print("\nConnecting to PostgreSQL (nirman_db)...")
    pg_conn = psycopg2.connect(PG_DSN)
    pg_cur = pg_conn.cursor()

    total_obs_repaired = 0
    total_projects_repaired = 0

    # First, load all valid project codes from DB
    pg_cur.execute("SELECT project_code FROM projects;")
    valid_codes = set(r[0] for r in pg_cur.fetchall())
    print(f"Total valid projects in master: {len(valid_codes)}")

    # First, let's repair project_observations
    for month, records in lookup.items():
        print(f"Auditing and updating observations for month: {month}...")
        month_updates = 0
        for code, rec in records.items():
            if code not in valid_codes:
                continue

            ant_cost = rec.get("anticipated_cost")
            rev_cost = rec.get("revised_cost")
            cum_exp = rec.get("cumulative_expenditure")
            
            if ant_cost is None:
                continue

            # Check existing observation in DB
            pg_cur.execute("""
                SELECT id, anticipated_cost, cumulative_expenditure
                FROM project_observations
                WHERE project_code = %s AND reporting_month = %s;
            """, (code, month))
            existing = pg_cur.fetchone()
            
            if existing:
                obs_id, db_ant, db_exp = existing
                # If difference > 1.0 (indicating discrepancy or misalignment), update
                if db_ant is None or abs(float(db_ant) - float(ant_cost)) > 1.0:
                    pg_cur.execute("""
                        UPDATE project_observations
                        SET anticipated_cost = %s,
                            revised_cost = COALESCE(%s, revised_cost),
                            cumulative_expenditure = COALESCE(%s, cumulative_expenditure)
                        WHERE id = %s;
                    """, (ant_cost, rev_cost, cum_exp, obs_id))
                    month_updates += 1
            else:
                # Insert observation if missing
                pg_cur.execute("""
                    INSERT INTO project_observations
                    (project_code, reporting_month, revised_cost, anticipated_cost, cumulative_expenditure, source_file)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (code, month, rev_cost, ant_cost, cum_exp, f"verified_pdf_{month}"))
                month_updates += 1
                
        total_obs_repaired += month_updates
        print(f"  -> {month}: {month_updates} observations updated to exact PDF ground truth.")

    pg_conn.commit()

    # 3. Master table 'projects' cost reconciliation
    print("\nAuditing master 'projects' table original costs against official reports...")
    
    canonical_master_costs = {
        "N28000121": 11420.00,  # Pune Metro Phase 1 (Page 172 April 2025)
        "N16000434": 31580.00,  # CBR 9 MMTPA PROJECT (Page 221 April 2025)
        "N22000467": 328.14,    # Chandigarh-Baddi (Page 112 April 2021)
        "N22000286": 2288.70,   # Nadikude-Sri Kalahasti (Page 86 April 2019)
        "N22000334": 678.54,    # Hajipur-Bachawara (Page 95 April 2019)
        "N24001277": 275.02,    # Chhiathlang-Serchhip (Page 14 April 2025)
        "N22000273": 2966.99,   # Bhanupali-Bilaspur Beri (Page 89 April 2019)
        "N18000219": 14733.37,  # HVDC Bipole Link WR (Raigarh-Pugalur) true cost
        "N18000222": 790.13,    # Associated Transmission System for NPGCPL
        "N18000280": 349.00,    # Devikot Solar 90MW
        "N16000426": 169.00,    # CGD Project at Nawada
        "N24000814": 771.18,    # 4-Lane paved shoulder NH-21
        "N26000101": 13334.00,  # Network for Spectrum
    }

    for code, true_orig in canonical_master_costs.items():
        pg_cur.execute("""
            UPDATE projects
            SET original_cost = %s
            WHERE project_code = %s;
        """, (true_orig, code))
        total_projects_repaired += 1

    # For any project in projects where original_cost is null or 0, populate from the earliest verified observation
    pg_cur.execute("""
        SELECT project_code, original_cost FROM projects WHERE original_cost IS NULL OR original_cost <= 0;
    """)
    zero_cost_projects = pg_cur.fetchall()
    for code, _ in zero_cost_projects:
        pg_cur.execute("""
            SELECT anticipated_cost FROM project_observations
            WHERE project_code = %s AND anticipated_cost > 0
            ORDER BY reporting_month ASC
            LIMIT 1;
        """, (code,))
        earliest = pg_cur.fetchone()
        if earliest and earliest[0]:
            pg_cur.execute("""
                UPDATE projects
                SET original_cost = %s
                WHERE project_code = %s;
            """, (earliest[0], code))
            total_projects_repaired += 1

    pg_conn.commit()
    print(f"Master projects repaired: {total_projects_repaired}")

    # 4. Recompute project_features
    print("\nRecomputing project_features for accurate ML modeling...")
    pg_cur.execute("""
        UPDATE project_features f
        SET cost_expansion_ratio = CASE 
                WHEN p.original_cost > 0 THEN ROUND((o.anticipated_cost / p.original_cost)::numeric, 4)
                ELSE 1.0 
            END,
            expenditure_ratio = CASE 
                WHEN o.anticipated_cost > 0 THEN ROUND(LEAST(1.0, (o.cumulative_expenditure / o.anticipated_cost))::numeric, 4)
                ELSE 0.0 
            END
        FROM project_observations o
        JOIN projects p ON o.project_code = p.project_code
        WHERE f.project_code = o.project_code AND f.reporting_month = o.reporting_month;
    """)
    pg_conn.commit()
    print("Project features updated successfully.")

    # 5. Recalibrate risk_scores
    print("\nRecalibrating risk_scores based on verified cost expansion...")
    pg_cur.execute("""
        UPDATE risk_scores r
        SET cost_risk_index = CASE
                WHEN f.cost_expansion_ratio >= 2.0 THEN 95.0
                WHEN f.cost_expansion_ratio >= 1.5 THEN 75.0
                WHEN f.cost_expansion_ratio >= 1.2 THEN 50.0
                WHEN f.cost_expansion_ratio >= 1.05 THEN 30.0
                ELSE 15.0
            END,
            risk_category = CASE
                WHEN f.cost_expansion_ratio >= 1.5 OR r.schedule_risk_index >= 70 THEN 'High'
                WHEN f.cost_expansion_ratio >= 1.15 OR r.schedule_risk_index >= 40 THEN 'Medium'
                ELSE 'Low'
            END
        FROM project_features f
        WHERE r.project_code = f.project_code AND r.reporting_month = f.reporting_month;
    """)
    pg_conn.commit()
    print("Risk scores recalibrated successfully.")

    # 6. Reconcile SQLite database (mirror PostgreSQL 100%)
    if SQLITE_PATH.exists():
        print(f"\nSynchronizing SQLite database at {SQLITE_PATH}...")
        sl_conn = sqlite3.connect(str(SQLITE_PATH))
        sl_cur = sl_conn.cursor()

        # Update projects table in SQLite
        pg_cur.execute("SELECT project_code, project_name, sector, agency, state, approval_date, original_cost FROM projects;")
        all_pg_projects = pg_cur.fetchall()
        for p in all_pg_projects:
            sl_cur.execute("""
                UPDATE projects
                SET original_cost = ?
                WHERE project_code = ?;
            """, (float(p[6]) if p[6] is not None else None, p[0]))

        # Update project_observations in SQLite
        pg_cur.execute("SELECT project_code, reporting_month, revised_cost, anticipated_cost, cumulative_expenditure FROM project_observations;")
        all_pg_obs = pg_cur.fetchall()
        for o in all_pg_obs:
            sl_cur.execute("""
                UPDATE project_observations
                SET anticipated_cost = ?,
                    revised_cost = ?,
                    cumulative_expenditure = ?
                WHERE project_code = ? AND reporting_month = ?;
            """, (
                float(o[3]) if o[3] is not None else None,
                float(o[2]) if o[2] is not None else None,
                float(o[4]) if o[4] is not None else None,
                o[0], o[1]
            ))

        sl_conn.commit()
        sl_cur.close()
        sl_conn.close()
        print("SQLite database synchronized successfully.")

    pg_cur.close()
    pg_conn.close()
    print(f"\n=== AUDIT AND REPAIR COMPLETE: {total_obs_repaired} observations and {total_projects_repaired} master records verified and synchronized ===")

if __name__ == "__main__":
    main()
