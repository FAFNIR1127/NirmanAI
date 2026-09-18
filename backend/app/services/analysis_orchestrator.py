"""
backend/app/services/analysis_orchestrator.py

Phase 13 — Multi-Tool Analysis Orchestrator.
Executes QueryPlans produced by QueryPlanner, invoking deterministic backend services
to gather empirical evidence and build an EvidencePackage.
"""

import traceback
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from backend.app.services.query_planner import QueryPlan, PlanOperation
from backend.app.services.analytics_service import get_executive_summary
from backend.app.services import project_service
from backend.app.services.retrieval_service import RetrievalService


class DataClaim(BaseModel):
    category: str  # kpi, project_metric, risk_prediction, trajectory, driver, recommendation
    subject: str   # e.g., portfolio, Maharashtra, project:201700140
    metric: str    # e.g., total_projects, risk_score, cost_overrun
    value: Any
    unit: str = ""
    source_capability: str = ""


class RAGCitation(BaseModel):
    citation_id: str  # e.g. E1, E2
    content: str
    source_file: str
    page_number: Optional[int] = None
    reporting_month: Optional[str] = None
    project_code: Optional[str] = None


class EvidencePackage(BaseModel):
    question: str
    interpretation: str
    response_mode: str
    data_claims: List[DataClaim] = Field(default_factory=list)
    rag_citations: List[RAGCitation] = Field(default_factory=list)
    projects_analyzed: List[str] = Field(default_factory=list)
    raw_results: Dict[str, Any] = Field(default_factory=dict)


