from typing import Optional, List
from pydantic import BaseModel


class ProjectSummary(BaseModel):
    project_code: str
    project_name: Optional[str] = None
    name: Optional[str] = None
    agency: Optional[str] = None
    state: Optional[str] = None
    sector: Optional[str] = None
    approval_date: Optional[str] = None
    original_cost: Optional[float] = None
    anticipated_cost: Optional[float] = None
    delay_months: Optional[float] = None
    physical_progress: Optional[float] = None
    risk_score: Optional[float] = None
    risk_category: Optional[str] = None


class ProjectObservation(BaseModel):
    reporting_month: str
    revised_cost: Optional[float] = None
    anticipated_cost: Optional[float] = None
    cumulative_expenditure: Optional[float] = None
    physical_progress: Optional[float] = None
    original_doc: Optional[str] = None
    anticipated_doc: Optional[str] = None
    delay_months: Optional[float] = None


class ProjectDetail(BaseModel):
    project_code: str
    project_name: Optional[str] = None
    name: Optional[str] = None
    agency: Optional[str] = None
    state: Optional[str] = None
    sector: Optional[str] = None
    approval_date: Optional[str] = None
    original_cost: Optional[float] = None
    latest_anticipated_cost: Optional[float] = None
    latest_delay_months: Optional[float] = None
    latest_physical_progress: Optional[float] = None
    latest_original_doc: Optional[str] = None
    latest_anticipated_doc: Optional[str] = None
    observations: List[ProjectObservation] = []


class ProjectPaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    projects: List[ProjectSummary]


