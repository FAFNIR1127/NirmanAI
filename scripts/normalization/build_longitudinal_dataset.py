from pathlib import Path
import json
import re
import pandas as pd
import numpy as np


# ============================================================
# PATHS
# ============================================================

EXTRACTED_DIR = Path("processed/extracted")

OUTPUT_PARQUET = Path("processed/normalized/longitudinal_projects.parquet")
OUTPUT_CSV = Path("processed/normalized/longitudinal_projects.csv")

FILE_MONTH_MAP = {
    "historical_2017_april.json": "2017-04",
    "historical_2018_april.json": "2018-04",
    "historical_2019_april.json": "2019-04",
    "historical_2020_april.json": "2020-04",
    "historical_2021_april.json": "2021-04",
    "historical_2022_april.json": "2022-04",
    "historical_2023_april.json": "2023-04",
    "historical_2024_april.json": "2024-04",
    "historical_2025_april.json": "2025-04",
    "historical_2026_april.json": "2026-04",
    "july_2025_all_ongoing.json": "2025-07",
    "july_2026_all_ongoing.json": "2026-07",
    "august_2025_all_ongoing.json": "2025-08",
}


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def clean_name(name):
    if not name or pd.isna(name):
        return None
    s = str(name).strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^\d+\s+", "", s)
    return s.strip() if s else None


def clean_code(code):
    if not code or pd.isna(code):
        return None
    s = str(code).strip().upper()
    m = re.search(r"(N\d{8}|\d{9})", s)
    return m.group(1) if m else None


def clean_date(val):
    if not val or pd.isna(val) or val in {"-", "N.A.", "NA"}:
        return None
    s = str(val).strip().replace("-", "/")
    s = re.sub(r"^[^\d]+", "", s)
    s = re.sub(r"[^\d]+$", "", s)
    parts = s.split("/")
    if len(parts) == 2:
        m, y = parts[0], parts[1]
        if len(m) == 1:
            m = "0" + m
        if len(y) == 4 and 1990 <= int(y) <= 2045 and 1 <= int(m) <= 12:
            return f"{y}-{m}"
    return None


def clean_numeric(val):
    if val is None or pd.isna(val) or val in {"-", "N.A.", "NA"}:
        return None
    try:
        f = float(str(val).replace(",", "").replace("(", "").replace(")", "").replace("[", "").replace("]", "").strip())
        return f if not np.isnan(f) else None
    except ValueError:
        return None


# ============================================================
# MAIN BUILD PIPELINE
# ============================================================

def build_longitudinal_dataset():
    all_rows = []

    for fname, reporting_month in FILE_MONTH_MAP.items():
        fpath = EXTRACTED_DIR / fname
        if not fpath.exists():
            continue

        with fpath.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            continue

        for item in data:
            if not isinstance(item, dict):
                continue

            p_code = clean_code(item.get("project_code"))
            if not p_code:
                continue

            orig_cost = clean_numeric(item.get("original_cost"))
            rev_cost = clean_numeric(item.get("revised_cost"))
            ant_cost = clean_numeric(item.get("anticipated_cost"))
            cum_exp = clean_numeric(item.get("cumulative_expenditure"))
            progress = clean_numeric(item.get("physical_progress"))

            if progress is not None and (progress < 0 or progress > 100):
                progress = None

            if orig_cost is not None and orig_cost < 0:
                orig_cost = None
            if ant_cost is not None and ant_cost < 0:
                ant_cost = None
            if cum_exp is not None and cum_exp < 0:
                cum_exp = None

            row = {
                "project_code": p_code,
                "reporting_month": reporting_month,
                "project_name": clean_name(item.get("project_name")),
                "agency": clean_name(item.get("agency")),
                "state": clean_name(item.get("state")),
                "approval_date": clean_date(item.get("approval_date")),
                "original_cost": orig_cost,
                "revised_cost": rev_cost,
                "anticipated_cost": ant_cost,
                "cumulative_expenditure": cum_exp,
                "physical_progress": progress,
                "original_doc": clean_date(item.get("original_doc")),
                "revised_doc": clean_date(item.get("revised_doc")),
                "anticipated_doc": clean_date(item.get("anticipated_doc")),
                "original_delay_months": clean_numeric(item.get("original_delay_months")),
                "revised_delay_months": clean_numeric(item.get("revised_delay_months")),
                "milestones_achieved": clean_numeric(item.get("milestones_achieved")),
                "milestones_total": clean_numeric(item.get("milestones_total")),
                "source_file": fname,
            }
            all_rows.append(row)

    df = pd.DataFrame(all_rows)

    df = df.drop_duplicates(subset=["project_code", "reporting_month"], keep="last")
    df = df.sort_values(by=["project_code", "reporting_month"]).reset_index(drop=True)

    OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PARQUET, index=False)
    df.to_csv(OUTPUT_CSV, index=False)

    print("=" * 100)
    print("UNIFIED LONGITUDINAL DATASET CREATED SUCCESSFULLY")
    print("=" * 100)
    print(f"Total project-month observations : {len(df):,}")
    print(f"Unique projects tracked           : {df['project_code'].nunique():,}")
    print(f"Reporting months covered          : {df['reporting_month'].nunique()} ({df['reporting_month'].min()} to {df['reporting_month'].max()})")
    print(f"Saved Parquet                     : {OUTPUT_PARQUET}")
    print(f"Saved CSV                         : {OUTPUT_CSV}")

    return df


if __name__ == "__main__":
    build_longitudinal_dataset()
