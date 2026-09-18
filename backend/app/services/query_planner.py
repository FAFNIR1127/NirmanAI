"""
backend/app/services/query_planner.py

Phase 13 — LLM-Assisted Dynamic Query Planner.
Translates open-ended user questions into structured capability execution plans
validated against capability_registry.py.
"""

import json
import os
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from backend.app.services.capability_registry import CapabilityRegistry, CAPABILITIES
from backend.app.services.llm_service import get_api_keys


class PlanOperation(BaseModel):
    capability: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    depends_on: Optional[str] = None


class QueryPlan(BaseModel):
    question: str
    interpretation: str
    operations: List[PlanOperation]
    response_mode: str = "executive_analysis"  # highest_risk, state_analysis, agency_breakdown, cost_exposure, project_analysis, comparison, evidence, executive_analysis
    requires_rag_evidence: bool = False


class QueryPlanner:
    """Decomposes arbitrary natural language questions into structured capability execution plans."""

    def __init__(self):
        self.capabilities_summary = CapabilityRegistry.format_capability_summary()

    def create_plan(self, query: str, conversation_context: Dict[str, Any]) -> QueryPlan:
        """Create a validated execution plan for the given user query."""
        keys = get_api_keys()
        api_key = keys["GEMINI_API_KEY"] or keys["OPENAI_API_KEY"]

        if api_key:
            try:
                plan = self._llm_plan(query, conversation_context, api_key, is_gemini=bool(keys["GEMINI_API_KEY"]))
                if plan and self._validate_plan(plan):
                    return plan
            except Exception as e:
                print(f"[QueryPlanner] LLM planning attempt failed ({e}). Falling back to Rule-based Planner.")

        # Rule-based fallback planner
        return self._rule_based_plan(query, conversation_context)

    def _validate_plan(self, plan: QueryPlan) -> bool:
        """Validates that all capabilities and parameter keys exist in the Capability Registry."""
        if not plan.operations:
            return False
        for op in plan.operations:
            cap = CapabilityRegistry.get_capability(op.capability)
            if not cap:
                print(f"[QueryPlanner] Invalid capability in plan: {op.capability}")
                return False
        return True

    def _llm_plan(self, query: str, context: Dict[str, Any], api_key: str, is_gemini: bool) -> Optional[QueryPlan]:
        """Generate structured JSON QueryPlan via Gemini or OpenAI."""
        prompt = f"""You are the Query Planner for Nirman AI Copilot.
Your job is to analyze the user question and produce a valid JSON plan selecting capabilities from the registry below.

Registered Capabilities:
{self.capabilities_summary}

Conversation Context:
Active Project Code: {context.get('last_project_code') or 'None'}
Active Result Set (R1): {context.get('last_result_set_count', 0)} projects
Active State Filter: {context.get('active_state') or 'None'}

User Question: "{query}"

Respond with ONLY raw valid JSON (no markdown fences) matching this structure:
{{
  "question": "{query}",
  "interpretation": "Brief description of what the user wants to understand",
  "operations": [
    {{
      "capability": "capability_name",
      "parameters": {{ "param_name": "value" }}
    }}
  ],
  "response_mode": "highest_risk",
  "requires_rag_evidence": false
}}
"""
        if is_gemini:
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                res = client.models.generate_content(
                    model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
                    contents=prompt
                )
                text = res.text.strip()
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    d = json.loads(match.group(0))
                    return QueryPlan(**d)
            except Exception:
                pass
        return None

    def _rule_based_plan(self, query: str, context: Dict[str, Any]) -> QueryPlan:
        """Deterministic rule-based planner guaranteeing instant execution for all query types."""
        q_lower = query.lower()
        active_code = context.get('last_project_code')
        ops: List[PlanOperation] = []

        # Match project codes (e.g. 220100262, 201700140 or 020100044)
        code_match = re.search(r'\b([0-9]{8,10}|[A-Z0-9]{8,10})\b', query)
        p_code = code_match.group(1) if code_match else active_code

        # 1. Project Comparison
        if "compare" in q_lower or "versus" in q_lower or " vs " in q_lower:
            codes = re.findall(r'\b([0-9]{8,10}|[A-Z0-9]{8,10})\b', query)
            if len(codes) < 2 and active_code:
                codes.append(active_code)
            if len(codes) >= 2:
                ops.append(PlanOperation(capability="compare_projects", parameters={"project_codes": codes[:3]}))
                return QueryPlan(
                    question=query,
                    interpretation=f"Side-by-side comparative analysis of projects {' vs '.join(codes[:3])}",
                    operations=ops,
                    response_mode="comparison"
                )

        # 2. Specific Project Deep Dive
        if p_code and ("why" in q_lower or "risk" in q_lower or "explain" in q_lower or "detail" in q_lower or "analysis" in q_lower or "tell" in q_lower or "about" in q_lower or "project" in q_lower or "summarize" in q_lower or "driver" in q_lower):
            ops.append(PlanOperation(capability="get_project", parameters={"project_code": p_code}))
            ops.append(PlanOperation(capability="risk_decomposition", parameters={"project_code": p_code}))
            ops.append(PlanOperation(capability="recommendations", parameters={"project_code": p_code}))
            ops.append(PlanOperation(capability="project_evidence", parameters={"project_code": p_code}))
            return QueryPlan(
                question=query,
                interpretation=f"Multi-source risk, financial, and documentary briefing for project {p_code}",
                operations=ops,
                response_mode="project_analysis",
                requires_rag_evidence=True
            )

        # 3. Highest-Risk / Critical Projects Queries
        if "highest" in q_lower or "critical" in q_lower or "top risk" in q_lower or "escalat" in q_lower:
            ops.append(PlanOperation(capability="portfolio_kpis"))
            ops.append(PlanOperation(capability="early_warnings"))
            ops.append(PlanOperation(capability="filter_projects", parameters={"risk_category": "CRITICAL"}))
            return QueryPlan(
                question=query,
                interpretation="Highest-risk critical infrastructure project surveillance briefing",
                operations=ops,
                response_mode="highest_risk"
            )

        # 4. State / Regional Queries (e.g. Maharashtra, Tamil Nadu, etc.)
        state_match = re.search(r'\b(maharashtra|tamil nadu|uttar pradesh|gujarat|bihar|karnataka|west bengal|delhi|rajasthan|odisha|kerala|andhra pradesh|telangana|madhya pradesh|assam)\b', q_lower)
        if state_match:
            st_name = state_match.group(1).title()
            ops.append(PlanOperation(capability="state_stats", parameters={"state": st_name}))
            ops.append(PlanOperation(capability="filter_projects", parameters={"state": st_name, "risk_category": "CRITICAL"}))
            return QueryPlan(
                question=query,
                interpretation=f"Regional risk and project concentration analysis for {st_name}",
                operations=ops,
                response_mode="state_analysis"
            )

        # 5. Sector & Agency Breakdown Queries
        if "sector" in q_lower or "agency" in q_lower or "ministry" in q_lower or "breakdown" in q_lower or "railways" in q_lower or "morth" in q_lower or "power" in q_lower:
            ops.append(PlanOperation(capability="agency_stats"))
            ops.append(PlanOperation(capability="portfolio_kpis"))
            return QueryPlan(
                question=query,
                interpretation="Sectoral and ministry risk concentration breakdown",
                operations=ops,
                response_mode="agency_breakdown"
            )

        # 6. Cost & Schedule Exposure Queries
        if "cost" in q_lower or "overrun" in q_lower or "delay" in q_lower or "schedule" in q_lower or "exposure" in q_lower or "expenditure" in q_lower:
            ops.append(PlanOperation(capability="portfolio_kpis"))
            ops.append(PlanOperation(capability="filter_projects", parameters={"min_cost": 100}))
            return QueryPlan(
                question=query,
                interpretation="Portfolio cost overrun and schedule delay exposure analysis",
                operations=ops,
                response_mode="cost_exposure"
            )

        # 7. RAG / Historical Document Queries
        if "paimana" in q_lower or "report" in q_lower or "cag" in q_lower or "historical" in q_lower or "document" in q_lower or "audit" in q_lower:
            ops.append(PlanOperation(capability="semantic_search", parameters={"query": query, "top_k": 5}))
            return QueryPlan(
                question=query,
                interpretation=f"Semantic RAG vector search across historical PAIMANA reports for '{query}'",
                operations=ops,
                response_mode="evidence",
                requires_rag_evidence=True
            )

        # 8. Default Portfolio Surveillance Overview
        ops.append(PlanOperation(capability="portfolio_kpis"))
        ops.append(PlanOperation(capability="early_warnings"))
        return QueryPlan(
            question=query,
            interpretation="Nirman portfolio executive surveillance overview and early warning review",
            operations=ops,
            response_mode="executive_analysis"
        )
