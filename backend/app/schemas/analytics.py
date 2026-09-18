from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class ExecutiveSummaryResponse(BaseModel):
    total_master_projects: int
    total_live_projects_2026: int
    total_original_cost_crore: float
    total_anticipated_cost_crore: float
    total_cost_overrun_crore: float
    overall_cost_overrun_percent: float
    critical_risk_project_count: int
    high_risk_project_count: int
    moderate_risk_project_count: int
    low_risk_project_count: int
    total_projects: Optional[int] = None
    high_critical_risk_count: Optional[int] = None
    high_risk_percentage: Optional[float] = None
    avg_cost_expansion: Optional[float] = 1.25
    avg_schedule_slippage: Optional[float] = 0.22
    avg_delay_months: Optional[float] = 22.0
    top_sectors_by_cost_overrun: Optional[List[Dict[str, Any]]] = []


class GeographicRiskItem(BaseModel):
    state: str
    total_projects: int
    high_risk_projects: int
    critical_risk_projects: int
    total_cost_overrun_cr: float
    avg_delay_months: float


class GeographicRiskResponse(BaseModel):
    states: List[GeographicRiskItem]





class RiskCategoryDistributionItem(BaseModel):
    risk_category: str
    project_count: int
    percent_of_total: float
    avg_risk_score: float
    total_anticipated_cost_crore: float


class StateStatisticsItem(BaseModel):
    state: str
    project_count: int
    total_original_cost_crore: float
    total_anticipated_cost_crore: float
    avg_risk_score: Optional[float] = None
    high_critical_risk_count: int


class AgencyStatisticsItem(BaseModel):
    agency: str
    project_count: int
    total_original_cost_crore: float
    total_anticipated_cost_crore: float
    cost_overrun_percent: float
    avg_risk_score: Optional[float] = None
    high_critical_risk_count: int


class CostDelayAnalyticsResponse(BaseModel):
    total_projects_with_cost_expansion: int
    avg_cost_expansion_ratio: float
    max_cost_expansion_ratio: float
    total_projects_with_delay: int
    avg_delay_months: float
    max_delay_months: float
    top_cost_overrun_projects: List[Dict[str, Any]] = []
    top_delayed_projects: List[Dict[str, Any]] = []


class ProjectComparisonItem(BaseModel):
    project_code: str
    project_name: Optional[str] = None
    agency: Optional[str] = None
    state: Optional[str] = None
    approval_date: Optional[str] = None
    original_cost: Optional[float] = None
    latest_anticipated_cost: Optional[float] = None
    cost_overrun_percent: Optional[float] = None
    delay_months: Optional[float] = None
    risk_score: Optional[float] = None
    risk_category: Optional[str] = None
    schedule_risk_index: Optional[float] = None
    cost_risk_index: Optional[float] = None
