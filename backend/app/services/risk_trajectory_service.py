import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, List, Optional

from backend.app.config import DATABASE_URL


class RiskTrajectoryService:
    """Computes model-versioned historical risk trajectories and deterministic mathematical trend classifications."""

    def _get_connection(self):
        return psycopg2.connect(DATABASE_URL)

    def get_project_risk_trajectory(self, project_code: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT reporting_month, risk_score, risk_category, predicted_severe_risk_prob,
                           cost_risk_index, schedule_risk_index
                    FROM risk_scores
                    WHERE project_code = %s
                    ORDER BY reporting_month ASC;
                """, (project_code,))
                rows = cur.fetchall()
        finally:
            conn.close()

        if not rows:
            return None

        trajectory = []
        for r in rows:
            trajectory.append({
                "reporting_month": r["reporting_month"],
                "risk_score": float(r["risk_score"]),
                "risk_category": str(r["risk_category"]),
                "predicted_prob": float(r["predicted_severe_risk_prob"]),
                "cost_risk_index": float(r["cost_risk_index"]),
                "schedule_risk_index": float(r["schedule_risk_index"])
            })

        n_obs = len(trajectory)
        
        # Sparse History Handling Guard (< 3 periods)
        if n_obs < 3:
            return {
                "project_code": project_code,
                "model_version": "risk_engine_v1",
                "total_observations": n_obs,
                "trajectory": trajectory,
                "trend": "INSUFFICIENT_HISTORY",
                "trend_slope": 0.0,
                "trend_variance": 0.0,
                "trend_description": f"Fewer than 3 historical reporting periods available ({n_obs} observation(s)). Insufficient history for trajectory slope computation."
            }

        # Mathematical Trend Classification over recent 6 reporting periods
        recent_obs = trajectory[-6:]
        scores = np.array([obs["risk_score"] for obs in recent_obs], dtype=np.float64)
        time_idx = np.arange(len(scores), dtype=np.float64)

        # Calculate slope m and variance
        if len(scores) > 1:
            slope, _ = np.polyfit(time_idx, scores, 1)
            variance = float(np.var(scores))
        else:
            slope = 0.0
            variance = 0.0

        slope = float(slope)

        # Classification rules: slope > 1.5 -> DETERIORATING, slope < -1.5 -> IMPROVING, var > 25 -> VOLATILE, else STABLE
        if variance > 25.0:
            trend = "VOLATILE"
            desc = f"Volatile trajectory with high score variance ({variance:.1f})."
        elif slope > 1.5:
            trend = "DETERIORATING"
            desc = f"Deteriorating trajectory with positive slope (+{slope:.2f} score points/month)."
        elif slope < -1.5:
            trend = "IMPROVING"
            desc = f"Improving trajectory with negative slope ({slope:.2f} score points/month)."
        else:
            trend = "STABLE"
            desc = f"Stable trajectory with minimal slope ({slope:.2f} points/month)."

        return {
            "project_code": project_code,
            "model_version": "risk_engine_v1",
            "total_observations": n_obs,
            "trajectory": trajectory,
            "trend": trend,
            "trend_slope": round(slope, 2),
            "trend_variance": round(variance, 2),
            "trend_description": desc
        }
