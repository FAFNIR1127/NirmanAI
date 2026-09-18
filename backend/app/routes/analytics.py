from typing import List, Optional
from fastapi import APIRouter, Query
from backend.app.schemas.analytics import (
    ExecutiveSummaryResponse, RiskCategoryDistributionItem,
    StateStatisticsItem, AgencyStatisticsItem, CostDelayAnalyticsResponse,
    GeographicRiskResponse
)
from backend.app.services.analytics_service import (
    get_executive_summary, get_risk_distribution,
    get_state_statistics, get_agency_statistics, get_cost_delay_analytics,
    get_geographic_risk
)

from backend.app.services.cache_service import cache_service

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])



@router.get("/summary", response_model=ExecutiveSummaryResponse)
@router.get("/portfolio_kpis", response_model=ExecutiveSummaryResponse)
def get_summary():
    cached = cache_service.get("analytics:portfolio_kpis")
    if cached:
        return cached
    res = get_executive_summary()
    cache_service.set("analytics:portfolio_kpis", res, ttl_seconds=60)
    return res




@router.get("/risk-distribution", response_model=List[RiskCategoryDistributionItem])
def get_risk_dist():
    return get_risk_distribution()


@router.get("/by-state", response_model=List[StateStatisticsItem])
def get_by_state(limit: int = Query(50, ge=1, le=500)):
    return get_state_statistics(limit=limit)


@router.get("/by-agency", response_model=List[AgencyStatisticsItem])
def get_by_agency(limit: int = Query(50, ge=1, le=500)):
    return get_agency_statistics(limit=limit)


@router.get("/cost-delay-stats", response_model=CostDelayAnalyticsResponse)
def get_cost_delay():
    return get_cost_delay_analytics()


@router.get("/geographic_risk", response_model=GeographicRiskResponse)
@router.get("/geographic-risk", response_model=GeographicRiskResponse)
def get_geo_risk():
    return get_geographic_risk()

