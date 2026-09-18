"""
backend/app/services/capability_registry.py

Phase 13 — Machine-Readable Capability & Tool Registry.
Defines strict schemas and execution contracts for all Nirman capabilities across:
- Project Data (get_project, search_projects, filter_projects, compare_projects)
- Analytics (portfolio_kpis, state_stats, agency_stats, cost_delay_analytics)
- Risk Intelligence (risk_prediction, decomposition, trajectory, early_warnings, recommendations)
- Documents & RAG (semantic_search, project_evidence, historical_reports)
- Conversation Context (project_context, active_filters, result_sets)
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class CapabilityContract(BaseModel):
    name: str
    category: str  # "project_data", "analytics", "risk_intelligence", "documents", "conversation"
    description: str
    required_params: List[str] = Field(default_factory=list)
    optional_params: List[str] = Field(default_factory=list)
    is_deterministic: bool = True
    produces_evidence: bool = True


# Global Registry of all capabilities exposed to the LLM Planner
CAPABILITIES: Dict[str, CapabilityContract] = {
    # Project Data Capabilities
    "get_project": CapabilityContract(
        name="get_project",
        category="project_data",
        description="Retrieve complete metadata, cost, schedule, and state for a single project code.",
        required_params=["project_code"]
    ),
    "search_projects": CapabilityContract(
        name="search_projects",
        category="project_data",
        description="Search projects by keyword, project code, or agency name.",
        required_params=["query"]
    ),
    "filter_projects": CapabilityContract(
        name="filter_projects",
        category="project_data",
        description="Filter projects by state, sector, agency, risk level, or cost overrun criteria.",
        optional_params=["state", "sector", "agency", "risk_category", "min_cost", "max_cost", "expenditure_progress_gap"]
    ),
    "compare_projects": CapabilityContract(
        name="compare_projects",
        category="project_data",
        description="Compare 2 or more projects side-by-side on financials, schedule, risk scores, and progress.",
        required_params=["project_codes"]
    ),

    # Analytics Capabilities
    "portfolio_kpis": CapabilityContract(
        name="portfolio_kpis",
        category="analytics",
        description="Retrieve portfolio summary KPIs (total projects, cost overruns, average delays, risk counts)."
    ),
    "state_stats": CapabilityContract(
        name="state_stats",
        category="analytics",
        description="Retrieve state-level geographic risk distribution and cost exposure breakdown.",
        optional_params=["state"]
    ),
    "agency_stats": CapabilityContract(
        name="agency_stats",
        category="analytics",
        description="Retrieve agency-level project concentration and risk exposure breakdown.",
        optional_params=["agency"]
    ),

    # Risk Intelligence Capabilities
    "risk_prediction": CapabilityContract(
        name="risk_prediction",
        category="risk_intelligence",
        description="Retrieve XGBoost Risk Engine v1 risk score, risk category (Critical/High/Watchlist/Normal), and probability.",
        required_params=["project_code"]
    ),
    "risk_decomposition": CapabilityContract(
        name="risk_decomposition",
        category="risk_intelligence",
        description="Retrieve SHAP feature attribution risk drivers and protective signals for a project.",
        required_params=["project_code"]
    ),
    "risk_trajectory": CapabilityContract(
        name="risk_trajectory",
        category="risk_intelligence",
        description="Retrieve historical risk score trend, slope, variance, and observation trajectory.",
        required_params=["project_code"]
    ),
    "early_warnings": CapabilityContract(
        name="early_warnings",
        category="risk_intelligence",
        description="Retrieve projects crossing the configured early warning threshold (T* >= 0.28).",
        optional_params=["state", "sector", "agency"]
    ),
    "recommendations": CapabilityContract(
        name="recommendations",
        category="risk_intelligence",
        description="Retrieve policy-triggered monitoring recommendations and audit rationale for a project.",
        required_params=["project_code"]
    ),

    # Document & RAG Capabilities
    "semantic_search": CapabilityContract(
        name="semantic_search",
        category="documents",
        description="Perform RAG hybrid RRF vector search across 331,206 document chunks from 150 official PAIMANA PDF reports.",
        required_params=["query"],
        optional_params=["project_code", "sector", "top_k"]
    ),
    "project_evidence": CapabilityContract(
        name="project_evidence",
        category="documents",
        description="Retrieve historical document report excerpts linked to a specific project code.",
        required_params=["project_code"]
    )
}


class CapabilityRegistry:
    """Provides machine-readable access and validation for system capabilities."""

    @staticmethod
    def get_capability(name: str) -> Optional[CapabilityContract]:
        return CAPABILITIES.get(name)

    @staticmethod
    def list_capabilities() -> List[Dict[str, Any]]:
        return [c.model_dump() for c in CAPABILITIES.values()]

    @staticmethod
    def format_capability_summary() -> str:
        """Returns concise summary of capabilities for LLM Query Planner prompt."""
        lines = []
        for name, cap in CAPABILITIES.items():
            lines.append(f"- {name} ({cap.category}): {cap.description}")
        return "\n".join(lines)
