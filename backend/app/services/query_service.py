import sqlite3
import sqlalchemy
import pandas as pd
from backend.app.config import DATABASE_URL, FALLBACK_SQLITE_PATH


def get_db_engine():
    try:
        engine = sqlalchemy.create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        return engine
    except Exception:
        return sqlalchemy.create_engine(f"sqlite:///{FALLBACK_SQLITE_PATH}")


def clean_records(records):
    cleaned = []
    for r in records:
        row = {}
        for k, v in r.items():
            if pd.isna(v) or v is None:
                row[k] = None
            elif isinstance(v, (pd.Timestamp, pd.Series)):
                row[k] = str(v)
            else:
                row[k] = v
        cleaned.append(row)
    return cleaned


def query_projects(
    search: str = None,
    sector: str = None,
    agency: str = None,
    state: str = None,
    ministry: str = None,
    risk_category: str = None,
    min_cost: float = None,
    max_cost: float = None,
    page: int = 1,
    page_size: int = 15,
    sort_by: str = "cost_overrun_cr",
    order: str = "desc"
):
    engine = get_db_engine()
    conditions = []
    params = {}

    if search:
        s = search.strip().lower()
        conditions.append("(LOWER(p.project_code) LIKE :search OR LOWER(p.project_name) LIKE :search OR LOWER(COALESCE(p.agency,'')) LIKE :search OR LOWER(COALESCE(p.state,'')) LIKE :search OR LOWER(COALESCE(p.sector,'')) LIKE :search OR p.project_code IN (SELECT canonical_code FROM project_aliases WHERE LOWER(alias_code) LIKE :search))")
        params["search"] = f"%{s}%"

    if sector and sector not in ("All", "All Sectors"):
        conditions.append("LOWER(COALESCE(p.sector, '')) LIKE :sector")
        params["sector"] = f"%{sector.strip().lower()}%"

    if ministry and ministry not in ("All", "All Ministries"):
        min_lower = ministry.strip().lower()
        # Map common ministry strings to sectors or keyword matches
        if "rail" in min_lower:
            conditions.append("(LOWER(COALESCE(p.sector, '')) LIKE '%rail%' OR LOWER(COALESCE(p.agency, '')) IN ('rvnl', 'ircon', 'dfccil', 'mrll', 'krcl', 'cr', 'nr', 'wr', 'sr', 'er'))")
        elif "road" in min_lower or "high" in min_lower or "transport" in min_lower:
            conditions.append("(LOWER(COALESCE(p.sector, '')) LIKE '%road%' OR LOWER(COALESCE(p.agency, '')) IN ('nhai', 'nhidcl', 'morth'))")
        elif "power" in min_lower or "energy" in min_lower:
            conditions.append("(LOWER(COALESCE(p.sector, '')) LIKE '%power%' OR LOWER(COALESCE(p.agency, '')) IN ('ntpc', 'pgcil', 'nhpc', 'sjvn', 'neepco', 'thdc'))")
        elif "petrol" in min_lower or "gas" in min_lower:
            conditions.append("(LOWER(COALESCE(p.sector, '')) LIKE '%petrol%' OR LOWER(COALESCE(p.agency, '')) IN ('ongc', 'iocl', 'bpcl', 'hpcl', 'gail', 'oil', 'nrl', 'mrpl'))")
        elif "coal" in min_lower or "mine" in min_lower:
            conditions.append("(LOWER(COALESCE(p.sector, '')) LIKE '%coal%' OR LOWER(COALESCE(p.sector, '')) LIKE '%mine%' OR LOWER(COALESCE(p.agency, '')) IN ('cil', 'secl', 'wcl', 'mcl', 'ccl', 'ecl', 'ncl', 'bcl', 'nmdc'))")
        elif "aviation" in min_lower or "airport" in min_lower:
            conditions.append("(LOWER(COALESCE(p.sector, '')) LIKE '%aviation%' OR LOWER(COALESCE(p.agency, '')) IN ('aai', 'ai'))")
        elif "port" in min_lower or "ship" in min_lower:
            conditions.append("(LOWER(COALESCE(p.sector, '')) LIKE '%port%' OR LOWER(COALESCE(p.sector, '')) LIKE '%ship%')")
        elif "telecom" in min_lower or "comm" in min_lower:
            conditions.append("(LOWER(COALESCE(p.sector, '')) LIKE '%telecom%')")
        elif "urban" in min_lower or "housing" in min_lower:
            conditions.append("(LOWER(COALESCE(p.sector, '')) LIKE '%urban%' OR LOWER(COALESCE(p.sector, '')) LIKE '%housing%')")
        else:
            conditions.append("(LOWER(COALESCE(p.sector, '')) LIKE :min_raw OR LOWER(COALESCE(p.agency, '')) LIKE :min_raw)")
            params["min_raw"] = f"%{min_lower}%"

    if agency and agency not in ("All", "All Agencies"):
        conditions.append("LOWER(COALESCE(p.agency, '')) LIKE :agency")
        params["agency"] = f"%{agency.strip().lower()}%"

    if state and state not in ("All", "All States", "All Regions"):
        conditions.append("LOWER(COALESCE(p.state, '')) LIKE :state")
        params["state"] = f"%{state.strip().lower()}%"

    if risk_category and risk_category != "All":
        cat_upper = risk_category.strip().upper()
        if cat_upper in ("NORMAL",):
            cat_upper = "LOW"
        elif cat_upper in ("WATCHLIST",):
            cat_upper = "MODERATE"
        conditions.append("r.risk_category = :risk_cat")
        params["risk_cat"] = cat_upper

    if min_cost is not None:
        conditions.append("p.original_cost >= :min_cost")
        params["min_cost"] = min_cost

    if max_cost is not None:
        conditions.append("p.original_cost <= :max_cost")
        params["max_cost"] = max_cost

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    sort_mapping = {
        "risk_score": "r.risk_score",
        "cost_overrun_cr": "GREATEST(0, COALESCE(o.anticipated_cost, p.original_cost, 0) - COALESCE(p.original_cost, 0))",
        "delay_months": "COALESCE(o.original_delay_months, o.revised_delay_months, 0)",
        "original_cost": "p.original_cost",
        "project_name": "p.project_name"
    }
    sort_expr = sort_mapping.get(sort_by, "r.risk_score")
    direction = "ASC" if (order and order.lower() == "asc") else "DESC"

    base_from = """
        FROM projects p
        LEFT JOIN (
            SELECT DISTINCT ON (project_code) project_code, risk_score, risk_category, reporting_month
            FROM risk_scores
            ORDER BY project_code, reporting_month DESC
        ) r ON p.project_code = r.project_code
        LEFT JOIN (
            SELECT DISTINCT ON (project_code) project_code, anticipated_cost, original_delay_months, revised_delay_months, physical_progress
            FROM project_observations
            ORDER BY project_code, reporting_month DESC
        ) o ON p.project_code = o.project_code
    """

    count_sql = f"SELECT COUNT(*) {base_from} {where_clause}"

    p = max(1, page)
    ps = max(1, min(1000, page_size))
    offset = (p - 1) * ps
    params["limit"] = ps
    params["offset"] = offset

    data_sql = f"""
        SELECT 
            p.project_code, p.project_name, p.project_name as name, p.agency, p.state, p.sector, p.approval_date, p.original_cost,
            r.risk_score, r.risk_category, r.reporting_month,
            o.anticipated_cost,
            COALESCE(o.original_delay_months, o.revised_delay_months, 0) as delay_months,
            o.physical_progress
        {base_from}
        {where_clause}
        ORDER BY {sort_expr} {direction} NULLS LAST
        LIMIT :limit OFFSET :offset
    """

    with engine.connect() as conn:
        total = conn.execute(sqlalchemy.text(count_sql), params).scalar() or 0
        df = pd.read_sql(sqlalchemy.text(data_sql), conn, params=params)

    return {
        "total": int(total),
        "page": p,
        "page_size": ps,
        "projects": clean_records(df.to_dict(orient="records"))
    }


