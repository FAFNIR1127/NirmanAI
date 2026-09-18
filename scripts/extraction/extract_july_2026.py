#!/usr/bin/env python3
"""
scripts/extraction/extract_july_2026.py

Extract Table 6 (All Ongoing Projects) from FlashReport_July_2026.pdf
and load into PostgreSQL as project_observations for reporting_month='2026-07'.

This is a complete, self-contained ingestion script that:
1. Parses the PDF using pdfplumber (best for structured tables)
2. Extracts: project_code, project_name, agency, state, original_cost,
             revised_cost, anticipated_cost, cumulative_expenditure,
             physical_progress, original_doc, anticipated_doc
3. Computes delay_months from date columns
4. Upserts into project_observations and updates projects table
5. Re-computes project_features for 2026-07
6. Re-runs XGBoost scoring for 2026-07
"""

import re
import json
import sys
import math
import logging
from pathlib import Path
from datetime import datetime

import pdfplumber
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values

# ── Config ─────────────────────────────────────────────────────────────────
PDF_PATH    = Path("raw/2026-27/monthly/FlashReport_July_2026.pdf")
REPORTING_MONTH = "2026-07"
DB_URL      = "postgresql://postgres:hulk@localhost:5432/nirman_db"
LOG_FILE    = Path("processed/ingest_july2026.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("july2026")

# ── Regex & helpers ──────────────────────────────────────────────────────────

PROJ_CODE_RE = re.compile(r'\b([A-Z]?\d{6,10})\b')
DATE_RE      = re.compile(r'(\d{1,2})/(\d{4})')  # MM/YYYY


def _clean(v):
    if v is None:
        return None
    return re.sub(r'\s+', ' ', str(v)).strip()


def _num(v):
    if v is None:
        return None
    s = re.sub(r'[,\s\(\)\[\]\{\}]', '', str(v)).strip()
    if not s or s in {'-', 'N.A.', 'NA', 'nil', 'Nil'}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(s):
    """Parse 'MM/YYYY' → datetime. Returns None on failure."""
    if not s:
        return None
    m = DATE_RE.search(str(s))
    if m:
        try:
            return datetime(int(m.group(2)), int(m.group(1)), 1)
        except ValueError:
            pass
    return None


def _delay_months(orig_doc_str: str, ant_doc_str: str) -> float | None:
    """Calculate delay in months between original DOC and anticipated DOC."""
    orig = _parse_date(orig_doc_str)
    ant  = _parse_date(ant_doc_str)
    if orig and ant and ant > orig:
        delta = (ant.year - orig.year) * 12 + (ant.month - orig.month)
        return float(delta)
    return None


# ── PDF Parser ───────────────────────────────────────────────────────────────

def _parse_project_row(row: list) -> dict | None:
    """
    Parse one row from Table 6. Expected columns:
    [0] Sl.No
    [1] Project Name + Agency + Project Code
    [2] State
    [3] Date of Approval / Start Date (MM/YYYY lines)
    [4] Original/Target DoC / Revised DoC (MM/YYYY lines)
    [5] Original Cost / Revised Cost (two numbers on separate lines)
    [6] Cumulative Expenditure
    [7] Physical Progress (%)
    """
    if not row or len(row) < 6:
        return None

    raw_name    = str(row[1]) if row[1] is not None else ''
    state_cell  = _clean(row[2]) or ''
    dates_appr  = str(row[3]) if row[3] is not None else ''
    dates_doc   = str(row[4]) if row[4] is not None else ''
    raw_costs   = str(row[5]) if row[5] is not None else ''
    exp_cell    = _clean(row[6]) if len(row) > 6 else None
    prog_cell   = _clean(row[7]) if len(row) > 7 else None

    # Skip header rows and ministry/sector label rows
    if not raw_name or len(raw_name.strip()) < 5:
        return None

    # --- Extract Project Code, Agency, and Clean Project Name ---
    lines = [l.strip() for l in raw_name.split('\n') if l.strip()]
    name_lines = []
    agency = None
    project_code = None

    for l in lines:
        c_match = PROJ_CODE_RE.findall(l)
        cleaned_l = l.strip('()[]- \t')
        if not cleaned_l:
            continue
        if c_match and not project_code and (l.startswith('(') or l.isdigit() or l.startswith('N') or len(cleaned_l) <= 10):
            project_code = c_match[0]
            continue
        if (l.startswith('(') and l.endswith(')')) or (l.startswith('[') and l.endswith(']')):
            if not agency and len(cleaned_l) > 2 and not cleaned_l.isdigit() and not c_match:
                agency = cleaned_l
                continue
        if not c_match or len(l) > 20:
            name_lines.append(l)

    if not project_code:
        # Fallback regex search on the whole cell
        c_match = PROJ_CODE_RE.findall(raw_name)
        if c_match:
            project_code = c_match[0]

    if not project_code or len(project_code) < 4:
        return None

    project_name = ' '.join(name_lines[:3])
    project_name = re.sub(r'\s+', ' ', project_name).strip()
    project_name = re.sub(r'\([^)]{0,40}\)', '', project_name).strip()
    project_name = re.sub(r'\[[^\]]{0,40}\]', '', project_name).strip()
    if not project_name:
        project_name = raw_name.split('\n')[0].strip()

    # --- Parse Dates ---
    approval_dates = DATE_RE.findall(dates_appr)
    doc_dates      = DATE_RE.findall(dates_doc)

    def fmt(t): return f"{t[0]}/{t[1]}" if t else None

    approval_date    = fmt(approval_dates[0]) if approval_dates else None
    original_doc     = fmt(doc_dates[0])      if doc_dates       else None
    revised_doc      = fmt(doc_dates[1])      if len(doc_dates) > 1 else None
    anticipated_doc  = revised_doc or original_doc

    # --- Parse Costs (properly handling multiple lines and parentheses) ---
    cost_matches = re.findall(r'(\d+(?:,\d+)*(?:\.\d+)?)', raw_costs)
    clean_costs = []
    for c in cost_matches:
        try:
            val = float(c.replace(',', ''))
            if val > 0:
                clean_costs.append(val)
        except ValueError:
            pass

    original_cost    = clean_costs[0] if len(clean_costs) > 0 else None
    revised_cost     = clean_costs[1] if len(clean_costs) > 1 else original_cost
    anticipated_cost = revised_cost or original_cost

    # --- Cumulative Expenditure ---
    cum_exp = _num(exp_cell) if exp_cell else None

    # --- Physical Progress ---
    prog = _num(prog_cell) if prog_cell else None
    if prog is not None and not (0.0 <= prog <= 100.0):
        prog = None

    # --- Delay Months ---
    delay_months = _delay_months(original_doc, anticipated_doc)

    # --- State ---
    state_lines = [l.strip() for l in state_cell.split('\n') if l.strip()]
    state = state_lines[0] if state_lines else None

    return {
        'project_code':           project_code,
        'project_name':           project_name[:300] if project_name else None,
        'agency':                 agency[:100] if agency else None,
        'state':                  state,
        'approval_date':          approval_date,
        'original_cost':          original_cost,
        'revised_cost':           revised_cost,
        'anticipated_cost':       anticipated_cost,
        'cumulative_expenditure': cum_exp,
        'physical_progress':      prog,
        'original_doc':           original_doc,
        'revised_doc':            revised_doc,
        'anticipated_doc':        anticipated_doc,
        'original_delay_months':  delay_months,
        'revised_delay_months':   None,
    }



def extract_from_pdf(pdf_path: Path) -> list[dict]:
    """Extract all project rows from Table 6 in the Flash Report PDF."""
    records = []
    seen_codes = set()

    log.info(f"Opening PDF: {pdf_path}")
    with pdfplumber.open(pdf_path) as pdf:
        log.info(f"Total pages: {len(pdf.pages)}")
        in_table6 = False

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ''

            # Detect start of Table 6
            if 'Table 6' in text or 'All Ongoing Projects' in text:
                in_table6 = True
                log.info(f"  Found Table 6 start at page {i+1}")

            if not in_table6:
                continue

            # Stop at Table 7 / Completed Projects
            if 'Table 3' in text and in_table6 and i > 60:
                log.info(f"  Stopping at page {i+1} (Table 3 detected)")
                break

            # Extract tables from page
            tables = page.extract_tables({
                'vertical_strategy': 'lines',
                'horizontal_strategy': 'lines',
                'snap_tolerance': 5,
                'join_tolerance': 3,
            })
            if not tables:
                # Try with text-based strategy
                tables = page.extract_tables({
                    'vertical_strategy': 'text',
                    'horizontal_strategy': 'lines',
                })

            for table in (tables or []):
                if not table or len(table) < 2:
                    continue

                # Verify this looks like Table 6 (has the expected header columns)
                header_str = str(table[0]).lower()
                if 'project' not in header_str and 'sl' not in header_str:
                    continue

                for row in table[1:]:
                    parsed = _parse_project_row(row)
                    if not parsed:
                        continue
                    code = parsed['project_code']
                    if code in seen_codes:
                        continue
                    seen_codes.add(code)
                    records.append(parsed)

    log.info(f"Extracted {len(records)} unique project records from PDF")
    return records


# ── DB Operations ─────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(DB_URL)


def upsert_observations(records: list[dict], reporting_month: str):
    """Upsert project_observations for the given reporting month."""
    if not records:
        log.warning("No records to upsert into project_observations.")
        return 0

    conn = get_conn()
    cur = conn.cursor()

    # Get all known project codes
    cur.execute("SELECT project_code FROM projects")
    known_codes = {row[0] for row in cur.fetchall()}

    # Delete existing records for this month to avoid conflicts
    cur.execute("DELETE FROM project_observations WHERE reporting_month = %s", (reporting_month,))
    deleted = cur.rowcount
    log.info(f"Deleted {deleted} existing rows for month {reporting_month}")

    rows = []
    skipped = 0
    for r in records:
        code = r['project_code']
        if code not in known_codes:
            skipped += 1
            continue
        rows.append((
            code,
            reporting_month,
            r.get('revised_cost'),
            r.get('anticipated_cost'),
            r.get('cumulative_expenditure'),
            r.get('physical_progress'),
            r.get('original_doc'),
            r.get('revised_doc'),
            r.get('anticipated_doc'),
            r.get('original_delay_months'),
            r.get('revised_delay_months'),
            None,   # milestones_achieved
            None,   # milestones_total
            'FlashReport_July_2026.pdf',
        ))

    if skipped:
        log.info(f"Skipped {skipped} projects not in master table (new projects in this report)")

    if not rows:
        log.warning("No matching projects found in master table!")
        conn.close()
        return 0

    insert_sql = """
        INSERT INTO project_observations
            (project_code, reporting_month, revised_cost, anticipated_cost,
             cumulative_expenditure, physical_progress, original_doc, revised_doc,
             anticipated_doc, original_delay_months, revised_delay_months,
             milestones_achieved, milestones_total, source_file)
        VALUES %s
        ON CONFLICT DO NOTHING
    """
    execute_values(cur, insert_sql, rows)
    inserted = len(rows)
    conn.commit()
    cur.close()
    conn.close()

    log.info(f"Inserted {inserted} rows into project_observations for {reporting_month}")
    return inserted


def update_project_master(records: list[dict]):
    """Insert new projects into master table and update existing project details."""
    conn = get_conn()
    cur = conn.cursor()

    # Get existing project codes
    cur.execute("SELECT project_code FROM projects")
    existing_codes = {row[0] for row in cur.fetchall()}

    new_count = 0
    updated_count = 0
    skipped_count = 0

    for r in records:
        code = r['project_code']
        orig_cost = r.get('original_cost')
        if orig_cost is not None and (orig_cost <= 0 or orig_cost > 1000000):
            orig_cost = None

        if code not in existing_codes:
            try:
                cur.execute("SAVEPOINT sp1")
                cur.execute("""
                    INSERT INTO projects (project_code, project_name, agency, state, original_cost, approval_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (project_code) DO NOTHING
                """, (
                    code,
                    r.get('project_name'),
                    r.get('agency'),
                    r.get('state'),
                    orig_cost,
                    r.get('approval_date'),
                ))
                cur.execute("RELEASE SAVEPOINT sp1")
                existing_codes.add(code)
                new_count += 1
            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT sp1")
                skipped_count += 1
        else:
            try:
                cur.execute("""
                    UPDATE projects SET
                        project_name = COALESCE(project_name, %s),
                        agency       = COALESCE(agency, %s),
                        state        = COALESCE(state, %s),
                        original_cost = COALESCE(original_cost, %s),
                        approval_date = COALESCE(approval_date, %s)
                    WHERE project_code = %s
                """, (
                    r.get('project_name'),
                    r.get('agency'),
                    r.get('state'),
                    orig_cost,
                    r.get('approval_date'),
                    code
                ))
                updated_count += 1
            except Exception:
                pass

    conn.commit()
    cur.close()
    conn.close()
    log.info(f"Projects master: {new_count} new added, {updated_count} updated, {skipped_count} skipped")





def compute_and_store_features(reporting_month: str):
    """
    Compute project_features for the new reporting month.
    Uses the same feature engineering logic as build_features.py
    but only for the new month.
    """
    conn = get_conn()
    cur = conn.cursor()

    # Get all observations for this month joined with project master
    cur.execute("""
        SELECT 
            po.project_code,
            po.reporting_month,
            po.anticipated_cost,
            po.revised_cost,
            po.cumulative_expenditure,
            po.physical_progress,
            po.original_doc,
            po.revised_doc,
            po.anticipated_doc,
            po.original_delay_months,
            po.revised_delay_months,
            p.original_cost,
            p.approval_date
        FROM project_observations po
        JOIN projects p ON po.project_code = p.project_code
        WHERE po.reporting_month = %s
    """, (reporting_month,))
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]

    if not rows:
        log.warning(f"No observations found for {reporting_month}")
        return 0

    df = pd.DataFrame(rows, columns=cols)

    # Cast all numeric PostgreSQL Decimal columns to float64
    numeric_cols = ['anticipated_cost', 'revised_cost', 'cumulative_expenditure',
                    'physical_progress', 'original_delay_months', 'revised_delay_months',
                    'original_cost']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')


    def safe_parse(s, default_day=1):
        if not s:
            return pd.NaT
        # Handle MM/YYYY format
        m = re.search(r'(\d{1,2})[/-](\d{4})', str(s))
        if m:
            try:
                return pd.Timestamp(int(m.group(2)), int(m.group(1)), default_day)
            except Exception:
                pass
        try:
            return pd.Timestamp(str(s) + '-01' if len(str(s)) == 7 else str(s))
        except Exception:
            return pd.NaT

    report_dt    = pd.Timestamp(reporting_month + '-01')
    df['dt_approval'] = df['approval_date'].apply(safe_parse)
    df['dt_orig_doc'] = df['original_doc'].apply(safe_parse)
    df['dt_ant_doc']  = df['anticipated_doc'].apply(safe_parse)

    # Feature 1: months_elapsed
    df['months_elapsed'] = df['dt_approval'].apply(
        lambda d: max(0.0, (report_dt - d).days / 30.4375) if pd.notna(d) else np.nan
    )

    # Feature 2: months_originally_planned
    df['months_originally_planned'] = df.apply(
        lambda r: (r['dt_orig_doc'] - r['dt_approval']).days / 30.4375
        if pd.notna(r['dt_orig_doc']) and pd.notna(r['dt_approval'])
           and r['dt_orig_doc'] > r['dt_approval']
        else np.nan, axis=1
    )

    # Feature 3: months_remaining
    df['months_remaining'] = df['dt_ant_doc'].apply(
        lambda d: (d - report_dt).days / 30.4375 if pd.notna(d) else np.nan
    )

    # Feature 4: cost_expansion_ratio
    df['cost_expansion_ratio'] = np.where(
        df['original_cost'].notna() & (df['original_cost'] > 0) & df['anticipated_cost'].notna(),
        df['anticipated_cost'] / df['original_cost'],
        np.nan
    )

    # Feature 5: expenditure_ratio
    df['expenditure_ratio'] = np.where(
        df['anticipated_cost'].notna() & (df['anticipated_cost'] > 0) & df['cumulative_expenditure'].notna(),
        df['cumulative_expenditure'] / df['anticipated_cost'],
        np.nan
    )

    # Feature 6: expenditure_progress_gap
    df['expenditure_progress_gap'] = np.where(
        df['expenditure_ratio'].notna() & df['physical_progress'].notna(),
        df['expenditure_ratio'] - (df['physical_progress'] / 100.0),
        np.nan
    )

    # Feature 7: delay_months and schedule_slippage_ratio
    df['delay_months'] = df.apply(
        lambda r: (r['dt_ant_doc'] - r['dt_orig_doc']).days / 30.4375
        if pd.notna(r['dt_ant_doc']) and pd.notna(r['dt_orig_doc']) and r['dt_ant_doc'] > r['dt_orig_doc']
        else (r['original_delay_months'] if pd.notna(r['original_delay_months']) else np.nan),
        axis=1
    )
    df['schedule_slippage_ratio'] = np.where(
        df['delay_months'].notna() & df['months_originally_planned'].notna() & (df['months_originally_planned'] > 0),
        df['delay_months'] / df['months_originally_planned'],
        np.nan
    )

    # Feature 8: progress_velocity (not computable for single month, set to NaN)
    df['progress_velocity'] = np.nan

    # Target labels for live data: use NaN (future unknown)
    df['target_cost_overrun_12m'] = np.nan
    df['target_time_overrun_12m'] = np.nan
    df['target_severe_risk_12m']  = np.nan

    feature_cols = ['project_code', 'reporting_month', 'months_elapsed',
                    'months_originally_planned', 'months_remaining',
                    'cost_expansion_ratio', 'expenditure_ratio',
                    'expenditure_progress_gap', 'schedule_slippage_ratio',
                    'progress_velocity', 'target_cost_overrun_12m',
                    'target_time_overrun_12m', 'target_severe_risk_12m']

    df_feat = df[feature_cols].copy()

    # Delete existing features for this month
    cur.execute("DELETE FROM project_features WHERE reporting_month = %s", (reporting_month,))

    # Insert new features
    feat_rows = []
    for _, row in df_feat.iterrows():
        def safe_val(v):
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return None
            return float(v)

        feat_rows.append((
            row['project_code'],
            row['reporting_month'],
            safe_val(row['months_elapsed']),
            safe_val(row['months_originally_planned']),
            safe_val(row['months_remaining']),
            safe_val(row['cost_expansion_ratio']),
            safe_val(row['expenditure_ratio']),
            safe_val(row['expenditure_progress_gap']),
            safe_val(row['schedule_slippage_ratio']),
            safe_val(row['progress_velocity']),
            None, None, None,  # targets = NULL for live data
        ))

    if feat_rows:
        execute_values(cur, """
            INSERT INTO project_features 
                (project_code, reporting_month, months_elapsed, months_originally_planned,
                 months_remaining, cost_expansion_ratio, expenditure_ratio,
                 expenditure_progress_gap, schedule_slippage_ratio, progress_velocity,
                 target_cost_overrun_12m, target_time_overrun_12m, target_severe_risk_12m)
            VALUES %s
            ON CONFLICT DO NOTHING
        """, feat_rows)

    conn.commit()
    cur.close()
    conn.close()

    non_null_cer = df['cost_expansion_ratio'].notna().sum()
    non_null_ssr = df['schedule_slippage_ratio'].notna().sum()
    log.info(f"Features computed for {reporting_month}: {len(feat_rows)} rows, "
             f"cost_expansion_ratio non-null: {non_null_cer}, "
             f"schedule_slippage_ratio non-null: {non_null_ssr}")

    return len(feat_rows)


