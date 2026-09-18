import re
from typing import List, Dict, Any, Optional

from backend.app.services.query_service import search_projects, filter_projects, compare_projects, get_project_by_code
from backend.app.services.analytics_service import (
    get_executive_summary,
    get_risk_distribution,
    get_state_statistics,
    get_agency_statistics,
    get_cost_delay_analytics
)
from backend.app.services.risk_engine import RiskEngineService
from backend.app.services.retrieval_service import RetrievalService
from backend.app.services.document_service import DocumentService
from backend.app.services.risk_decomposition_service import RiskDecompositionService
from backend.app.services.risk_trajectory_service import RiskTrajectoryService
from backend.app.services.recommendation_engine import PrescriptiveRecommendationEngine
from backend.app.services.early_warning_service import EarlyWarningPrioritizationService
from backend.app.services.executive_briefing_service import ExecutiveBriefingService

PROJECT_CODE_PATTERN = re.compile(r'\b([0-9N]\d{8})\b')


class DeterministicToolRegistry:
    """Strict controlled tools that wrap backend services. Prevents arbitrary SQL execution or DB hallucination."""
    
    def __init__(self):
        self.risk_engine = RiskEngineService()
        self.retrieval_service = RetrievalService()
        self.document_service = DocumentService()
        self.decomposition_service = RiskDecompositionService()
        self.trajectory_service = RiskTrajectoryService()
        self.recommendation_engine = PrescriptiveRecommendationEngine()
        self.early_warning_service = EarlyWarningPrioritizationService()
        self.executive_briefing_service = ExecutiveBriefingService()

    def get_executive_summary(self) -> Dict[str, Any]:
        return get_executive_summary()

    def get_state_statistics(self) -> List[Dict[str, Any]]:
        return get_state_statistics()

    def get_agency_statistics(self) -> List[Dict[str, Any]]:
        return get_agency_statistics()

    def get_risk_distribution(self) -> Dict[str, Any]:
        return get_risk_distribution()

    def get_cost_delay_analytics(self) -> Dict[str, Any]:
        return get_cost_delay_analytics()

    def search_projects(self, query: str) -> List[Dict[str, Any]]:
        return search_projects(query_str=query)

    def filter_projects(
        self,
        state: Optional[str] = None,
        agency: Optional[str] = None,
        risk_category: Optional[str] = None,
        min_cost: Optional[float] = None,
        max_cost: Optional[float] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        return filter_projects(
            state=state,
            agency=agency,
            risk_category=risk_category,
            min_cost=min_cost,
            max_cost=max_cost,
            limit=limit
        )

    def compare_projects(self, project_codes: List[str]) -> List[Dict[str, Any]]:
        return compare_projects(project_codes=project_codes)

    def get_project(self, project_code: str) -> Optional[Dict[str, Any]]:
        return get_project_by_code(project_code=project_code)

    def get_project_risk(self, project_code: str) -> Optional[Dict[str, Any]]:
        return self.risk_engine.get_project_risk_assessment(project_code=project_code)

    def get_project_risk_decomposition(self, project_code: str) -> Optional[Dict[str, Any]]:
        return self.decomposition_service.decompose_project_risk(project_code=project_code)

    def get_project_risk_trajectory(self, project_code: str) -> Optional[Dict[str, Any]]:
        return self.trajectory_service.get_project_risk_trajectory(project_code=project_code)

    def get_project_recommendations(self, project_code: str) -> Optional[Dict[str, Any]]:
        return self.recommendation_engine.get_project_recommendations(project_code=project_code)

    def get_early_warning_projects(self, limit: int = 15) -> List[Dict[str, Any]]:
        return self.early_warning_service.get_early_warning_projects(limit=limit)

    def get_executive_briefing(self) -> Dict[str, Any]:
        return self.executive_briefing_service.get_executive_briefing()

    def search_documents(
        self,
        query: str,
        project_code: Optional[str] = None,
        reporting_month: Optional[str] = None,
        document_type: Optional[str] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        res = self.retrieval_service.search(
            query=query,
            project_code=project_code,
            reporting_month=reporting_month,
            document_type=document_type,
            top_k=top_k
        )
        return res.model_dump()

    def get_project_documents(self, project_code: str, limit: int = 10) -> List[Dict[str, Any]]:
        return self.document_service.get_project_documents(project_code=project_code, limit=limit)


class QueryRouter:
    """Classifies user query intent, extracts entities, and invokes deterministic tools."""

    def __init__(self):
        self.tools = DeterministicToolRegistry()

    def extract_entities(self, query: str, session_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract project codes, years, months, states, and risk levels from query text."""
        query_upper = query.upper()
        found_codes = list(set(PROJECT_CODE_PATTERN.findall(query_upper)))

        # Pronoun & Entity Resolution via Session Memory
        if not found_codes and session_context and session_context.get("last_project_code"):
            pronoun_triggers = ["ITS", "IT", "THIS PROJECT", "THAT PROJECT", "SAME PROJECT", "THE PROJECT"]
            if any(trigger in query_upper for trigger in pronoun_triggers):
                found_codes = [session_context["last_project_code"]]

        # Extract Risk Categories
        found_risk = None
        for cat in ["CRITICAL", "HIGH", "MODERATE", "LOW"]:
            if cat in query_upper:
                found_risk = cat
                break

        # Extract Reporting Month (YYYY-MM)
        month_match = re.search(r'\b(20[1-2][0-9]-(?:0[1-9]|1[0-2]))\b', query)
        found_month = month_match.group(1) if month_match else None

        # Extract Document Type
        found_doc_type = None
        if "QUARTERLY" in query_upper:
            found_doc_type = "QUARTERLY"
        elif "SYNOPSIS" in query_upper or "OVERVIEW" in query_upper:
            found_doc_type = "PART_I_SYNOPSIS"

        return {
            "project_codes": found_codes,
            "primary_project_code": found_codes[0] if found_codes else None,
            "risk_category": found_risk,
            "reporting_month": found_month,
            "document_type": found_doc_type,
            "has_comparison": len(found_codes) > 1 or "COMPARE" in query_upper or "VS" in query_upper
        }

    def route_and_execute(self, query: str, session_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Classify query intent, execute deterministic tools, and aggregate raw evidence."""
        query_lower = query.lower()
        entities = self.extract_entities(query, session_context)
        p_code = entities["primary_project_code"]

        tools_used = []
        structured_evidence = []
        risk_evidence = []
        document_evidence = []

        # Intent Classification Decision Tree
        if "situation" in query_lower or "brief" in query_lower or "executive monitoring" in query_lower or "overview situation" in query_lower:
            intent = "EXECUTIVE_MONITORING_BRIEF"
            tools_used.append("get_executive_briefing")
            brief_res = self.tools.get_executive_briefing()
            structured_evidence.append(brief_res.get("portfolio_kpis", {}))
            structured_evidence.extend(brief_res.get("top_early_warning_projects", []))
            document_evidence.extend(brief_res.get("documentary_context", []))

        elif "urgent" in query_lower or "early warning" in query_lower or "require attention" in query_lower or "require urgent" in query_lower:
            intent = "EARLY_WARNING_PRIORITIZATION"
            tools_used.append("get_early_warning_projects")
            ew_res = self.tools.get_early_warning_projects(limit=10)
            risk_evidence.extend(ew_res)

        elif entities["has_comparison"] and len(entities["project_codes"]) >= 2:
            intent = "COMPARATIVE_ANALYSIS"
            tools_used.append("compare_projects")
            comp_res = self.tools.compare_projects(entities["project_codes"])
            structured_evidence.extend(comp_res)
            
            for code in entities["project_codes"]:
                tools_used.append("get_project_risk")
                risk_info = self.tools.get_project_risk(code)
                if risk_info:
                    risk_evidence.append(risk_info)

        elif "source" in query_lower or "citation" in query_lower or "supporting" in query_lower:
            intent = "EVIDENCE_CITATION"
            if p_code:
                tools_used.append("get_project_documents")
                doc_res = self.tools.get_project_documents(p_code, limit=5)
                document_evidence.extend(doc_res)
            else:
                tools_used.append("search_documents")
                search_res = self.tools.search_documents(query, top_k=5)
                document_evidence.extend(search_res.get("retrieved_chunks", []))

        elif p_code:
            # When a specific project code is referenced
            if "trajectory" in query_lower or "evolve" in query_lower or "trend" in query_lower or "over time" in query_lower or "history of risk" in query_lower:
                intent = "RISK_TRAJECTORY_TREND"
                tools_used.extend(["get_project_risk_trajectory", "get_project_risk"])
                traj_res = self.tools.get_project_risk_trajectory(p_code)
                if traj_res:
                    risk_evidence.append(traj_res)
                risk_info = self.tools.get_project_risk(p_code)
                if risk_info:
                    risk_evidence.append(risk_info)

            elif "recommend" in query_lower or "suggest" in query_lower or "action" in query_lower or "mitigat" in query_lower:
                intent = "PRESCRIPTIVE_RECOMMENDATIONS"
                tools_used.extend(["get_project_recommendations", "get_project_risk"])
                rec_res = self.tools.get_project_recommendations(p_code)
                if rec_res:
                    risk_evidence.append(rec_res)
                risk_info = self.tools.get_project_risk(p_code)
                if risk_info:
                    risk_evidence.append(risk_info)

            else:
                is_historical = any(k in query_lower for k in ["report", "say", "document", "paimana", "historical", "2017", "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026"])
                is_hybrid = any(k in query_lower for k in ["why", "who", "delay", "overrun", "reason", "cause", "history", "responsible"])

                if is_historical and not is_hybrid:
                    intent = "HISTORICAL_DOCUMENT_RAG"
                    tools_used.append("search_documents")
                    search_res = self.tools.search_documents(
                        query=query,
                        project_code=p_code,
                        reporting_month=entities["reporting_month"],
                        document_type=entities["document_type"],
                        top_k=5
                    )
                    document_evidence.extend(search_res.get("retrieved_chunks", []))
                elif is_hybrid:
                    intent = "HYBRID_MULTI_SOURCE"
                    tools_used.extend(["get_project_risk", "get_project", "search_documents"])
                    risk_info = self.tools.get_project_risk(p_code)
                    if risk_info:
                        risk_evidence.append(risk_info)
                    proj_info = self.tools.get_project(p_code)
                    if proj_info:
                        structured_evidence.append(proj_info)
                    doc_res = self.tools.search_documents(query=query, project_code=p_code, top_k=5)
                    document_evidence.extend(doc_res.get("retrieved_chunks", []))
                else:
                    intent = "PROJECT_RISK_INFERENCE"
                    tools_used.extend(["get_project_risk", "get_project"])
                    risk_info = self.tools.get_project_risk(p_code)
                    if risk_info:
                        risk_evidence.append(risk_info)
                    proj_info = self.tools.get_project(p_code)
                    if proj_info:
                        structured_evidence.append(proj_info)

        else:
            # General portfolio analytics or general historical documents without project code
            if any(k in query_lower for k in ["report", "say", "document", "paimana", "quarterly", "synopsis"]):
                intent = "HISTORICAL_DOCUMENT_RAG"
                tools_used.append("search_documents")
                search_res = self.tools.search_documents(
                    query=query,
                    reporting_month=entities["reporting_month"],
                    document_type=entities["document_type"],
                    top_k=5
                )
                document_evidence.extend(search_res.get("retrieved_chunks", []))
            else:
                intent = "STRUCTURED_ANALYTICS"
                if "state" in query_lower:
                    tools_used.append("get_state_statistics")
                    res = self.tools.get_state_statistics()
                    structured_evidence.extend(res if isinstance(res, list) else [res])
                elif "agency" in query_lower or "ministry" in query_lower:
                    tools_used.append("get_agency_statistics")
                    res = self.tools.get_agency_statistics()
                    structured_evidence.extend(res if isinstance(res, list) else [res])
                elif "cost" in query_lower or "delay" in query_lower:
                    tools_used.append("get_cost_delay_analytics")
                    res = self.tools.get_cost_delay_analytics()
                    structured_evidence.extend(res if isinstance(res, list) else [res])
                elif entities["risk_category"] or "how many" in query_lower or "risk distribution" in query_lower:
                    tools_used.append("get_risk_distribution")
                    res = self.tools.get_risk_distribution()
                    structured_evidence.extend(res if isinstance(res, list) else [res])
                else:
                    tools_used.append("get_executive_summary")
                    res = self.tools.get_executive_summary()
                    structured_evidence.extend(res if isinstance(res, list) else [res])

        return {
            "intent": intent,
            "entities": entities,
            "tools_used": list(set(tools_used)),
            "structured_evidence": structured_evidence,
            "risk_evidence": risk_evidence,
            "document_evidence": document_evidence
        }
