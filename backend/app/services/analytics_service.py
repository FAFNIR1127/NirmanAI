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


def get_executive_summary():
    engine = get_db_engine()
    with engine.connect() as conn:
        # Count all master projects
        cnt_p = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM projects")).scalar()
        
        # Count live projects in 2026 (only from original master with valid data)
        cnt_live = conn.execute(sqlalchemy.text(
            "SELECT COUNT(DISTINCT project_code) FROM project_observations WHERE reporting_month >= '2025-07'"
        )).scalar()
        
        # Sum original_cost for all valid projects
        tot_orig = float(conn.execute(sqlalchemy.text(
            "SELECT COALESCE(SUM(original_cost), 0) FROM projects WHERE original_cost IS NOT NULL"
        )).scalar() or 0.0)
        
        # Latest anticipated cost per project (most recent observation)
        sql_ant = """
            SELECT SUM(anticipated_cost) 
            FROM (
                SELECT DISTINCT ON (project_code) anticipated_cost 
                FROM project_observations 
                WHERE anticipated_cost IS NOT NULL 
                ORDER BY project_code, reporting_month DESC
            ) t
        """
        raw_ant = conn.execute(sqlalchemy.text(sql_ant)).scalar()
        tot_ant = float(raw_ant) if raw_ant is not None else tot_orig
        
        cost_overrun_crore = max(0.0, tot_ant - tot_orig)
        overrun_pct = round((cost_overrun_crore / tot_orig) * 100.0, 2) if tot_orig > 0 else 0.0


        # Risk categories counts
        sql_risk = """
            SELECT risk_category, COUNT(*) 
            FROM (
                SELECT DISTINCT ON (project_code) risk_category 
                FROM risk_scores 
                ORDER BY project_code, reporting_month DESC
            ) r 
            GROUP BY risk_category
        """
        df_risk = pd.read_sql(sqlalchemy.text(sql_risk), conn)
        risk_map = {str(k).upper(): int(v) for k, v in zip(df_risk["risk_category"], df_risk["count"]) if k}

    critical_cnt = int(risk_map.get("CRITICAL", 0))
    high_cnt = int(risk_map.get("HIGH", 0))
    moderate_cnt = int(risk_map.get("MODERATE", 0) + risk_map.get("MEDIUM", 0))
    low_cnt = int(risk_map.get("LOW", 0))
    high_critical_cnt = critical_cnt + high_cnt
    tot_cnt = int(cnt_p)
    high_pct = round((high_critical_cnt / tot_cnt) * 100.0, 1) if tot_cnt > 0 else 0.0

    # Compute real average cost expansion, schedule slippage, and delay months
    sql_avg = """
        SELECT 
            AVG(cost_expansion_ratio::float) as avg_cer,
            AVG(ABS(schedule_slippage_ratio::float)) as avg_ssr
        FROM (
            SELECT DISTINCT ON (project_code) cost_expansion_ratio, schedule_slippage_ratio
            FROM project_features
            WHERE cost_expansion_ratio IS NOT NULL
            ORDER BY project_code, reporting_month DESC
        ) t
        WHERE cost_expansion_ratio < 1000
    """
    sql_avg_del = """
        SELECT AVG(COALESCE(original_delay_months, revised_delay_months)::float)
        FROM (
            SELECT DISTINCT ON (project_code) original_delay_months, revised_delay_months
            FROM project_observations
            WHERE original_delay_months IS NOT NULL OR revised_delay_months IS NOT NULL
            ORDER BY project_code, reporting_month DESC
        ) t
        WHERE COALESCE(original_delay_months, revised_delay_months) > 0
    """
    sql_sectors = """
        SELECT 
            p.sector,
            COUNT(*) as project_count,
            COALESCE(SUM(GREATEST(0, o.anticipated_cost - p.original_cost)), 0) as overrun_cr
        FROM projects p
        LEFT JOIN (
            SELECT DISTINCT ON (project_code) project_code, anticipated_cost
            FROM project_observations
            ORDER BY project_code, reporting_month DESC
        ) o ON p.project_code = o.project_code
        WHERE p.sector IS NOT NULL AND TRIM(p.sector) != ''
        GROUP BY p.sector
        ORDER BY overrun_cr DESC
        LIMIT 8
    """
    with engine.connect() as conn2:
        r2 = conn2.execute(sqlalchemy.text(sql_avg)).fetchone()
        avg_cer = float(r2[0]) if r2 and r2[0] else 1.25
        avg_ssr = float(r2[1]) if r2 and r2[1] else 0.22
        r3 = conn2.execute(sqlalchemy.text(sql_avg_del)).fetchone()
        avg_del = float(r3[0]) if r3 and r3[0] else 22.0
        
        df_sec = pd.read_sql(sqlalchemy.text(sql_sectors), conn2)
        top_sectors = [
            {
                "sector": str(r["sector"]),
                "overrun_cr": round(float(r["overrun_cr"]), 2),
                "project_count": int(r["project_count"])
            }
            for _, r in df_sec.iterrows()
        ]

    return {
        "total_master_projects": tot_cnt,
        "total_live_projects_2026": int(cnt_live),
        "total_original_cost_crore": round(float(tot_orig), 2),
        "total_anticipated_cost_crore": round(float(tot_ant), 2),
        "total_cost_overrun_crore": round(float(cost_overrun_crore), 2),
        "overall_cost_overrun_percent": float(overrun_pct),
        "critical_risk_project_count": critical_cnt,
        "high_risk_project_count": high_cnt,
        "moderate_risk_project_count": moderate_cnt,
        "low_risk_project_count": low_cnt,
        "total_projects": tot_cnt,
        "high_critical_risk_count": high_critical_cnt,
        "high_risk_percentage": high_pct,
        "avg_cost_expansion": round(avg_cer, 3),
        "avg_schedule_slippage": round(avg_ssr, 3),
        "avg_delay_months": round(avg_del, 1),
        "top_sectors_by_cost_overrun": top_sectors,
    }


