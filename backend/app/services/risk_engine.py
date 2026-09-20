import json
import sqlalchemy
import pandas as pd
import joblib
from backend.app.config import MODEL_VERSION_DIR, DATABASE_URL, FALLBACK_SQLITE_PATH


class RiskEngineService:
    def __init__(self):
        self.calibrator_path = MODEL_VERSION_DIR / "calibrator.pkl"
        self.xgb_path = MODEL_VERSION_DIR / "xgboost_model.joblib"
        self.meta_path = MODEL_VERSION_DIR / "model_metadata.json"
        
        self.calibrated_model = joblib.load(self.calibrator_path) if self.calibrator_path.exists() else None
        self.xgb_model = joblib.load(self.xgb_path) if self.xgb_path.exists() else None
        
        with open(self.meta_path, "r") as f:
            self.metadata = json.load(f)
            
        self.operational_threshold = self.metadata.get("operational_threshold", 0.28)

    def get_db_engine(self):
        try:
            engine = sqlalchemy.create_engine(DATABASE_URL)
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("SELECT 1"))
            return engine
        except Exception:
            return sqlalchemy.create_engine(f"sqlite:///{FALLBACK_SQLITE_PATH}")

    def get_project_risk_assessment(self, project_code: str):
        engine = self.get_db_engine()
        with engine.connect() as conn:
            try:
                alias_res = conn.execute(sqlalchemy.text("SELECT canonical_code FROM project_aliases WHERE alias_code = :c"), {"c": project_code}).fetchone()
                if alias_res and alias_res[0]:
                    project_code = str(alias_res[0])
            except Exception:
                pass

            query = """
                SELECT r.*, p.project_name, p.agency, p.state
                FROM risk_scores r
                JOIN projects p ON r.project_code = p.project_code
                WHERE r.project_code = :code
                ORDER BY r.reporting_month DESC
                LIMIT 1
            """
            df = pd.read_sql(sqlalchemy.text(query), conn, params={"code": project_code})
            
        if df.empty:
            return None

        row = df.iloc[0]
        
        prob = float(row["predicted_severe_risk_prob"])
        score = float(row["risk_score"])
        category = str(row["risk_category"])
        
        drivers_raw = row.get("key_risk_drivers")
        protective_raw = row.get("protective_factors")
        
        drivers = json.loads(drivers_raw) if isinstance(drivers_raw, str) else (drivers_raw if isinstance(drivers_raw, list) else [])
        protective = json.loads(protective_raw) if isinstance(protective_raw, str) else (protective_raw if isinstance(protective_raw, list) else [])

        return {
            "project_code": str(row["project_code"]),
            "project_name": str(row.get("project_name", "")),
            "agency": str(row.get("agency", "")),
            "state": str(row.get("state", "")),
            "reporting_month": str(row["reporting_month"]),
            "predicted_severe_risk_prob": prob,
            "risk_score": score,
            "risk_category": category,
            "early_warning": prob >= self.operational_threshold,
            "cost_risk_index": float(row["cost_risk_index"]),
            "schedule_risk_index": float(row["schedule_risk_index"]),
            "risk_drivers": drivers,
            "protective_factors": protective,
            "model_version": self.metadata.get("model_version", "risk_engine_v1")
        }


risk_engine_service = RiskEngineService()
