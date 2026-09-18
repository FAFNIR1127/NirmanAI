from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from backend.app.schemas.project import ProjectSummary, ProjectDetail, ProjectPaginatedResponse
from backend.app.schemas.analytics import ProjectComparisonItem
from backend.app.services.project_service import list_projects_summary, get_project_details
from backend.app.services.query_service import search_projects, filter_projects, compare_projects, query_projects

router = APIRouter(prefix="/api/projects", tags=["Projects"])



@router.get("", response_model=ProjectPaginatedResponse)
def get_projects(
    search: Optional[str] = None,
    sector: Optional[str] = None,
    agency: Optional[str] = None,
    state: Optional[str] = None,
    risk_category: Optional[str] = None,
    min_cost: Optional[float] = None,
    max_cost: Optional[float] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=1000),
    sort_by: str = Query("cost_overrun_cr"),
    order: str = Query("desc")
):
    return query_projects(
        search=search,
        sector=sector,
        agency=agency,
        state=state,
        risk_category=risk_category,
        min_cost=min_cost,
        max_cost=max_cost,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        order=order
    )


@router.get("/search", response_model=List[ProjectSummary])
def search_projects_endpoint(q: str = Query(..., min_length=1), limit: int = Query(50, ge=1, le=500)):
    return search_projects(query_str=q, limit=limit)


@router.get("/filter", response_model=List[ProjectSummary])
def filter_projects_endpoint(
    state: Optional[str] = None,
    agency: Optional[str] = None,
    risk_category: Optional[str] = None,
    min_cost: Optional[float] = None,
    max_cost: Optional[float] = None,
    limit: int = Query(100, ge=1, le=500)
):
    return filter_projects(
        state=state,
        agency=agency,
        risk_category=risk_category,
        min_cost=min_cost,
        max_cost=max_cost,
        limit=limit
    )



@router.get("/compare", response_model=List[ProjectComparisonItem])
def compare_projects_endpoint(codes: str = Query(..., description="Comma-separated project codes e.g. 020100044,N04000073")):
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if not code_list:
        raise HTTPException(status_code=400, detail="Must provide at least one valid project code")
    return compare_projects(code_list)


@router.get("/{project_code}", response_model=ProjectDetail)
def get_project_by_code(project_code: str):
    detail = get_project_details(project_code)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Project with code '{project_code}' not found")
    return detail
