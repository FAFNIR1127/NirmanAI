#!/usr/bin/env python3
"""
scripts/database/deduplicate_projects.py

Deduplicates duplicate project pairs in nirman_db and nirman.db:
- Canonical project is preserved with complete longitudinal observation history.
- Observations from the secondary duplicate are merged into the canonical project.
- Redundant secondary project rows are removed from master tables.
- Alias mappings are created so searches for either code resolve to the canonical project.
- Dual database sync to PostgreSQL & SQLite.
"""

import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import sqlite3

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("dedup")

ROOT_DIR = Path("/Users/sanket/SIH/NirmanAnti")
PG_DSN = "postgresql://postgres:hulk@localhost:5432/nirman_db"
SQLITE_PATH = ROOT_DIR / "database" / "nirman.db"
ALIAS_FILE = ROOT_DIR / "processed" / "extracted" / "project_aliases.json"

def norm(s):
    if not s: return ''
    s = re.sub(r'\(.*?\)|\[.*?\]', '', s)
    s = re.sub(r'[^a-zA-Z0-9]', '', s).lower()
    return s

def run_deduplication():
    log.info("Starting project deduplication...")
    pg_conn = psycopg2.connect(PG_DSN)
    pg_cur = pg_conn.cursor(cursor_factory=RealDictCursor)

    # 1. Find all duplicate pairs
    pg_cur.execute("SELECT project_code, project_name FROM projects;")
    all_projects = pg_cur.fetchall()

    legacy = [p for p in all_projects if p["project_code"].startswith('N') or (p["project_code"].isdigit() and len(p["project_code"]) > 6)]
    numeric = [p for p in all_projects if p["project_code"].isdigit() and len(p["project_code"]) <= 6]

    legacy_dict = {}
    for l in legacy:
        nl = norm(l["project_name"])
        if nl and len(nl) >= 5:
            legacy_dict[nl] = l["project_code"]

    dups = []
    for n in numeric:
        nn = norm(n["project_name"])
        if nn in legacy_dict:
            l_code = legacy_dict[nn]
            dups.append((l_code, n["project_code"]))

    log.info(f"Identified {len(dups)} duplicate pairs to merge.")

    # 2. Create project_aliases table if not exists
    pg_cur.execute("""
        CREATE TABLE IF NOT EXISTS project_aliases (
            alias_code VARCHAR(32) PRIMARY KEY,
            canonical_code VARCHAR(32) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    aliases = {}

    for canonical_code, dup_code in dups:
        log.info(f"Merging duplicate {dup_code} -> canonical {canonical_code}...")
        aliases[dup_code] = canonical_code

        # Store in project_aliases table
        pg_cur.execute("""
            INSERT INTO project_aliases (alias_code, canonical_code)
            VALUES (%s, %s)
            ON CONFLICT (alias_code) DO UPDATE SET canonical_code = EXCLUDED.canonical_code;
        """, (dup_code, canonical_code))

        # Get observations of duplicate code
        pg_cur.execute("SELECT * FROM project_observations WHERE project_code = %s;", (dup_code,))
        dup_obs = pg_cur.fetchall()

        for d_obs in dup_obs:
            m = d_obs["reporting_month"]
            # Check if canonical already has this observation
            pg_cur.execute("""
                SELECT id FROM project_observations 
                WHERE project_code = %s AND reporting_month = %s;
            """, (canonical_code, m))
            canon_obs = pg_cur.fetchone()

            if canon_obs:
                # Update any null fields on canonical from duplicate
                pg_cur.execute("""
                    UPDATE project_observations
                    SET revised_cost = COALESCE(revised_cost, %s),
                        anticipated_cost = COALESCE(anticipated_cost, %s),
                        cumulative_expenditure = COALESCE(cumulative_expenditure, %s),
                        physical_progress = COALESCE(physical_progress, %s),
                        original_doc = COALESCE(original_doc, %s),
                        revised_doc = COALESCE(revised_doc, %s),
                        anticipated_doc = COALESCE(anticipated_doc, %s),
                        original_delay_months = COALESCE(original_delay_months, %s)
                    WHERE id = %s;
                """, (
                    d_obs["revised_cost"], d_obs["anticipated_cost"], d_obs["cumulative_expenditure"],
                    d_obs["physical_progress"], d_obs["original_doc"], d_obs["revised_doc"],
                    d_obs["anticipated_doc"], d_obs["original_delay_months"], canon_obs["id"]
                ))
            else:
                # Re-parent observation to canonical_code
                pg_cur.execute("""
                    UPDATE project_observations
                    SET project_code = %s
                    WHERE id = %s;
                """, (canonical_code, d_obs["id"]))

        # Delete remaining dependent records for dup_code
        pg_cur.execute("DELETE FROM project_risk_predictions WHERE project_code = %s;", (dup_code,))
        pg_cur.execute("DELETE FROM risk_scores WHERE project_code = %s;", (dup_code,))
        pg_cur.execute("DELETE FROM project_features WHERE project_code = %s;", (dup_code,))
        pg_cur.execute("DELETE FROM project_observations WHERE project_code = %s;", (dup_code,))
        pg_cur.execute("DELETE FROM projects WHERE project_code = %s;", (dup_code,))

    pg_conn.commit()
    log.info(f"Successfully merged {len(dups)} duplicate projects in PostgreSQL.")

    # 3. Save alias map to JSON file for backend fallback
    ALIAS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ALIAS_FILE, "w") as f:
        json.dump(aliases, f, indent=2)
    log.info(f"Saved {len(aliases)} alias pairs to {ALIAS_FILE}")

    # 4. Sync into SQLite (database/nirman.db)
    log.info("Synchronizing SQLite (database/nirman.db)...")
    sq_conn = sqlite3.connect(SQLITE_PATH)
    sq_cur = sq_conn.cursor()

    # Create project_aliases in SQLite
    sq_cur.execute("""
        CREATE TABLE IF NOT EXISTS project_aliases (
            alias_code TEXT PRIMARY KEY,
            canonical_code TEXT NOT NULL,
            created_at TEXT
        );
    """)

    tables = ["projects", "project_observations", "project_features", "risk_scores", "project_risk_predictions", "project_aliases"]
    
    for t in tables:
        pg_cur.execute(f"SELECT * FROM {t};")
        rows = pg_cur.fetchall()
        if not rows:
            continue
        
        sq_cur.execute(f"PRAGMA table_info({t});")
        sq_cols = [c[1] for c in sq_cur.fetchall()]
        
        pg_cols = list(rows[0].keys())
        cols = [c for c in pg_cols if c in sq_cols]
        
        sq_cur.execute(f"DELETE FROM {t};")
        placeholders = ", ".join(["?" for _ in cols])
        cols_str = ", ".join(cols)
        insert_sql = f"INSERT INTO {t} ({cols_str}) VALUES ({placeholders});"

        sq_batch = []
        for r in rows:
            row_vals = []
            for c in cols:
                v = r[c]
                if isinstance(v, (datetime,)):
                    row_vals.append(v.isoformat())
                elif isinstance(v, (dict, list)):
                    row_vals.append(json.dumps(v))
                elif v is not None and hasattr(v, '__float__'):
                    row_vals.append(float(v))
                else:
                    row_vals.append(v)
            sq_batch.append(row_vals)

        sq_cur.executemany(insert_sql, sq_batch)
        sq_conn.commit()
        log.info(f"  Synced {len(sq_batch)} rows into '{t}' in SQLite.")

    sq_conn.close()
    pg_conn.close()
    log.info("Deduplication complete and dual databases synchronized!")

if __name__ == "__main__":
    run_reconciliation = run_deduplication
    run_deduplication()