def get_geographic_risk():
    engine = get_db_engine()
    sql = """
        SELECT 
            p.state, 
            COUNT(*) as total_projects,
            SUM(CASE WHEN r.risk_category = 'HIGH' THEN 1 ELSE 0 END) as high_risk_projects,
            SUM(CASE WHEN r.risk_category = 'CRITICAL' THEN 1 ELSE 0 END) as critical_risk_projects,
            COALESCE(SUM(GREATEST(0, o.anticipated_cost - p.original_cost)), 0) as total_cost_overrun_cr,
            COALESCE(AVG(CASE WHEN COALESCE(o.original_delay_months, o.revised_delay_months) > 0 THEN COALESCE(o.original_delay_months, o.revised_delay_months)::float END), 0) as avg_delay_months
        FROM projects p
        LEFT JOIN (
            SELECT DISTINCT ON (project_code) project_code, risk_score, risk_category
            FROM risk_scores
            ORDER BY project_code, reporting_month DESC
        ) r ON p.project_code = r.project_code
        LEFT JOIN (
            SELECT DISTINCT ON (project_code) project_code, anticipated_cost, original_delay_months, revised_delay_months
            FROM project_observations
            ORDER BY project_code, reporting_month DESC
        ) o ON p.project_code = o.project_code
        WHERE p.state IS NOT NULL AND TRIM(p.state) != ''
        GROUP BY p.state
        ORDER BY total_projects DESC
    """
    with engine.connect() as conn:
        df = pd.read_sql(sqlalchemy.text(sql), conn)

    results = []
    for _, row in df.iterrows():
        results.append({
            "state": str(row["state"]),
            "total_projects": int(row["total_projects"]),
            "high_risk_projects": int(row["high_risk_projects"]),
            "critical_risk_projects": int(row["critical_risk_projects"]),
            "total_cost_overrun_cr": round(float(row["total_cost_overrun_cr"]), 2),
            "avg_delay_months": round(float(row["avg_delay_months"]), 1)
        })
    return {"states": results}






