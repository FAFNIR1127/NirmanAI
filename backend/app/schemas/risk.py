from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class RiskDriverItem(BaseModel):
    feature_name: str
    feature_code: str
    points_added: str
    value: Optional[float] = None


class ProtectiveFactorItem(BaseModel):
    feature_name: str
    feature_code: str
    points_reduced: str
    value: Optional[float] = None


class RiskPredictionResponse(BaseModel):
    project_code: str
    project_name: Optional[str] = None
    agency: Optional[str] = None
    state: Optional[str] = None
    reporting_month: str
    predicted_severe_risk_prob: float
    risk_score: float
    risk_category: str
    early_warning: bool
    cost_risk_index: float
    schedule_risk_index: float
    risk_drivers: List[RiskDriverItem] = []
    protective_factors: List[ProtectiveFactorItem] = []
    model_version: str = "risk_engine_v1"
