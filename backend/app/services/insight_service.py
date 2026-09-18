"""
backend/app/services/insight_service.py

Phase 13 — Proactive Insight & Surveillance Service.
Generates proactive morning surveillance snapshots, state risk digests, and early warning triggers.
"""

from typing import Dict, Any, List
import pandas as pd
import sqlalchemy

from backend.app.services.analytics_service import get_db_engine, get_executive_summary


class InsightService:
    """Provides proactive morning surveillance snapshots and regional risk digests."""

    @staticmethod
    def get_morning_surveillance() -> Dict[str, Any]:
        """Generate proactive morning surveillance snapshot across portfolio."""
        engine = get_db_engine()
        with engine.connect() as conn:
            # Newly escalated Critical projects
            query_crit = """
                SELECT p.project_code, p.project_name, p.state, p.sector, r.risk_score, r.risk_category
                FROM projects p
                JOIN (
                    SELECT DISTINCT ON (project_code) project_code, risk_score, risk_category
                    FROM risk_scores
                    ORDER BY project_code, reporting_month DESC
                ) r ON p.project_code = r.project_code
                WHERE r.risk_category = 'CRITICAL'
                ORDER BY r.risk_score DESC
                LIMIT 5
            """
            df_crit = pd.read_sql(sqlalchemy.text(query_crit), conn)
            crit_projects = df_crit.to_dict(orient="records")

            # High cost overrun projects
            query_cost = """
                SELECT p.project_code, p.project_name, p.original_cost, o.anticipated_cost, (o.anticipated_cost - p.original_cost) as cost_overrun
                FROM projects p
                JOIN (
                    SELECT DISTINCT ON (project_code) project_code, anticipated_cost
                    FROM project_observations
                    WHERE anticipated_cost IS NOT NULL
                    ORDER BY project_code, reporting_month DESC
                ) o ON p.project_code = o.project_code
                WHERE (o.anticipated_cost - p.original_cost) > 500
                ORDER BY cost_overrun DESC
                LIMIT 5
            """
            df_cost = pd.read_sql(sqlalchemy.text(query_cost), conn)
            cost_projects = df_cost.to_dict(orient="records")

        exec_kpis = get_executive_summary()
        top_sectors = exec_kpis.get("top_sectors_by_cost_overrun", [])
        top_sector_name = top_sectors[0]["sector"] if top_sectors else "infrastructure"

        return {
            "title": "Morning Infrastructure Surveillance Snapshot",
            "date": pd.Timestamp.now().strftime("%Y-%m-%d"),
            "portfolio_summary": {
                "total_projects": exec_kpis.get("total_projects", exec_kpis.get("total_master_projects", 0)),
                "live_projects_2026": exec_kpis.get("total_live_projects_2026", 0),
                "critical_projects": exec_kpis.get("critical_risk_project_count", 0),
                "high_projects": exec_kpis.get("high_risk_project_count", 0),
                "moderate_projects": exec_kpis.get("moderate_risk_project_count", 0),
                "low_projects": exec_kpis.get("low_risk_project_count", 0),
                "total_original_cost_crore": exec_kpis.get("total_original_cost_crore", 0.0),
                "total_anticipated_cost_crore": exec_kpis.get("total_anticipated_cost_crore", 0.0),
                "total_cost_overrun_crore": exec_kpis.get("total_cost_overrun_crore", 0.0),
                "overall_cost_overrun_percent": exec_kpis.get("overall_cost_overrun_percent", 0.0),
                "avg_delay_months": exec_kpis.get("avg_delay_months", 0.0),
            },
            "top_critical_escalations": crit_projects,
            "top_cost_overruns": cost_projects,
            "top_sectors_by_exposure": top_sectors[:5],
            "recommended_actions": [
                f"Review critical risk projects in {top_sector_name} — highest national cost exposure.",
                "Initiate ground evidence verification for top cost overrun projects listed above.",
                f"Issue early warning advisory to all {exec_kpis.get('critical_risk_project_count', 0):,} Critical and {exec_kpis.get('high_risk_project_count', 0):,} High risk project authorities.",
                f"Monitor {exec_kpis.get('total_live_projects_2026', 0):,} active 2026 projects for schedule adherence."
            ]
        }

    @staticmethod
    def get_state_digest(state_name: str) -> Dict[str, Any]:
        """Generate state-level project risk and concentration digest."""
        engine = get_db_engine()
        with engine.connect() as conn:
            query = """
                SELECT p.project_code, p.project_name, p.sector, p.agency, p.original_cost, r.risk_score, r.risk_category
                FROM projects p
                LEFT JOIN (
                    SELECT DISTINCT ON (project_code) project_code, risk_score, risk_category
                    FROM risk_scores
                    ORDER BY project_code, reporting_month DESC
                ) r ON p.project_code = r.project_code
                WHERE LOWER(p.state) = LOWER(:state)
                ORDER BY r.risk_score DESC NULLS LAST
            """
            df = pd.read_sql(sqlalchemy.text(query), conn, params={"state": state_name})
            records = df.to_dict(orient="records")

        total_cnt = len(records)
        crit_cnt = sum(1 for r in records if r.get("risk_category") == "CRITICAL")
        high_cnt = sum(1 for r in records if r.get("risk_category") == "HIGH")
        tot_cost = sum(float(r.get("original_cost")) for r in records if r.get("original_cost") is not None and pd.notna(r.get("original_cost")))

        return {
            "state": state_name.title(),
            "total_projects": total_cnt,
            "critical_count": crit_cnt,
            "high_count": high_cnt,
            "total_outlay_crore": round(tot_cost, 2),
            "top_risk_projects": records[:5]
        }
