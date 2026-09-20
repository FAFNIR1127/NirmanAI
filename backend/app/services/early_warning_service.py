import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, List

from backend.app.config import DATABASE_URL
from backend.app.services.risk_trajectory_service import RiskTrajectoryService


class EarlyWarningPrioritizationService:
    """Prioritizes monitored projects requiring urgent intervention, separating raw risk score from urgency rationale."""

    def __init__(self):
        self.trajectory_service = RiskTrajectoryService()

    def _get_connection(self):
        return psycopg2.connect(DATABASE_URL)

    def get_early_warning_projects(
        self,
        limit: int = 60,
        sector: str = None,
        risk_category: str = None,
        search: str = None
    ) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                where_clauses = ["(r.predicted_severe_risk_prob >= 0.25 OR r.risk_score >= 25.0)"]
                params = []

                if sector and sector.strip():
                    where_clauses.append("(p.sector ILIKE %s OR p.sector ILIKE %s)")
                    params.extend([sector.strip(), f"%{sector.strip()}%"])

                if risk_category and risk_category.strip() and risk_category.upper() != 'ALL':
                    where_clauses.append("UPPER(r.risk_category) = %s")
                    params.append(risk_category.strip().upper())

                if search and search.strip():
                    where_clauses.append("(p.project_name ILIKE %s OR p.project_code ILIKE %s OR p.agency ILIKE %s)")
                    params.extend([f"%{search.strip()}%", f"%{search.strip()}%", f"%{search.strip()}%"])

                where_sql = " AND ".join(where_clauses)
                params.append(limit)

                query = f"""
                    SELECT r.project_code, r.risk_score, r.risk_category, r.predicted_severe_risk_prob,
                           r.cost_risk_index, r.schedule_risk_index, r.reporting_month,
                           p.project_name, p.agency, p.state, p.sector, p.original_cost,
                           o.anticipated_cost,
                           COALESCE(o.original_delay_months, o.revised_delay_months, 0) as delay_months,
                           GREATEST(0, COALESCE(o.anticipated_cost, p.original_cost, 0) - COALESCE(p.original_cost, 0)) as cost_overrun_cr
                    FROM (
                        SELECT DISTINCT ON (project_code) project_code, risk_score, risk_category,
                               predicted_severe_risk_prob, cost_risk_index, schedule_risk_index, reporting_month
                        FROM risk_scores
                        ORDER BY project_code, reporting_month DESC
                    ) r
                    JOIN projects p ON r.project_code = p.project_code
                    LEFT JOIN (
                        SELECT DISTINCT ON (project_code) project_code, anticipated_cost, original_delay_months, revised_delay_months
                        FROM project_observations
                        ORDER BY project_code, reporting_month DESC
                    ) o ON p.project_code = o.project_code
                    WHERE {where_sql}
                    ORDER BY r.risk_score DESC, cost_overrun_cr DESC
                    LIMIT %s;
                """
                cur.execute(query, tuple(params))
                rows = cur.fetchall()

        finally:
            conn.close()

        prioritized = []
        for rank, r in enumerate(rows, start=1):
            p_code = r["project_code"]
            traj = self.trajectory_service.get_project_risk_trajectory(p_code)
            trend = traj.get("trend", "STABLE") if traj else "STABLE"

            # Construct explainable urgency rationale
            raw_category = (r["risk_category"] or "High").capitalize()
            urgency_factors = []
            if r["risk_score"] >= 40.0:
                urgency_factors.append(f"Critical risk score ({r['risk_score']:.1f}/100)")
            elif r["risk_score"] >= 25.0:
                urgency_factors.append(f"Moderate-to-high risk score ({r['risk_score']:.1f}/100)")

            if trend == "DETERIORATING":
                urgency_factors.append("Deteriorating 6-period risk trajectory")
            elif trend == "VOLATILE":
                urgency_factors.append("Volatile historical risk score variance")

            if r["cost_risk_index"] > 1.2:
                urgency_factors.append("High cost risk index")
            if r["schedule_risk_index"] > 1.2:
                urgency_factors.append("High schedule delay index")

            urgency_reason = " | ".join(urgency_factors) if urgency_factors else "Exceeds operational monitoring threshold."

            prioritized.append({
                "urgency_rank": rank,
                "project_code": p_code,
                "project_name": r["project_name"],
                "agency": r["agency"],
                "state": r["state"],
                "risk_score": float(r["risk_score"]),
                "risk_category": raw_category,
                "predicted_prob": float(r["predicted_severe_risk_prob"]),
                "trajectory_trend": trend,
                "early_warning": True,
                "cost_warning": r["cost_risk_index"] > 1.0,
                "schedule_warning": r["schedule_risk_index"] > 1.0,
                "cost_overrun_cr": round(float(r["cost_overrun_cr"] or 0), 2),
                "delay_months": round(float(r["delay_months"] or 0), 1),
                "sector": r.get("sector") or "Infrastructure",
                "urgency_reason": urgency_reason,
                "reporting_month": r["reporting_month"]
            })

        return prioritized

