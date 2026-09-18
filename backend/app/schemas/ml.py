"""
ml.py - Pydantic Schemas for Machine Learning Prediction & Governance APIs
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator


class RiskDriver(BaseModel):
    feature: str
    attribution: float = Field(..., description="SHAP feature attribution value")
    description: str = Field(..., description="Human-readable impact description")


class MLPredictionRequest(BaseModel):
    # Mode 1: Existing project lookup
    project_code: Optional[str] = Field(None, description="Project code to query live database (e.g. N18000419)")

    # Mode 2: What-if simulation parameters
    original_cost: Optional[float] = Field(None, gt=0, description="Original sanctioned cost in Crore")
    revised_cost: Optional[float] = Field(None, ge=0, description="Revised sanctioned cost in Crore")
    anticipated_cost: Optional[float] = Field(None, ge=0, description="Latest anticipated cost in Crore")
    cumulative_expenditure: Optional[float] = Field(None, ge=0, description="Cumulative expenditure to date in Crore")
    physical_progress: Optional[float] = Field(None, ge=0.0, le=100.0, description="Physical progress percentage (0-100)")
    months_elapsed: Optional[float] = Field(None, ge=0.0, description="Months elapsed since sanction")
    months_originally_planned: Optional[float] = Field(None, gt=0.0, description="Originally planned duration in months")
    months_remaining: Optional[float] = Field(None, description="Anticipated months remaining to completion")
    delay_months: Optional[float] = Field(None, description="Current delay in months")
    sector: Optional[str] = Field(None, description="Infrastructure sector (e.g. Railways, Roads & Highways)")
    agency: Optional[str] = Field(None, description="Implementing agency (e.g. NHAI, MOR)")
    state: Optional[str] = Field(None, description="State / Multi-state territory")

    @model_validator(mode="after")
    def validate_request_mode(self):
        if not self.project_code and self.original_cost is None:
            raise ValueError("Must provide either 'project_code' (Mode 1: Existing project) or 'original_cost' (Mode 2: What-if analysis).")
        return self


class MLPredictionResponse(BaseModel):
    mode: str = Field(..., description="'existing_project' or 'what_if_analysis'")
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    predicted_risk_probability: float = Field(..., ge=0.0, le=1.0, description="Calibrated probability of severe risk within 12 months")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Normalized risk index from 0 to 100")
    risk_tier: str = Field(..., description="High, Moderate, or Low")
    is_severe_risk_alert: bool = Field(..., description="True if probability >= operational threshold")
    operational_threshold: float = Field(..., description="Cost-minimized decision threshold (e.g. 0.25)")
    confidence_assessment: str = Field(..., description="Reliability / calibration interval")
    key_risk_drivers: List[RiskDriver] = Field(default_factory=list, description="Top positive SHAP contributors increasing risk")
    protective_factors: List[RiskDriver] = Field(default_factory=list, description="Top negative SHAP contributors mitigating risk")
    inference_latency_ms: float = Field(..., description="End-to-end inference execution time in milliseconds")