def search_projects(query_str: str, limit: int = 50):
    res = query_projects(search=query_str, page=1, page_size=limit)
    return res["projects"]


def filter_projects(
    state: str = None,
    agency: str = None,
    risk_category: str = None,
    min_cost: float = None,
    max_cost: float = None,
    limit: int = 100
):
    res = query_projects(
        state=state,
        agency=agency,
        risk_category=risk_category,
        min_cost=min_cost,
        max_cost=max_cost,
        page=1,
        page_size=limit
    )
    return res["projects"]




def compare_projects(project_codes: list):
    if not project_codes:
        return []

    engine = get_db_engine()
    sql = """
        SELECT p.project_code, p.project_name, p.agency, p.state, p.approval_date, p.original_cost,
               r.risk_score, r.risk_category, r.schedule_risk_index, r.cost_risk_index,
               obs.anticipated_cost as latest_anticipated_cost, f.schedule_slippage_ratio, f.cost_expansion_ratio
        FROM projects p
        LEFT JOIN (
            SELECT DISTINCT ON (project_code) project_code, risk_score, risk_category, schedule_risk_index, cost_risk_index
            FROM risk_scores
            ORDER BY project_code, reporting_month DESC
        ) r ON p.project_code = r.project_code
        LEFT JOIN (
            SELECT DISTINCT ON (project_code) project_code, anticipated_cost
            FROM project_observations
            WHERE anticipated_cost IS NOT NULL
            ORDER BY project_code, reporting_month DESC
        ) obs ON p.project_code = obs.project_code
        LEFT JOIN (
            SELECT DISTINCT ON (project_code) project_code, schedule_slippage_ratio, cost_expansion_ratio
            FROM project_features
            ORDER BY project_code, reporting_month DESC
        ) f ON p.project_code = f.project_code
        WHERE p.project_code IN :codes
    """
    with engine.connect() as conn:
        # Pass tuple for IN clause in SQLAlchemy
        df = pd.read_sql(sqlalchemy.text(sql), conn, params={"codes": tuple(project_codes)})

    results = []
    for _, row in df.iterrows():
        orig = float(row["original_cost"]) if pd.notna(row.get("original_cost")) else None
        ant = float(row["latest_anticipated_cost"]) if pd.notna(row.get("latest_anticipated_cost")) else None
        overrun_pct = round(((ant - orig) / orig) * 100.0, 2) if (orig and ant and orig > 0) else None

        results.append({
            "project_code": str(row["project_code"]),
            "project_name": str(row["project_name"]) if pd.notna(row.get("project_name")) else None,
            "agency": str(row["agency"]) if pd.notna(row.get("agency")) else None,
            "state": str(row["state"]) if pd.notna(row.get("state")) else None,
            "approval_date": str(row["approval_date"]) if pd.notna(row.get("approval_date")) else None,
            "original_cost": orig,
            "latest_anticipated_cost": ant,
            "cost_overrun_percent": overrun_pct,
            "delay_months": float(row["schedule_slippage_ratio"] * 12.0) if pd.notna(row.get("schedule_slippage_ratio")) else None,
            "risk_score": float(row["risk_score"]) if pd.notna(row.get("risk_score")) else None,
            "risk_category": str(row["risk_category"]) if pd.notna(row.get("risk_category")) else None,
            "schedule_risk_index": float(row["schedule_risk_index"]) if pd.notna(row.get("schedule_risk_index")) else None,
            "cost_risk_index": float(row["cost_risk_index"]) if pd.notna(row.get("cost_risk_index")) else None
        })
    return results