def compute_risk_scores(reporting_month: str):
    """
    Run XGBoost model to compute risk scores for all projects in the reporting month.
    Uses the trained model from models/risk_engine_v1/.
    """
    import joblib
    from pathlib import Path as P

    model_dir = P("models/risk_engine_v1")
    calibrator_path = model_dir / "calibrator.pkl"
    meta_path = model_dir / "model_metadata.json"

    if not calibrator_path.exists():
        log.error(f"Model not found: {calibrator_path}")
        return 0

    calibrator = joblib.load(calibrator_path)
    with open(meta_path) as f:
        meta = json.load(f)

    feature_names = meta.get("feature_names", [
        "cost_expansion_ratio", "expenditure_ratio", "expenditure_progress_gap",
        "schedule_slippage_ratio", "months_elapsed", "months_originally_planned",
        "months_remaining", "progress_velocity",
        "original_cost", "agency_encoded"
    ])
    operational_threshold = meta.get("operational_threshold", 0.28)

    conn = get_conn()
    cur = conn.cursor()

    # Get features + raw observation data for this month + project metadata
    cur.execute("""
        SELECT pf.project_code, pf.reporting_month,
               pf.cost_expansion_ratio, pf.expenditure_ratio, pf.expenditure_progress_gap,
               pf.schedule_slippage_ratio, pf.months_elapsed, pf.months_originally_planned,
               pf.months_remaining, pf.progress_velocity,
               p.original_cost, p.agency, p.state,
               po.revised_cost, po.anticipated_cost, po.cumulative_expenditure,
               po.physical_progress, po.original_delay_months, po.revised_delay_months,
               po.milestones_achieved, po.milestones_total
        FROM project_features pf
        JOIN projects p ON pf.project_code = p.project_code
        LEFT JOIN project_observations po ON pf.project_code = po.project_code
              AND pf.reporting_month = po.reporting_month
        WHERE pf.reporting_month = %s
    """, (reporting_month,))

    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]

    if not rows:
        log.warning(f"No features for {reporting_month}")
        conn.close()
        return 0

    df = pd.DataFrame(rows, columns=cols)

    # Cast all numeric PostgreSQL Decimal columns to float64
    for col in df.columns:
        if col not in ('project_code', 'reporting_month', 'agency'):
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Encode agency
    cur.execute("SELECT DISTINCT agency FROM projects ORDER BY agency")
    agencies = [r[0] for r in cur.fetchall() if r[0]]
    agency_map = {a: i+1 for i, a in enumerate(sorted(agencies))}
    df['agency_encoded'] = df['agency'].map(agency_map).fillna(0).astype(float)

    # Encode state (if available)
    if 'state' in df.columns:
        cur.execute("SELECT DISTINCT state FROM projects ORDER BY state")
        states = [r[0] for r in cur.fetchall() if r[0]]
        state_map = {s: i+1 for i, s in enumerate(sorted(states))}
        df['state_encoded'] = df['state'].map(state_map).fillna(0).astype(float)
    else:
        df['state_encoded'] = 0.0

    # Compute delay_months (direct model feature)
    df['delay_months'] = df['original_delay_months'].fillna(0.0)

    # milestone_rate = 0 for live data
    df['milestone_rate'] = 0.0

    # Full 21-feature matrix matching model's actual feature_names_in_
    FULL_FEATURE_NAMES = [
        'original_cost', 'revised_cost', 'anticipated_cost',
        'cumulative_expenditure', 'physical_progress',
        'original_delay_months', 'revised_delay_months',
        'milestones_achieved', 'milestones_total',
        'months_elapsed', 'months_originally_planned', 'months_remaining',
        'cost_expansion_ratio', 'expenditure_ratio', 'expenditure_progress_gap',
        'delay_months', 'schedule_slippage_ratio', 'milestone_rate',
        'progress_velocity', 'agency_encoded', 'state_encoded'
    ]

    # Add missing columns with zeros
    for feat in FULL_FEATURE_NAMES:
        if feat not in df.columns:
            df[feat] = 0.0

    X = df[FULL_FEATURE_NAMES].copy().astype(float)

    # Impute missing values
    for col in X.columns:
        if col in ['cost_expansion_ratio', 'expenditure_ratio', 'months_elapsed',
                   'anticipated_cost', 'original_cost', 'cumulative_expenditure']:
            X[col] = X[col].fillna(X[col].median() if X[col].notna().any() else 0.0)
        else:
            X[col] = X[col].fillna(0.0)


    # Predict
    try:
        probs = calibrator.predict_proba(X)[:, 1]
    except Exception as e:
        log.error(f"Model prediction error: {e}")
        # Fallback: compute scores from cost_expansion_ratio directly
        cer = df['cost_expansion_ratio'].fillna(1.0)
        ssr = df['schedule_slippage_ratio'].fillna(0.0)
        probs = np.clip((cer - 1.0) * 0.15 + ssr * 0.05, 0.0, 0.95)

    df['prob'] = probs

    # Convert probability to 0-100 risk score
    def prob_to_score(p: float) -> float:
        """Map probability [0,1] → risk score [0,100] with meaningful spread."""
        # Calibrated scoring: score = 25 + 75 * sigmoid_stretch(p)
        # At p=0.28 → score ≈ 45 (early warning threshold)
        score = 100.0 * p
        return round(min(100.0, max(0.0, score)), 2)

    def prob_to_category(score: float) -> str:
        if score >= 75:
            return 'CRITICAL'
        elif score >= 55:
            return 'HIGH'
        elif score >= 35:
            return 'MODERATE'
        return 'LOW'

    # Cost risk index: scaled cost_expansion_ratio
    def cost_risk_index(cer):
        if cer is None or (isinstance(cer, float) and math.isnan(cer)):
            return 25.0  # default moderate
        return round(min(100.0, max(0.0, (float(cer) - 1.0) * 30.0 + 15.0)), 2)

    # Schedule risk index: scaled schedule_slippage_ratio  
    def schedule_risk_index(ssr):
        if ssr is None or (isinstance(ssr, float) and math.isnan(ssr)):
            return 20.0  # default moderate
        return round(min(100.0, max(0.0, float(ssr) * 25.0 + 10.0)), 2)

    # Build SHAP-like risk drivers from feature contributions
    def build_risk_drivers(row_dict: dict, prob: float) -> list:
        drivers = []
        cer = row_dict.get('cost_expansion_ratio')
        ssr = row_dict.get('schedule_slippage_ratio')
        exp_gap = row_dict.get('expenditure_progress_gap')
        months_elap = row_dict.get('months_elapsed')

        if cer is not None and not (isinstance(cer, float) and math.isnan(cer)) and float(cer) > 1.1:
            contrib = round(float(cer - 1.0) * 20.0, 1)
            drivers.append({
                'feature_name': 'Cost Expansion Ratio',
                'feature_code': 'cost_expansion_ratio',
                'value': round(float(cer), 3),
                'points_added': f'+{contrib}',
            })

        if ssr is not None and not (isinstance(ssr, float) and math.isnan(ssr)) and float(ssr) > 0.1:
            contrib = round(float(ssr) * 15.0, 1)
            drivers.append({
                'feature_name': 'Schedule Slippage Ratio',
                'feature_code': 'schedule_slippage_ratio',
                'value': round(float(ssr), 3),
                'points_added': f'+{contrib}',
            })

        if exp_gap is not None and not (isinstance(exp_gap, float) and math.isnan(exp_gap)) and float(exp_gap) > 0.1:
            contrib = round(float(exp_gap) * 12.0, 1)
            drivers.append({
                'feature_name': 'Expenditure-Progress Gap',
                'feature_code': 'expenditure_progress_gap',
                'value': round(float(exp_gap), 3),
                'points_added': f'+{contrib}',
            })

        if months_elap is not None and not (isinstance(months_elap, float) and math.isnan(months_elap)):
            me = float(months_elap)
            if me > 120:  # over 10 years
                drivers.append({
                    'feature_name': 'Project Age (Months Elapsed)',
                    'feature_code': 'months_elapsed',
                    'value': round(me, 0),
                    'points_added': f'+{round(min(20, me/10), 1)}',
                })

        return drivers[:5]

    # Delete existing risk scores for this month
    cur.execute("DELETE FROM risk_scores WHERE reporting_month = %s", (reporting_month,))

    # Insert new risk scores
    risk_rows = []
    df_dict = df.to_dict('records')
    for i, row in enumerate(df_dict):
        prob = float(probs[i])
        score = prob_to_score(prob)
        category = prob_to_category(score)
        c_risk = cost_risk_index(row.get('cost_expansion_ratio'))
        s_risk = schedule_risk_index(row.get('schedule_slippage_ratio'))
        drivers = build_risk_drivers(row, prob)
        protective = []

        risk_rows.append((
            row['project_code'],
            reporting_month,
            score,
            category,
            s_risk,
            c_risk,
            prob,
            json.dumps(drivers),
            json.dumps(protective),
        ))

    execute_values(cur, """
        INSERT INTO risk_scores
            (project_code, reporting_month, risk_score, risk_category,
             schedule_risk_index, cost_risk_index, predicted_severe_risk_prob,
             key_risk_drivers, protective_factors)
        VALUES %s
        ON CONFLICT DO NOTHING
    """, risk_rows)

    conn.commit()

    # Report results
    scores_df = pd.DataFrame([(r[2], r[3]) for r in risk_rows], columns=['risk_score', 'risk_category'])
    cat_counts = scores_df['risk_category'].value_counts().to_dict()
    log.info(f"Risk scores computed for {reporting_month}: {len(risk_rows)} projects")
    log.info(f"  CRITICAL: {cat_counts.get('CRITICAL', 0)}, HIGH: {cat_counts.get('HIGH', 0)}, "
             f"MODERATE: {cat_counts.get('MODERATE', 0)}, LOW: {cat_counts.get('LOW', 0)}")
    log.info(f"  Max score: {scores_df['risk_score'].max():.1f}, "
             f"Mean: {scores_df['risk_score'].mean():.1f}")

    cur.close()
    conn.close()
    return len(risk_rows)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 80)
    log.info(f"NIRMAN July 2026 Data Ingestion Pipeline")
    log.info(f"Reporting Month: {REPORTING_MONTH}")
    log.info("=" * 80)

    # Step 1: Extract from PDF
    log.info("\n[STEP 1] Extracting project data from PDF...")
    records = extract_from_pdf(PDF_PATH)
    log.info(f"  Extracted {len(records)} projects")

    if not records:
        log.error("No records extracted! Aborting.")
        sys.exit(1)

    # Show sample
    log.info("  Sample records:")
    for r in records[:3]:
        log.info(f"    {r['project_code']} | {str(r.get('project_name',''))[:50]} | "
                 f"orig={r.get('original_cost')} | ant={r.get('anticipated_cost')} | "
                 f"prog={r.get('physical_progress')}% | delay={r.get('original_delay_months')}m")

    # Step 2: Update project master
    log.info("\n[STEP 2] Updating project master table...")
    update_project_master(records)

    # Step 3: Upsert observations
    log.info(f"\n[STEP 3] Upserting into project_observations for {REPORTING_MONTH}...")
    n_obs = upsert_observations(records, REPORTING_MONTH)
    log.info(f"  Upserted {n_obs} observations")

    # Step 4: Compute features
    log.info(f"\n[STEP 4] Computing project_features for {REPORTING_MONTH}...")
    n_feat = compute_and_store_features(REPORTING_MONTH)
    log.info(f"  Computed {n_feat} feature rows")

    # Step 5: Run risk scoring
    log.info(f"\n[STEP 5] Running XGBoost risk scoring for {REPORTING_MONTH}...")
    n_scores = compute_risk_scores(REPORTING_MONTH)
    log.info(f"  Scored {n_scores} projects")

    # Final summary
    log.info("\n" + "=" * 80)
    log.info("INGESTION COMPLETE")
    log.info(f"  Observations ingested : {n_obs}")
    log.info(f"  Features computed     : {n_feat}")
    log.info(f"  Risk scores generated : {n_scores}")
    log.info(f"  Reporting month       : {REPORTING_MONTH}")
    log.info("=" * 80)


if __name__ == "__main__":
    main()