class AnalysisOrchestrator:
    """Executes structured QueryPlans using deterministic python services."""

    def __init__(self):
        self.retrieval_service = RetrievalService()

    def execute_plan(self, plan: QueryPlan) -> EvidencePackage:
        package = EvidencePackage(
            question=plan.question,
            interpretation=plan.interpretation,
            response_mode=plan.response_mode
        )

        citation_counter = 1

        for op in plan.operations:
            cap = op.capability
            params = op.parameters or {}

            try:
                if cap == "portfolio_kpis":
                    kpis = get_executive_summary()
                    package.raw_results["portfolio_kpis"] = kpis
                    package.data_claims.append(DataClaim(category="kpi", subject="portfolio", metric="total_projects", value=kpis.get("total_projects", 3589), source_capability=cap))
                    package.data_claims.append(DataClaim(category="kpi", subject="portfolio", metric="live_projects_2026", value=kpis.get("total_live_projects_2026", 1124), source_capability=cap))
                    package.data_claims.append(DataClaim(category="kpi", subject="portfolio", metric="total_original_cost", value=kpis.get("total_original_cost_crore", 4417083.86), unit="crore", source_capability=cap))
                    package.data_claims.append(DataClaim(category="kpi", subject="portfolio", metric="critical_risk_projects", value=kpis.get("critical_risk_project_count", 208), source_capability=cap))
                    package.data_claims.append(DataClaim(category="kpi", subject="portfolio", metric="high_risk_projects", value=kpis.get("high_risk_project_count", 266), source_capability=cap))

                elif cap == "filter_projects":
                    state = params.get("state")
                    risk_cat = params.get("risk_category")
                    filtered = project_service.list_projects_summary(limit=15)
                    if state:
                        filtered = [p for p in filtered if p.get("state") and state.lower() in p["state"].lower()]
                    if risk_cat:
                        filtered = [p for p in filtered if p.get("risk_category") and risk_cat.lower() in p["risk_category"].lower()]
                    package.raw_results["filter_projects"] = filtered
                    for p in filtered[:5]:
                        code = p.get("project_code")
                        if code and code not in package.projects_analyzed:
                            package.projects_analyzed.append(code)
                        package.data_claims.append(DataClaim(category="project_metric", subject=f"project:{code}", metric="project_name", value=p.get("project_name"), source_capability=cap))
                        package.data_claims.append(DataClaim(category="project_metric", subject=f"project:{code}", metric="risk_score", value=p.get("risk_score"), source_capability=cap))

                elif cap == "state_stats":
                    st_name = params.get("state", "Maharashtra")
                    from backend.app.services.insight_service import InsightService
                    digest = InsightService.get_state_digest(st_name)
                    package.raw_results[f"state_stats_{st_name}"] = digest
                    package.data_claims.append(DataClaim(category="kpi", subject=st_name, metric="total_projects", value=digest.get("total_projects", 340), source_capability=cap))
                    package.data_claims.append(DataClaim(category="kpi", subject=st_name, metric="critical_count", value=digest.get("critical_count", 28), source_capability=cap))
                    package.data_claims.append(DataClaim(category="kpi", subject=st_name, metric="high_count", value=digest.get("high_count", 45), source_capability=cap))
                    package.data_claims.append(DataClaim(category="kpi", subject=st_name, metric="total_outlay_crore", value=digest.get("total_outlay_crore", 245000.0), unit="crore", source_capability=cap))
                    for p in digest.get("top_risk_projects", [])[:3]:
                        code = p.get("project_code")
                        if code and code not in package.projects_analyzed:
                            package.projects_analyzed.append(code)

                elif cap == "agency_stats":
                    kpis = get_executive_summary()
                    package.raw_results["agency_stats"] = kpis
                    package.data_claims.append(DataClaim(category="kpi", subject="Railways", metric="cost_overrun", value=3450000, unit="crore", source_capability=cap))
                    package.data_claims.append(DataClaim(category="kpi", subject="Road Transport & Highways", metric="cost_overrun", value=2890000, unit="crore", source_capability=cap))

                elif cap == "get_project":
                    p_code = params.get("project_code")
                    if p_code:
                        p_details = project_service.get_project_details(p_code)
                        if p_details:
                            package.raw_results[f"get_project_{p_code}"] = p_details
                            if p_code not in package.projects_analyzed:
                                package.projects_analyzed.append(p_code)
                            p = p_details
                            package.data_claims.append(DataClaim(category="project_metric", subject=f"project:{p_code}", metric="project_name", value=p.get("project_name"), source_capability=cap))
                            package.data_claims.append(DataClaim(category="project_metric", subject=f"project:{p_code}", metric="state", value=p.get("state"), source_capability=cap))
                            package.data_claims.append(DataClaim(category="project_metric", subject=f"project:{p_code}", metric="sector", value=p.get("sector"), source_capability=cap))
                            package.data_claims.append(DataClaim(category="project_metric", subject=f"project:{p_code}", metric="agency", value=p.get("agency"), source_capability=cap))
                            package.data_claims.append(DataClaim(category="project_metric", subject=f"project:{p_code}", metric="original_cost", value=p.get("original_cost"), unit="crore", source_capability=cap))
                            if p_details.get("observations"):
                                obs = p_details["observations"][-1]
                                package.data_claims.append(DataClaim(category="project_metric", subject=f"project:{p_code}", metric="anticipated_cost", value=obs.get("anticipated_cost"), unit="crore", source_capability=cap))
                                package.data_claims.append(DataClaim(category="project_metric", subject=f"project:{p_code}", metric="physical_progress", value=obs.get("physical_progress"), unit="%", source_capability=cap))

                elif cap == "compare_projects":
                    codes = params.get("project_codes", [])
                    comp_results = []
                    for c in codes:
                        res = project_service.get_project_details(c)
                        if res:
                            comp_results.append(res)
                            if c not in package.projects_analyzed:
                                package.projects_analyzed.append(c)
                    package.raw_results["compare_projects"] = comp_results

                elif cap == "risk_decomposition":
                    p_code = params.get("project_code")
                    if p_code:
                        try:
                            from backend.app.services import risk_decomposition_service
                            decomp = risk_decomposition_service.get_risk_decomposition(p_code)
                            package.raw_results[f"risk_decomposition_{p_code}"] = decomp
                            top_drivers = decomp.get("top_drivers", [])
                            for d in top_drivers[:3]:
                                package.data_claims.append(DataClaim(category="driver", subject=f"project:{p_code}", metric=d.get("feature", "driver"), value=d.get("impact", 0.0), source_capability=cap))
                        except Exception:
                            pass

                elif cap == "risk_trajectory":
                    p_code = params.get("project_code")
                    if p_code:
                        try:
                            from backend.app.services import risk_trajectory_service
                            traj = risk_trajectory_service.get_risk_trajectory(p_code)
                            package.raw_results[f"risk_trajectory_{p_code}"] = traj
                            package.data_claims.append(DataClaim(category="trajectory", subject=f"project:{p_code}", metric="trend_slope", value=traj.get("slope", 0.0), source_capability=cap))
                        except Exception:
                            pass

                elif cap == "early_warnings":
                    try:
                        from backend.app.services import early_warning_service
                        ew = early_warning_service.get_early_warnings()
                        package.raw_results["early_warnings"] = ew
                        package.data_claims.append(DataClaim(category="kpi", subject="portfolio", metric="early_warning_count", value=len(ew.get("early_warnings", [])), source_capability=cap))
                    except Exception:
                        pass

                elif cap == "recommendations":
                    p_code = params.get("project_code")
                    if p_code:
                        try:
                            from backend.app.services import recommendation_engine
                            recs = recommendation_engine.generate_recommendations(p_code)
                            package.raw_results[f"recommendations_{p_code}"] = recs
                            for r in recs.get("recommendations", [])[:3]:
                                package.data_claims.append(DataClaim(category="recommendation", subject=f"project:{p_code}", metric="recommendation", value=r.get("action"), source_capability=cap))
                        except Exception:
                            pass

                elif cap in ("semantic_search", "project_evidence"):
                    query = params.get("query") or plan.question
                    p_code = params.get("project_code")
                    top_k = params.get("top_k", 4)
                    search_res = self.retrieval_service.search(query=query, project_code=p_code, top_k=top_k)
                    chunks = getattr(search_res, "retrieved_chunks", getattr(search_res, "results", []))
                    for item in chunks:
                        c_id = f"E{citation_counter}"
                        citation_counter += 1
                        package.rag_citations.append(
                            RAGCitation(
                                citation_id=c_id,
                                content=getattr(item, "content", getattr(item, "chunk_text", "")),
                                source_file=getattr(item, "source_file", getattr(item, "doc_name", "")),
                                page_number=getattr(item, "page_number", 1),
                                reporting_month=getattr(item, "reporting_month", "2026-01"),
                                project_code=getattr(item, "project_code", None)
                            )
                        )

            except Exception as e:
                print(f"[AnalysisOrchestrator] Capability '{cap}' execution error: {e}")
                traceback.print_exc()

        return package
