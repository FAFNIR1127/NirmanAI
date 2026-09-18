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
        # Fallback to SQLite if PostgreSQL connection fails
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


def list_projects_summary(limit: int = 100):
    engine = get_db_engine()
    query = """
        SELECT p.project_code, p.project_name, p.project_name as name, p.agency, p.state, p.sector, p.approval_date, p.original_cost,
               r.risk_score, r.risk_category, r.reporting_month,
               o.anticipated_cost,
               COALESCE(o.original_delay_months, o.revised_delay_months, 0) as delay_months,
               o.physical_progress
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
        ORDER BY r.risk_score DESC NULLS LAST
        LIMIT :limit
    """
    with engine.connect() as conn:
        df = pd.read_sql(sqlalchemy.text(query), conn, params={"limit": limit})
    return clean_records(df.to_dict(orient="records"))



def get_project_details(project_code: str):
    engine = get_db_engine()
    query_p = "SELECT * FROM projects WHERE project_code = :code"
    query_o = "SELECT * FROM project_observations WHERE project_code = :code ORDER BY reporting_month ASC"
    
    with engine.connect() as conn:
        df_p = pd.read_sql(sqlalchemy.text(query_p), conn, params={"code": project_code})
        df_o = pd.read_sql(sqlalchemy.text(query_o), conn, params={"code": project_code})
        
    if df_p.empty:
        return None
    
    p_row = df_p.iloc[0]
    
    latest_ant_cost = None
    latest_delay_months = None
    latest_progress = None
    latest_orig_doc = None
    latest_ant_doc = None
    if not df_o.empty:
        valid_ant = df_o["anticipated_cost"].dropna()
        if not valid_ant.empty:
            latest_ant_cost = float(valid_ant.iloc[-1])
        last_obs = df_o.iloc[-1]
        if pd.notna(last_obs.get("original_delay_months")):
            latest_delay_months = float(last_obs["original_delay_months"])
        elif pd.notna(last_obs.get("revised_delay_months")):
            latest_delay_months = float(last_obs["revised_delay_months"])
        if pd.notna(last_obs.get("physical_progress")):
            latest_progress = float(last_obs["physical_progress"])
        if pd.notna(last_obs.get("original_doc")):
            latest_orig_doc = str(last_obs["original_doc"])
        if pd.notna(last_obs.get("anticipated_doc")):
            latest_ant_doc = str(last_obs["anticipated_doc"])

    obs_list = []
    for _, o_row in df_o.iterrows():
        del_m = None
        if pd.notna(o_row.get("original_delay_months")):
            del_m = float(o_row["original_delay_months"])
        elif pd.notna(o_row.get("revised_delay_months")):
            del_m = float(o_row["revised_delay_months"])

        obs_list.append({
            "reporting_month": str(o_row.get("reporting_month", "")),
            "revised_cost": float(o_row["revised_cost"]) if pd.notna(o_row.get("revised_cost")) else None,
            "anticipated_cost": float(o_row["anticipated_cost"]) if pd.notna(o_row.get("anticipated_cost")) else None,
            "cumulative_expenditure": float(o_row["cumulative_expenditure"]) if pd.notna(o_row.get("cumulative_expenditure")) else None,
            "physical_progress": float(o_row["physical_progress"]) if pd.notna(o_row.get("physical_progress")) else None,
            "original_doc": str(o_row["original_doc"]) if pd.notna(o_row.get("original_doc")) else None,
            "anticipated_doc": str(o_row["anticipated_doc"]) if pd.notna(o_row.get("anticipated_doc")) else None,
            "delay_months": del_m,
        })
    
    p_name = str(p_row["project_name"]) if pd.notna(p_row.get("project_name")) else None
    return {
        "project_code": str(p_row["project_code"]),
        "project_name": p_name,
        "name": p_name,
        "agency": str(p_row["agency"]) if pd.notna(p_row.get("agency")) else None,
        "state": str(p_row["state"]) if pd.notna(p_row.get("state")) else None,
        "sector": str(p_row["sector"]) if pd.notna(p_row.get("sector")) else None,
        "approval_date": str(p_row["approval_date"]) if pd.notna(p_row.get("approval_date")) else None,
        "original_cost": float(p_row["original_cost"]) if pd.notna(p_row.get("original_cost")) else None,
        "latest_anticipated_cost": latest_ant_cost,
        "latest_delay_months": latest_delay_months,
        "latest_physical_progress": latest_progress,
        "latest_original_doc": latest_orig_doc,
        "latest_anticipated_doc": latest_ant_doc,
        "observations": obs_list
    }


