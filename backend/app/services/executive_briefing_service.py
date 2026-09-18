from typing import Dict, Any
from backend.app.services.analytics_service import get_executive_summary, get_risk_distribution, get_cost_delay_analytics
from backend.app.services.early_warning_service import EarlyWarningPrioritizationService
from backend.app.services.retrieval_service import RetrievalService


class ExecutiveBriefingService:
    """Synthesizes executive monitoring briefs, strictly enforcing evidence separation (Quantitative KPIs vs RAG Documentary Context)."""

    def __init__(self):
        self.early_warning_service = EarlyWarningPrioritizationService()
        self.retrieval_service = RetrievalService()

    def get_executive_briefing(self) -> Dict[str, Any]:
        # 1. Authoritative Quantitative KPIs directly from PostgreSQL
        exec_kpis = get_executive_summary()
        risk_dist = get_risk_distribution()
        cost_delay = get_cost_delay_analytics()
        early_warnings = self.early_warning_service.get_early_warning_projects(limit=5)

        # 2. Documentary Context from PAIMANA RAG Retrieval
        rag_res = self.retrieval_service.search(
            query="Infrastructure project monitoring executive overview cost overrun delay status",
            document_type="PART_I_SYNOPSIS",
            top_k=3
        )
        if not rag_res.retrieved_chunks:
            # Fallback search if SYNOPSIS filter returned no chunks
            rag_res = self.retrieval_service.search(
                query="Infrastructure project monitoring executive overview cost overrun delay status",
                top_k=3
            )

        doc_context = [chunk.model_dump() for chunk in rag_res.retrieved_chunks]

        # 3. Format Structured Executive Briefing Summary
        total_p = exec_kpis.get("total_master_projects", 0)
        orig_c = exec_kpis.get("total_original_cost_crore", 0.0)
        ant_c = exec_kpis.get("total_anticipated_cost_crore", 0.0)
        overrun_pct = exec_kpis.get("overall_cost_overrun_percent", 0.0)

        briefing_text = (
            f"=== NIRMAN EXECUTIVE INFRASTRUCTURE MONITORING BRIEF ===\n"
            f"• Portfolio Scope: Monitoring {total_p:,} projects with total original cost of ₹{orig_c:,.2f} Cr and anticipated cost of ₹{ant_c:,.2f} Cr (Overall Cost Overrun: {overrun_pct:.1f}%).\n"
            f"• Risk Distribution: {exec_kpis.get('critical_risk_project_count', 0)} Critical Risk, {exec_kpis.get('high_risk_project_count', 0)} High Risk, {exec_kpis.get('moderate_risk_project_count', 0)} Moderate Risk, {exec_kpis.get('low_risk_project_count', 0)} Low Risk projects.\n"
            f"• Cost & Delay Indicators: {cost_delay.get('total_projects_with_cost_expansion', 0)} projects experiencing cost expansion (avg: {cost_delay.get('avg_cost_expansion_ratio', 1.0):.2f}x); {cost_delay.get('total_projects_with_delay', 0)} projects experiencing schedule delays (avg: {cost_delay.get('avg_delay_months', 0.0):.1f} months).\n"
            f"• Top Priority Early Warning Projects: " + ", ".join([f"{p['project_code']} ({p['project_name'][:25]}... Risk: {p['risk_score']}/100)" for p in early_warnings[:3]])
        )

        return {
            "portfolio_kpis": exec_kpis,
            "risk_distribution": risk_dist,
            "cost_delay_analytics": cost_delay,
            "top_early_warning_projects": early_warnings,
            "documentary_context": doc_context,
            "executive_briefing_summary": briefing_text
        }
