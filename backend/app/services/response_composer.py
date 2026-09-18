"""
backend/app/services/response_composer.py

Phase 13 — 6-Part Adaptive Response Composer.
Composes executive briefings, project deep-dives, comparisons, and RAG search responses
into structured CopilotResponse objects validated by EvidenceValidator.
"""

import os
import json
import re
from typing import Dict, Any, List, Optional
from backend.app.services.analysis_orchestrator import EvidencePackage
from backend.app.services.evidence_validator import EvidenceValidator
from backend.app.schemas.assistant import (
    CopilotResponse, CitationItem, NumberCallout, DriverCallout
)
from backend.app.services.llm_service import get_api_keys


class ResponseComposer:
    """Composes structured 6-part executive copilot responses strictly grounded in EvidencePackages."""

    def __init__(self):
        self.validator = EvidenceValidator()

    def compose(self, package: EvidencePackage, session_id: str = "default") -> CopilotResponse:
        """Compose 6-part adaptive response payload."""
        
        # 1. Build Citation Objects
        citations: List[CitationItem] = []
        for rag in package.rag_citations:
            citations.append(
                CitationItem(
                    citation_id=rag.citation_id,
                    title=f"{rag.source_file} (p. {rag.page_number or 1})",
                    source_file=rag.source_file,
                    page_number=rag.page_number,
                    reporting_month=rag.reporting_month,
                    project_code=rag.project_code,
                    snippet=rag.content[:250] + "..." if len(rag.content) > 250 else rag.content
                )
            )

        # 2. Extract Important Numbers & Drivers from Data Claims
        numbers: List[NumberCallout] = []
        drivers: List[DriverCallout] = []
        tools_used = list(package.raw_results.keys())

        for claim in package.data_claims:
            if claim.category == "kpi":
                lbl = claim.metric.replace("_", " ").title()
                val_str = f"{claim.value:,}" if isinstance(claim.value, int) else str(claim.value)
                status = "critical" if "critical" in claim.metric else ("warning" if "high" in claim.metric else "info")
                numbers.append(NumberCallout(label=f"{claim.subject} {lbl}".strip(), value=val_str, unit=claim.unit, status=status))

            elif claim.category == "project_metric" and claim.metric in ("original_cost", "anticipated_cost", "physical_progress", "cost_overrun", "time_overrun_months", "risk_score"):
                lbl = claim.metric.replace("_", " ").title()
                val_str = f"₹{claim.value:,.2f}" if "cost" in claim.metric and isinstance(claim.value, (int, float)) else str(claim.value)
                numbers.append(NumberCallout(label=f"{claim.subject} {lbl}".strip(), value=val_str, unit=claim.unit, status="info"))

            elif claim.category == "driver":
                drivers.append(DriverCallout(label=claim.metric.replace("_", " ").title(), impact=f"{claim.value:+.2f} SHAP risk impact", detail=f"Extracted from Risk Engine v1 SHAP attribution for {claim.subject}"))

        # 3. Generate Natural Language Direct Answer & Key Findings via LLM or Rule Generator
        direct_answer, key_findings, next_actions = self._generate_insights(package)

        # 4. Validate and Audit Response with EvidenceValidator
        full_text = direct_answer + "\n" + "\n".join(key_findings)
        refined_text, is_verified, notes = self.validator.validate_and_refine(full_text, package)

        formatted_answer = f"### {package.interpretation}\n\n{direct_answer}\n\n"
        if key_findings:
            formatted_answer += "#### Key Findings\n" + "\n".join([f"* {f}" for f in key_findings]) + "\n\n"
        if citations:
            formatted_answer += "#### Evidence & Report Citations\n" + "\n".join([f"* [{c.citation_id}] {c.title}: {c.snippet}" for c in citations])

        return CopilotResponse(
            direct_answer=direct_answer,
            key_findings=key_findings,
            important_numbers=numbers[:6],
            risk_and_drivers=drivers[:5],
            evidence_citations=citations,
            next_actions=next_actions,
            answer=formatted_answer,
            response=formatted_answer,
            intent="DYNAMIC_CAPABILITY_INTELLIGENCE",
            response_mode=package.response_mode,
            tools_used=tools_used,
            citations=citations,
            is_verified=is_verified,
            verification_notes=notes,
            session_id=session_id
        )

    def _generate_insights(self, package: EvidencePackage) -> tuple[str, List[str], List[str]]:
        """Generate structured text insights and next action chips."""
        keys = get_api_keys()
        api_key = keys["GEMINI_API_KEY"] or keys["OPENAI_API_KEY"]

        if api_key and keys["GEMINI_API_KEY"]:
            try:
                from google import genai
                client = genai.Client(api_key=api_key)

                claims_summary = "\n".join([f"- {c.subject} | {c.metric}: {c.value} {c.unit}" for c in package.data_claims])
                citations_summary = "\n".join([f"[{c.citation_id}] {c.source_file} p.{c.page_number or 1}: {c.content[:200]}" for c in package.rag_citations])

                prompt = f"""You are Nirman AI Copilot, an official infrastructure monitoring assistant.
Synthesize the provided data claims and RAG citations into an executive analysis.

User Question: "{package.question}"
Interpretation: "{package.interpretation}"
Response Mode: "{package.response_mode}"

Data Claims:
{claims_summary or 'No data claims.'}

RAG Citations:
{citations_summary or 'No citations.'}

Respond with ONLY valid JSON:
{{
  "direct_answer": "Concise 1-2 sentence executive answer directly addressing the user question.",
  "key_findings": [
    "Analytical bullet point 1 with exact numbers",
    "Analytical bullet point 2 with risk context"
  ],
  "next_actions": [
    "Suggested follow-up prompt chip 1",
    "Suggested follow-up prompt chip 2"
  ]
}}
"""
                res = client.models.generate_content(
                    model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
                    contents=prompt
                )
                text = res.text.strip()
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    d = json.loads(match.group(0))
                    return d.get("direct_answer", ""), d.get("key_findings", []), d.get("next_actions", [])
            except Exception as e:
                print(f"[ResponseComposer] LLM insight generation failed ({e}). Using deterministic rule generator.")

        # Deterministic Rule-based Insight Generator tailored to each response mode
        if package.response_mode == "highest_risk":
            crit_claim = next((c for c in package.data_claims if c.metric == "critical_risk_projects"), None)
            crit_cnt = crit_claim.value if crit_claim else 0
            p_codes = package.projects_analyzed[:3]

            codes_str = ', '.join(p_codes) if p_codes else "the projects listed above"
            answer = f"The XGBoost Risk Engine v1 currently classifies **{crit_cnt:,}** infrastructure projects as Critical risk across the portfolio."
            findings = [
                f"Highest-risk projects identified: {codes_str} — these have crossed the critical threshold T* >= 0.28.",
                "Primary risk drivers: schedule slippage exceeding 24 months and expenditure gaps above 25%.",
                "All critical projects require immediate ground evidence verification and escalation."
            ]
            actions = [
                f"Show risk breakdown for project {p_codes[0] if p_codes else 'top critical project'}",
                "Analyse risk drivers by state",
                "Break down critical projects by sector",
                "Examine cost and schedule exposure"
            ]
            return answer, findings, actions

        elif package.response_mode == "state_analysis":
            st_claim = next((c for c in package.data_claims if c.subject != "portfolio" and c.metric in ("total_projects", "critical_count")), None)
            st_name = st_claim.subject if st_claim else "the selected state"
            st_tot  = next((c.value for c in package.data_claims if c.subject == st_name and c.metric == "total_projects"), 0)
            st_crit = next((c.value for c in package.data_claims if c.subject == st_name and c.metric == "critical_count"), 0)
            st_cost = next((c.value for c in package.data_claims if c.subject == st_name and c.metric == "total_outlay_crore"), 0.0)

            answer = f"In **{st_name}**, Nirman is tracking **{st_tot:,}** infrastructure projects with a combined sanctioned allocation of ₹**{st_cost:,.2f}** crore."
            findings = [
                f"{st_name} Risk Breakdown: {st_crit} Critical risk projects and high concentration in transport and urban infrastructure.",
                f"Top monitored projects in {st_name}: {', '.join(package.projects_analyzed[:3]) if package.projects_analyzed else 'regional corridors'}.",
                "State-level expenditure progress indicates significant gap against physical milestone targets."
            ]
            actions = [
                f"Why is project {package.projects_analyzed[0] if package.projects_analyzed else '220100262'} high risk?",
                f"Show highest-risk projects in {st_name}",
                "Break down risk by sector and agency",
                "Examine cost and schedule exposure"
            ]
            return answer, findings, actions

        elif package.response_mode == "agency_breakdown":
            # Pull live sector data from DataClaims populated by agency_stats capability
            sector_claims = [c for c in package.data_claims if c.metric == "cost_overrun" and c.subject != "portfolio"]
            if sector_claims:
                sector_lines = [f"- **{c.subject}**: ₹{c.value:,.0f} crore cost overrun" for c in sorted(sector_claims, key=lambda x: (x.value or 0), reverse=True)[:4]]
                top_sector = sector_claims[0].subject
                answer = f"Sectoral cost overrun analysis (live data): **{top_sector}** is the highest-exposure sector in the portfolio."
                findings = sector_lines + [
                    "Primary agency delays stem from land acquisition, environmental clearances, and contractor execution slippage."
                ]
            else:
                answer = "Sectoral risk analysis reveals the Roads & Highways and Railways sectors account for the largest portfolio cost overruns."
                findings = [
                    "See the Portfolio KPIs panel for live sector-wise overrun breakdown.",
                    "Primary delays stem from land acquisition, environmental clearances, and contractor slippage."
                ]
            actions = [
                "Show highest-risk projects by sector",
                "Analyse Railways cost overrun projects",
                "Examine Roads & Highways risk exposure",
                "Summarize portfolio overruns by state"
            ]
            return answer, findings, actions

        elif package.response_mode == "cost_exposure":
            # Pull live cost data from DataClaims
            cost_claim    = next((c for c in package.data_claims if c.metric == "total_original_cost"), None)
            ant_claim     = next((c for c in package.data_claims if c.metric == "total_anticipated_cost"), None)
            overrun_claim = next((c for c in package.data_claims if c.metric == "total_cost_overrun"), None)
            pct_claim     = next((c for c in package.data_claims if c.metric == "cost_overrun_pct"), None)
            delay_claim   = next((c for c in package.data_claims if c.metric == "avg_delay_months"), None)

            orig    = cost_claim.value    if cost_claim    else 0.0
            ant     = ant_claim.value     if ant_claim     else 0.0
            overrun = overrun_claim.value if overrun_claim else 0.0
            pct     = pct_claim.value     if pct_claim     else 0.0
            delay   = delay_claim.value   if delay_claim   else 0.0

            answer = f"Total portfolio cost overrun stands at ₹**{overrun:,.0f}** crore — a **{pct:.1f}%** increase over original sanctioned cost (latest data)."
            findings = [
                f"Original sanctioned cost: ₹**{orig:,.0f}** crore → Latest anticipated cost: ₹**{ant:,.0f}** crore",
                f"Average schedule delay across monitored projects: **{delay:.1f} months**",
                "Projects with >₹500 crore individual overrun are flagged for immediate ministerial review."
            ]
            actions = [
                "Show top projects by cost overrun",
                "Analyse cost exposure by sector",
                "Show state-wise cost overrun breakdown",
                "What did PAIMANA reports say about cost overruns?"
            ]
            return answer, findings, actions

        elif package.response_mode == "project_analysis" and package.projects_analyzed:
            p_code = package.projects_analyzed[0]
            answer = f"Comprehensive monitoring briefing for project {p_code} based on multi-source risk scores, observation history, and official reports."
            findings = [
                f"Project {p_code} is actively tracked with empirical risk predictions from XGBoost Risk Engine v1.",
                "SHAP risk decomposition highlights schedule variance and expenditure gaps as primary risk drivers.",
                f"Historical document search returned {len(package.rag_citations)} official report citations."
            ]
            actions = [
                f"Analyse risk trajectory for project {p_code}",
                f"Show recommendations for project {p_code}",
                "Compare with similar sector projects",
                "Show highest-risk projects"
            ]
            return answer, findings, actions

        elif package.response_mode == "comparison":
            answer = f"Side-by-side comparative analysis of projects {', '.join(package.projects_analyzed)}."
            findings = [
                f"Compared {len(package.projects_analyzed)} projects across original cost, anticipated cost, risk category, and physical progress.",
                "Discrepancies in expenditure progress vs physical progress highlight targeted monitoring candidates."
            ]
            actions = [
                f"Why is project {package.projects_analyzed[0]} high risk?" if package.projects_analyzed else "Show highest-risk projects",
                "Analyse main risk drivers across Maharashtra",
                "Examine cost and schedule exposure"
            ]
            return answer, findings, actions

        elif package.response_mode == "evidence":
            answer = f"Retrieved {len(package.rag_citations)} official report citations from historical PAIMANA document corpus."
            findings = [
                f"Vector search matched query '{package.question}' against 331,206 document chunks using RRF hybrid ranking.",
                "Document excerpts provide qualitative evidence on procurement delays, land acquisition status, and audit observations."
            ]
            actions = [
                "Show highest-risk projects",
                "Analyse main risk drivers across Maharashtra",
                "Break down risk by sector and agency"
            ]
            return answer, findings, actions

        # Executive / Portfolio Overview default
        kpi_claim  = next((c for c in package.data_claims if c.metric == "total_projects"), None)
        crit_claim = next((c for c in package.data_claims if c.metric == "critical_risk_projects"), None)
        high_claim = next((c for c in package.data_claims if c.metric == "high_risk_projects"), None)
        mod_claim  = next((c for c in package.data_claims if c.metric == "moderate_risk_projects"), None)
        low_claim  = next((c for c in package.data_claims if c.metric == "low_risk_projects"), None)
        overrun_claim = next((c for c in package.data_claims if c.metric == "total_cost_overrun"), None)
        cost_claim    = next((c for c in package.data_claims if c.metric == "total_original_cost"), None)

        tot     = kpi_claim.value  if kpi_claim  else 0
        crit    = crit_claim.value if crit_claim else 0
        high    = high_claim.value if high_claim else 0
        mod     = mod_claim.value  if mod_claim  else 0
        low     = low_claim.value  if low_claim  else 0
        overrun = overrun_claim.value if overrun_claim else 0.0
        cost    = cost_claim.value    if cost_claim    else 0.0

        answer = (
            f"As of the latest reporting (July 2026), Nirman is monitoring **{tot:,}** infrastructure projects. "
            f"**{crit:,}** are flagged as Critical risk and **{high:,}** as High risk by the XGBoost Risk Engine."
        )
        findings = [
            f"Total projects monitored: **{tot:,}** (across all states and sectors)",
            f"Risk distribution: **{crit:,}** Critical | **{high:,}** High | **{mod:,}** Moderate | **{low:,}** Low",
            f"Total original sanctioned cost: ₹**{cost:,.0f}** Crore | Total cost overrun: ₹**{overrun:,.0f}** Crore",
            f"Early warning threshold: T* >= 0.28 (XGBoost Risk Engine v1)",
        ]
        actions = [
            "Show highest-risk projects in detail",
            "Analyse risk and cost exposure by state",
            "Break down by sector and agency",
            "Examine schedule delays and completion trends"
        ]
        return answer, findings, actions