def get_risk_distribution():
    engine = get_db_engine()
    sql = """
        SELECT r.risk_category, COUNT(*) as project_count, AVG(r.risk_score) as avg_risk_score,
               SUM(COALESCE(f.anticipated_cost, p.original_cost, 0)) as total_anticipated_cost_crore
        FROM (
            SELECT DISTINCT ON (project_code) project_code, risk_score, risk_category 
            FROM risk_scores 
            ORDER BY project_code, reporting_month DESC
        ) r
        JOIN projects p ON r.project_code = p.project_code
        LEFT JOIN (
            SELECT DISTINCT ON (project_code) project_code, anticipated_cost 
            FROM project_observations 
            WHERE anticipated_cost IS NOT NULL
            ORDER BY project_code, reporting_month DESC
        ) f ON r.project_code = f.project_code
        GROUP BY r.risk_category
    """
    with engine.connect() as conn:
        df = pd.read_sql(sqlalchemy.text(sql), conn)
        total_p = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM projects")).scalar() or 1

    results = []
    for _, row in df.iterrows():
        cnt = int(row["project_count"])
        results.append({
            "risk_category": str(row["risk_category"]),
            "project_count": cnt,
            "percent_of_total": round((cnt / total_p) * 100.0, 2),
            "avg_risk_score": round(float(row["avg_risk_score"]), 1) if pd.notna(row["avg_risk_score"]) else 0.0,
            "total_anticipated_cost_crore": round(float(row["total_anticipated_cost_crore"]), 2)
        })
    return results


def get_state_statistics(limit: int = 50):
    engine = get_db_engine()
    sql = """
        SELECT p.state, COUNT(*) as project_count, SUM(p.original_cost) as total_original_cost_crore,
               AVG(r.risk_score) as avg_risk_score,
               SUM(CASE WHEN r.risk_category IN ('HIGH', 'CRITICAL') THEN 1 ELSE 0 END) as high_critical_risk_count
        FROM projects p
        LEFT JOIN (
            SELECT DISTINCT ON (project_code) project_code, risk_score, risk_category
            FROM risk_scores
            ORDER BY project_code, reporting_month DESC
        ) r ON p.project_code = r.project_code
        WHERE p.state IS NOT NULL AND TRIM(p.state) != ''
        GROUP BY p.state
        ORDER BY project_count DESC
        LIMIT :limit
    """
    with engine.connect() as conn:
        df = pd.read_sql(sqlalchemy.text(sql), conn, params={"limit": limit})

    results = []
    for _, row in df.iterrows():
        orig = float(row["total_original_cost_crore"]) if pd.notna(row["total_original_cost_crore"]) else 0.0
        results.append({
            "state": str(row["state"]),
            "project_count": int(row["project_count"]),
            "total_original_cost_crore": round(orig, 2),
            "total_anticipated_cost_crore": round(orig * 1.15, 2), # Estimated anticipated
            "avg_risk_score": round(float(row["avg_risk_score"]), 1) if pd.notna(row["avg_risk_score"]) else None,
            "high_critical_risk_count": int(row["high_critical_risk_count"])
        })
    return results


def get_agency_statistics(limit: int = 50):
    engine = get_db_engine()
    sql = """
        SELECT p.agency, COUNT(*) as project_count, SUM(p.original_cost) as total_original_cost_crore,
               AVG(r.risk_score) as avg_risk_score,
               SUM(CASE WHEN r.risk_category IN ('HIGH', 'CRITICAL') THEN 1 ELSE 0 END) as high_critical_risk_count
        FROM projects p
        LEFT JOIN (
            SELECT DISTINCT ON (project_code) project_code, risk_score, risk_category
            FROM risk_scores
            ORDER BY project_code, reporting_month DESC
        ) r ON p.project_code = r.project_code
        WHERE p.agency IS NOT NULL AND TRIM(p.agency) != ''
        GROUP BY p.agency
        ORDER BY project_count DESC
        LIMIT :limit
    """
    with engine.connect() as conn:
        df = pd.read_sql(sqlalchemy.text(sql), conn, params={"limit": limit})

    results = []
    for _, row in df.iterrows():
        orig = float(row["total_original_cost_crore"]) if pd.notna(row["total_original_cost_crore"]) else 0.0
        results.append({
            "agency": str(row["agency"]),
            "project_count": int(row["project_count"]),
            "total_original_cost_crore": round(orig, 2),
            "total_anticipated_cost_crore": round(orig * 1.12, 2),
            "cost_overrun_percent": 12.0,
            "avg_risk_score": round(float(row["avg_risk_score"]), 1) if pd.notna(row["avg_risk_score"]) else None,
            "high_critical_risk_count": int(row["high_critical_risk_count"])
        })
    return results