def get_project_by_code(project_code: str):
    res = compare_projects([project_code])
    return res[0] if res else None


def get_filter_options():
    engine = get_db_engine()
    with engine.connect() as conn:
        agency_rows = conn.execute(sqlalchemy.text("""
            SELECT agency, COUNT(*) as cnt 
            FROM projects 
            WHERE agency IS NOT NULL AND agency != '' 
            GROUP BY agency 
            ORDER BY cnt DESC 
            LIMIT 50
        """)).fetchall()
        agencies = [r[0] for r in agency_rows]

        state_rows = conn.execute(sqlalchemy.text("""
            SELECT DISTINCT state 
            FROM projects 
            WHERE state IS NOT NULL AND state != '' 
            ORDER BY state ASC
        """)).fetchall()
        raw_states = [r[0].strip() for r in state_rows if r[0] and len(r[0].strip()) > 1]
        
        # Canonical Indian States & UTs
        canonical_states = [
            "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
            "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
            "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
            "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
            "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
            "Uttar Pradesh", "Uttarakhand", "West Bengal",
            "Andaman and Nicobar", "Chandigarh", "Dadra and Nagar Haveli",
            "Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh",
            "Lakshadweep", "Puducherry", "Multi-State"
        ]
        
        # Merge canonical with any clean custom states (length <= 30 and no digit prefixes)
        extra_states = [s for s in raw_states if len(s) <= 30 and not s[0].isdigit() and s not in canonical_states and not s.startswith("&")]
        states = sorted(canonical_states + extra_states)


        sector_rows = conn.execute(sqlalchemy.text("""
            SELECT DISTINCT sector 
            FROM projects 
            WHERE sector IS NOT NULL AND sector != '' 
            ORDER BY sector ASC
        """)).fetchall()
        sectors = [r[0] for r in sector_rows]

    ministries = [
        "Ministry of Railways",
        "Ministry of Road Transport and Highways",
        "Ministry of Petroleum and Natural Gas",
        "Ministry of Power",
        "Ministry of Coal & Mines",
        "Ministry of Civil Aviation",
        "Ministry of Ports, Shipping and Waterways",
        "Ministry of Communications",
        "Ministry of Housing and Urban Affairs",
        "Ministry of Heavy Industries & Steel"
    ]

    return {
        "agencies": agencies,
        "states": states,
        "sectors": sectors,
        "ministries": ministries,
        "risk_categories": ["Critical", "High", "Moderate", "Low"]
    }