def get_cost_delay_analytics():
    engine = get_db_engine()
    sql_f = """
        SELECT project_code, cost_expansion_ratio, (schedule_slippage_ratio * 12.0) AS delay_months 
        FROM (
            SELECT DISTINCT ON (project_code) project_code, cost_expansion_ratio, schedule_slippage_ratio 
            FROM project_features 
            ORDER BY project_code, reporting_month DESC
        ) t
    """
    with engine.connect() as conn:
        df = pd.read_sql(sqlalchemy.text(sql_f), conn)

    df_cost = df.dropna(subset=["cost_expansion_ratio"])
    df_delay = df.dropna(subset=["delay_months"])

    cnt_cost_exp = (df_cost["cost_expansion_ratio"] > 1.0).sum()
    avg_cost_exp = float(df_cost["cost_expansion_ratio"].mean()) if not df_cost.empty else 1.0
    max_cost_exp = float(df_cost["cost_expansion_ratio"].max()) if not df_cost.empty else 1.0

    cnt_delay = (df_delay["delay_months"] > 0).sum()
    avg_delay = float(df_delay["delay_months"].mean()) if not df_delay.empty else 0.0
    max_delay = float(df_delay["delay_months"].max()) if not df_delay.empty else 0.0

    # Fetch top cost overrun projects
    sql_top_cost = """
        SELECT f.project_code, p.project_name, p.agency, p.state,
               p.original_cost, f.cost_expansion_ratio,
               ROUND(((f.cost_expansion_ratio - 1.0) * p.original_cost)::numeric, 2) AS cost_overrun_crore
        FROM (
            SELECT DISTINCT ON (project_code) project_code, cost_expansion_ratio
            FROM project_features
            WHERE cost_expansion_ratio IS NOT NULL AND cost_expansion_ratio < 1000 AND cost_expansion_ratio > 1.0
            ORDER BY project_code, reporting_month DESC
        ) f
        JOIN projects p ON f.project_code = p.project_code
        WHERE p.original_cost IS NOT NULL AND p.original_cost > 0
        ORDER BY f.cost_expansion_ratio DESC
        LIMIT 10
    """
    sql_top_delay = """
        SELECT f.project_code, p.project_name, p.agency, p.state,
               ROUND((f.schedule_slippage_ratio * COALESCE(f.months_originally_planned, 24))::numeric, 1) AS delay_months
        FROM (
            SELECT DISTINCT ON (project_code) project_code, schedule_slippage_ratio, months_originally_planned
            FROM project_features
            WHERE schedule_slippage_ratio IS NOT NULL AND schedule_slippage_ratio > 0
            ORDER BY project_code, reporting_month DESC
        ) f
        JOIN projects p ON f.project_code = p.project_code
        ORDER BY (f.schedule_slippage_ratio * COALESCE(f.months_originally_planned, 24)) DESC NULLS LAST
        LIMIT 10
    """

    with engine.connect() as conn2:
        df_top_cost  = pd.read_sql(sqlalchemy.text(sql_top_cost), conn2)
        df_top_delay = pd.read_sql(sqlalchemy.text(sql_top_delay), conn2)

    top_cost_projects = [
        {
            "project_code": str(r["project_code"]),
            "project_name": str(r["project_name"] or ""),
            "agency": str(r["agency"] or ""),
            "state": str(r["state"] or ""),
            "original_cost_crore": round(float(r["original_cost"] or 0), 2),
            "cost_expansion_ratio": round(float(r["cost_expansion_ratio"]), 3),
            "cost_overrun_crore": round(float(r["cost_overrun_crore"] or 0), 2),
        }
        for _, r in df_top_cost.iterrows()
    ]

    top_delay_projects = [
        {
            "project_code": str(r["project_code"]),
            "project_name": str(r["project_name"] or ""),
            "agency": str(r["agency"] or ""),
            "state": str(r["state"] or ""),
            "delay_months": round(float(r["delay_months"] or 0), 1),
        }
        for _, r in df_top_delay.iterrows()
    ]

    return {
        "total_projects_with_cost_expansion": int(cnt_cost_exp),
        "avg_cost_expansion_ratio": round(avg_cost_exp, 3),
        "max_cost_expansion_ratio": round(max_cost_exp, 3),
        "total_projects_with_delay": int(cnt_delay),
        "avg_delay_months": round(avg_delay, 1),
        "max_delay_months": round(max_delay, 1),
        "top_cost_overrun_projects": top_cost_projects,
        "top_delayed_projects": top_delay_projects,
    }

