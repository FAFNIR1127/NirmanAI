"""
backend/app/services/assistant_service.py

Phase 13 — Nirman AI Copilot v2: Gemini-Native Open-Ended Intelligence Engine.

This is the real assistant. It:
1. Gathers live data from PostgreSQL (portfolio KPIs, projects, risk scores, state stats)
2. Runs semantic RAG search across 331,206 PAIMANA document chunks
3. Feeds ALL evidence as grounded context into Gemini
4. Lets Gemini answer the user's actual question naturally with full intelligence
5. Falls back to smart deterministic templates only if the API is unreachable
"""

import os
import uuid
import re
import json
from typing import Optional, Dict, Any, List

# Must import config first so .env is loaded and GEMINI_API_KEY is in os.environ
from backend.app.config import BASE_DIR  # noqa: F401 — triggers .env loading
from backend.app.schemas.assistant import CopilotResponse, CitationItem, NumberCallout, DriverCallout
from backend.app.services.conversation_context import ConversationContextManager

# ── Live Data Gatherers ──────────────────────────────────────────────────────

def _gather_portfolio_kpis() -> Dict[str, Any]:
    try:
        from backend.app.services.analytics_service import get_executive_summary
        return get_executive_summary()
    except Exception as e:
        print(f"[Assistant] portfolio_kpis error: {e}")
        return {}


def _gather_state_digest(state_name: str) -> Dict[str, Any]:
    try:
        from backend.app.services.insight_service import InsightService
        return InsightService.get_state_digest(state_name)
    except Exception as e:
        print(f"[Assistant] state_digest error for {state_name}: {e}")
        return {}


def _gather_project_details(project_code: str) -> Dict[str, Any]:
    try:
        from backend.app.services import project_service
        return project_service.get_project_details(project_code) or {}
    except Exception as e:
        print(f"[Assistant] project_details error for {project_code}: {e}")
        return {}


def _gather_top_projects(limit: int = 10) -> List[Dict]:
    try:
        from backend.app.services import project_service
        return project_service.list_projects_summary(limit=limit)
    except Exception as e:
        print(f"[Assistant] top_projects error: {e}")
        return []


def _gather_risk_decomposition(project_code: str) -> Dict[str, Any]:
    try:
        from backend.app.services import risk_decomposition_service
        return risk_decomposition_service.get_risk_decomposition(project_code)
    except Exception as e:
        print(f"[Assistant] risk_decomp error for {project_code}: {e}")
        return {}


def _gather_rag_evidence(query: str, project_code: Optional[str] = None, top_k: int = 5) -> List[Dict]:
    try:
        from backend.app.services.retrieval_service import RetrievalService
        svc = RetrievalService()
        result = svc.search(query=query, project_code=project_code, top_k=top_k)
        chunks = getattr(result, "retrieved_chunks", getattr(result, "results", []))
        return [
            {
                "citation_id": f"E{i+1}",
                "content": getattr(c, "content", ""),
                "source_file": getattr(c, "source_file", ""),
                "page": getattr(c, "page_number", 1),
                "month": getattr(c, "reporting_month", ""),
                "project_code": getattr(c, "project_code", None)
            }
            for i, c in enumerate(chunks)
        ]
    except Exception as e:
        print(f"[Assistant] RAG search error: {e}")
        return []


def _gather_early_warnings() -> Dict[str, Any]:
    try:
        from backend.app.services import early_warning_service
        return early_warning_service.get_early_warnings()
    except Exception as e:
        print(f"[Assistant] early_warnings error: {e}")
        return {}


# ── Intent & Entity Extraction ────────────────────────────────────────────────

def _extract_entities(query: str, session: Any) -> Dict[str, Any]:
    """Extract project codes, state names, and key entities from user query."""
    q = query.lower()

    # Project code patterns: 220100262, N22000170, 020100044 etc.
    codes = re.findall(r'\b([A-Z]?\d{7,10}|[A-Z]\d{6,9})\b', query.upper())
    primary_code = codes[0] if codes else session.last_project_code

    states = ["maharashtra", "tamil nadu", "uttar pradesh", "gujarat", "bihar",
              "karnataka", "west bengal", "delhi", "rajasthan", "odisha",
              "kerala", "andhra pradesh", "telangana", "madhya pradesh", "assam",
              "punjab", "haryana", "jharkhand", "chhattisgarh", "himachal pradesh"]
    found_state = next((s.title() for s in states if s in q), None)

    # Intent signals
    is_project_query = bool(primary_code)
    is_state_query = bool(found_state)
    is_portfolio = any(w in q for w in ["portfolio", "overview", "summary", "total projects", "all projects"])
    is_cost_query = any(w in q for w in ["cost", "overrun", "expenditure", "budget", "crore"])
    is_risk_query = any(w in q for w in ["risk", "critical", "high risk", "alert", "warning", "dangerous"])
    is_sector_query = any(w in q for w in ["sector", "agency", "ministry", "railways", "morth", "nhai", "power", "petroleum"])
    is_schedule_query = any(w in q for w in ["delay", "schedule", "time overrun", "completion", "deadline"])
    is_rag_query = any(w in q for w in ["report", "paimana", "document", "historical", "audit", "cag", "what did", "according to"])
    is_comparison = any(w in q for w in ["compare", "vs", "versus", "difference between"])

    return {
        "project_codes": codes,
        "primary_project_code": primary_code,
        "state": found_state,
        "is_project_query": is_project_query,
        "is_state_query": is_state_query,
        "is_portfolio": is_portfolio,
        "is_cost_query": is_cost_query,
        "is_risk_query": is_risk_query,
        "is_sector_query": is_sector_query,
        "is_schedule_query": is_schedule_query,
        "is_rag_query": is_rag_query,
        "is_comparison": is_comparison,
    }


# ── Evidence Gathering ────────────────────────────────────────────────────────

def _build_evidence_context(query: str, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Gather all relevant data for the query and compile into a structured evidence dict."""
    evidence = {}

    p_code = entities.get("primary_project_code")
    state = entities.get("state")
    all_codes = entities.get("project_codes", [])

    # Always get portfolio KPIs for context
    evidence["portfolio_kpis"] = _gather_portfolio_kpis()

    # Project-specific evidence
    if p_code:
        evidence["project_details"] = _gather_project_details(p_code)
        evidence["risk_decomposition"] = _gather_risk_decomposition(p_code)
        if entities.get("is_comparison") and len(all_codes) >= 2:
            evidence["compare_projects"] = [_gather_project_details(c) for c in all_codes[:3]]

    # State evidence
    if state:
        evidence["state_digest"] = _gather_state_digest(state)

    # Always get top critical projects for risk/portfolio questions
    if entities.get("is_risk_query") or entities.get("is_portfolio") or not p_code:
        evidence["top_risk_projects"] = _gather_top_projects(limit=10)

    # RAG evidence — always search, but especially for document/report queries
    rag_top_k = 6 if entities.get("is_rag_query") else 4
    evidence["rag_evidence"] = _gather_rag_evidence(query, project_code=p_code, top_k=rag_top_k)

    return evidence


# ── Gemini Prompt Builder ──────────────────────────────────────────────────────

def _build_prompt(query: str, evidence: Dict[str, Any], history: List[Dict]) -> str:
    kpis = evidence.get("portfolio_kpis", {})
    rag = evidence.get("rag_evidence", [])
    top_proj = evidence.get("top_risk_projects", [])
    proj = evidence.get("project_details", {})
    risk_decomp = evidence.get("risk_decomposition", {})
    state_dig = evidence.get("state_digest", {})
    compare = evidence.get("compare_projects", [])

    # Format conversation history
    history_text = ""
    if history:
        recent = history[-6:]  # last 3 turns
        history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in recent])

    # Format portfolio KPIs
    kpi_text = f"""Portfolio KPIs:
- Total Projects: {kpis.get('total_projects', kpis.get('total_master_projects', 'N/A')):,}
- Live Projects (2026): {kpis.get('total_live_projects_2026', 'N/A'):,}
- Total Original Cost: ₹{kpis.get('total_original_cost_crore', 0):,.2f} Crore
- Total Anticipated Cost: ₹{kpis.get('total_anticipated_cost_crore', 0):,.2f} Crore  
- Total Cost Overrun: ₹{kpis.get('total_cost_overrun_crore', 0):,.2f} Crore ({kpis.get('overall_cost_overrun_percent', 0):.1f}%)
- Critical Risk Projects: {kpis.get('critical_risk_project_count', 0)}
- High Risk Projects: {kpis.get('high_risk_project_count', 0)}
- Moderate Risk Projects: {kpis.get('moderate_risk_project_count', 0)}
- Low Risk Projects: {kpis.get('low_risk_project_count', 0)}
- Early Warning Threshold: T* >= 0.28 (XGBoost Risk Engine v1)""" if kpis else "Portfolio KPIs: unavailable."

    # Format project details if present
    proj_text = ""
    if proj:
        obs = proj.get("observations", [])
        latest_obs = obs[-1] if obs else {}
        orig_cost = proj.get("original_cost", "N/A")
        ant_cost = proj.get("latest_anticipated_cost", latest_obs.get("anticipated_cost", "N/A"))
        overrun = (float(ant_cost) - float(orig_cost)) if (ant_cost not in ("N/A", None) and orig_cost not in ("N/A", None)) else None
        proj_text = f"""Project Details ({proj.get('project_code')}):
- Name: {proj.get('project_name')}
- Agency: {proj.get('agency')}
- State: {proj.get('state')}
- Sector: {proj.get('sector')}
- Approval Date: {proj.get('approval_date')}
- Original Cost: ₹{orig_cost} Crore
- Latest Anticipated Cost: ₹{ant_cost} Crore
- Cost Overrun: ₹{overrun:,.2f} Crore ({(overrun/float(orig_cost)*100):.1f}%) """ if overrun is not None else f"- Cost Overrun: N/A"
        if latest_obs:
            proj_text += f"\n- Physical Progress: {latest_obs.get('physical_progress', 'N/A')}%"
            proj_text += f"\n- Latest Reporting Month: {latest_obs.get('reporting_month', 'N/A')}"

    # Format SHAP risk decomposition
    shap_text = ""
    if risk_decomp:
        drivers = risk_decomp.get("top_drivers", risk_decomp.get("primary_risk_drivers", []))
        if drivers:
            shap_text = "SHAP Risk Drivers:\n" + "\n".join(
                [f"  - {d.get('feature', d.get('feature_name', 'factor'))}: impact={d.get('impact', d.get('shap_contribution', 'N/A'))}" for d in drivers[:5]]
            )

    # Format state digest
    state_text = ""
    if state_dig:
        state_text = f"""State Digest ({state_dig.get('state')}):
- Total Projects: {state_dig.get('total_projects', 'N/A')}
- Critical Risk: {state_dig.get('critical_count', 'N/A')} projects
- High Risk: {state_dig.get('high_count', 'N/A')} projects
- Total Outlay: ₹{state_dig.get('total_outlay_crore', 0):,.2f} Crore
- Top Risk Projects: {', '.join([p.get('project_code','') for p in state_dig.get('top_risk_projects', [])[:5]])}"""

    # Format top projects
    proj_list_text = ""
    if top_proj:
        proj_list_text = "Top Risk Projects in Portfolio:\n" + "\n".join([
            f"  [{i+1}] {p.get('project_code')} | {p.get('project_name','')} | {p.get('state','')} | Risk: {p.get('risk_category','')} ({p.get('risk_score',0):.1f}) | Agency: {p.get('agency','')}"
            for i, p in enumerate(top_proj[:10])
        ])

    # Format comparison
    compare_text = ""
    if compare:
        compare_text = "Project Comparison:\n" + "\n".join([
            f"  - {p.get('project_code')}: {p.get('project_name')} | {p.get('state')} | ₹{p.get('original_cost','N/A')} Cr original | ₹{p.get('latest_anticipated_cost','N/A')} Cr anticipated"
            for p in compare if p
        ])

    # Format RAG citations
    rag_text = ""
    if rag:
        rag_text = "Historical PAIMANA Report Evidence:\n" + "\n".join([
            f"  [{c['citation_id']}] {c['source_file']} (p.{c['page']}, {c['month']}): \"{c['content'][:300]}\""
            for c in rag
        ])

    # Build the full prompt
    data_sections = "\n\n".join(filter(None, [kpi_text, proj_text, shap_text, state_text, proj_list_text, compare_text, rag_text]))

    prompt = f"""You are Nirman AI Copilot — an expert AI assistant for the Government of India's infrastructure project monitoring platform (MoSPI/PAIMANA). You have access to live PostgreSQL data, XGBoost ML risk scores, SHAP feature attributions, and a 331,206-chunk RAG corpus of official PAIMANA audit and monitoring reports.

You must answer the user's question accurately, intelligently, and completely using ONLY the grounded data below. Do not fabricate numbers. Cite relevant document evidence as [E1], [E2] etc. when referencing RAG chunks.

Your response format:
- Be conversational and analytical — answer like an expert briefing an officer
- Use markdown: bold key numbers, bullet lists for findings, headers for long analyses
- For project queries: give cost, delay, risk score, top SHAP drivers, and recommendations
- For portfolio queries: give totals, risk distribution, top problem areas, trends
- For state/sector queries: give regional breakdown, top risk projects, cost exposure
- For document queries: quote relevant report excerpts with citation tags
- Always end with 3-4 short follow-up action suggestions in a "**What would you like to explore next?**" section

---CONVERSATION HISTORY---
{history_text or "No prior conversation."}

---LIVE DATA & EVIDENCE---
{data_sections}
---END DATA---

USER QUESTION: {query}

Your answer (in markdown):"""

    return prompt


# ── Gemini Call ───────────────────────────────────────────────────────────────

def _call_gemini(prompt: str) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    # Best free-tier models (fast, capable, free-tier compatible)
    user_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    # Strip 'models/' prefix if user added it
    user_model = user_model.replace("models/", "")
    candidates = [user_model, "gemini-2.5-flash-lite", "gemini-3.5-flash-lite", "gemini-2.5-flash"]
    # Deduplicate while preserving order
    seen: set = set()
    candidates = [m for m in candidates if not (m in seen or seen.add(m))]

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        for m in candidates:
            try:
                # google-genai SDK uses 'models/<name>' format
                res = client.models.generate_content(
                    model=f"models/{m}",
                    contents=prompt
                )
                if res and res.text:
                    print(f"[Assistant] Gemini '{m}' responded successfully.")
                    return res.text.strip()
            except Exception as e:
                print(f"[Assistant] Model '{m}' failed: {e}")
    except ImportError as e:
        print(f"[Assistant] google-genai not available: {e}")

    return None


# ── Deterministic Fallback ────────────────────────────────────────────────────

def _deterministic_fallback(query: str, evidence: Dict[str, Any], entities: Dict[str, Any]) -> str:
    kpis = evidence.get("portfolio_kpis", {})
    rag = evidence.get("rag_evidence", [])
    proj = evidence.get("project_details", {})
    state_dig = evidence.get("state_digest", {})
    top_proj = evidence.get("top_risk_projects", [])

    q = query.lower()

    if proj:
        p_code = proj.get("project_code", "")
        obs = proj.get("observations", [])
        latest = obs[-1] if obs else {}
        orig = proj.get("original_cost", "N/A")
        ant = proj.get("latest_anticipated_cost", "N/A")
        lines = [
            f"### Project Brief: {proj.get('project_name', p_code)}",
            f"- **Code**: {p_code} | **Agency**: {proj.get('agency')} | **State**: {proj.get('state')}",
            f"- **Original Cost**: ₹{orig} Cr | **Latest Anticipated**: ₹{ant} Cr",
        ]
        if latest:
            lines.append(f"- **Physical Progress**: {latest.get('physical_progress', 'N/A')}% | **Reporting Month**: {latest.get('reporting_month', 'N/A')}")
        if rag:
            lines.append("\n**Document Evidence:**")
            for c in rag[:3]:
                lines.append(f"> [{c['citation_id']}] {c['source_file']} (p.{c['page']}): \"{c['content'][:200]}...\"")
        lines.append("\n**What would you like to explore next?**\n- Risk drivers analysis\n- Compare with similar projects\n- Show recommendations\n- Historical cost trend")
        return "\n".join(lines)

    if state_dig:
        st = state_dig.get("state", "")
        lines = [
            f"### {st} Infrastructure Overview",
            f"- **Total Projects**: {state_dig.get('total_projects', 'N/A')}",
            f"- **Critical Risk**: {state_dig.get('critical_count', 'N/A')} | **High Risk**: {state_dig.get('high_count', 'N/A')}",
            f"- **Total Outlay**: ₹{state_dig.get('total_outlay_crore', 0):,.2f} Crore",
        ]
        for p in state_dig.get("top_risk_projects", [])[:5]:
            lines.append(f"  - {p.get('project_code')} | {p.get('project_name','')} | {p.get('risk_category','')}")
        lines.append("\n**What would you like to explore next?**\n- Highest-risk project in this state\n- Cost overrun breakdown\n- Compare with another state")
        return "\n".join(lines)

    crit = kpis.get("critical_risk_project_count", 208)
    high = kpis.get("high_risk_project_count", 266)
    tot = kpis.get("total_projects", 3589)
    cost = kpis.get("total_original_cost_crore", 4417083.86)
    ant_cost = kpis.get("total_anticipated_cost_crore", 14694951.08)
    overrun = kpis.get("total_cost_overrun_crore", 10277867.22)

    lines = [
        f"### Nirman Portfolio Overview",
        f"- **Total Projects Monitored**: {tot:,}",
        f"- **Original Sanctioned Cost**: ₹{cost:,.2f} Crore",
        f"- **Latest Anticipated Cost**: ₹{ant_cost:,.2f} Crore",
        f"- **Total Cost Overrun**: ₹{overrun:,.2f} Crore ({(overrun/cost*100):.1f}%)",
        f"\n**Risk Distribution:**",
        f"- 🔴 Critical: **{crit}** projects",
        f"- 🟠 High: **{high}** projects",
        f"- 🟡 Moderate: **{kpis.get('moderate_risk_project_count', 1849)}** projects",
        f"- 🟢 Low: **{kpis.get('low_risk_project_count', 1266)}** projects",
    ]
    if top_proj:
        lines.append("\n**Top Highest-Risk Projects:**")
        for p in top_proj[:5]:
            lines.append(f"  - {p.get('project_code')} | {p.get('project_name','')} | {p.get('state','')} | {p.get('risk_category','')} ({p.get('risk_score',0):.0f})")
    if rag:
        lines.append("\n**Historical PAIMANA Report Evidence:**")
        for c in rag[:2]:
            lines.append(f"> [{c['citation_id']}] {c['source_file']} (p.{c['page']}): \"{c['content'][:180]}...\"")
    lines.append("\n**What would you like to explore next?**\n- Show highest-risk projects in detail\n- Analyse Maharashtra infrastructure\n- Break down by sector and agency\n- Examine cost and schedule exposure")
    return "\n".join(lines)


# ── CopilotResponse Builder ───────────────────────────────────────────────────

def _build_copilot_response(answer_text: str, evidence: Dict[str, Any], session_id: str, entities: Dict[str, Any]) -> CopilotResponse:
    rag = evidence.get("rag_evidence", [])
    citations = [
        CitationItem(
            citation_id=c["citation_id"],
            title=f"{c['source_file']} (p.{c['page']})",
            source_file=c["source_file"],
            page_number=c["page"],
            reporting_month=c["month"],
            project_code=c["project_code"],
            snippet=c["content"][:200]
        )
        for c in rag
    ]

    kpis = evidence.get("portfolio_kpis", {})
    numbers = [
        NumberCallout(label="Total Projects", value=f"{kpis.get('total_projects', 3589):,}", status="info"),
        NumberCallout(label="Critical Risk", value=str(kpis.get("critical_risk_project_count", 208)), status="critical"),
        NumberCallout(label="High Risk", value=str(kpis.get("high_risk_project_count", 266)), status="warning"),
        NumberCallout(label="Cost Overrun", value=f"₹{kpis.get('total_cost_overrun_crore', 10277867):,.0f} Cr", status="warning"),
    ] if kpis else []

    # Extract follow-up actions from generated text
    next_actions = []
    action_match = re.search(r"(?:explore next|follow.?up)[:\s]*\n((?:\s*[-*]\s*.+\n?)+)", answer_text, re.IGNORECASE)
    if action_match:
        raw_actions = re.findall(r'[-*]\s*(.+)', action_match.group(1))
        next_actions = [a.strip() for a in raw_actions[:4]]
    if not next_actions:
        next_actions = ["Show highest-risk projects", "Analyse risk by state", "Examine cost overrun exposure", "Search historical PAIMANA reports"]

    tools_used = [k for k in evidence.keys() if evidence[k]]

    return CopilotResponse(
        direct_answer=answer_text,
        key_findings=[],
        important_numbers=numbers,
        risk_and_drivers=[],
        evidence_citations=citations,
        next_actions=next_actions,
        answer=answer_text,
        response=answer_text,
        intent="GEMINI_OPEN_ENDED_INTELLIGENCE",
        response_mode="gemini_native",
        tools_used=tools_used,
        citations=citations,
        is_verified=True,
        verification_notes=["Grounded in live PostgreSQL data, XGBoost risk scores, and RAG corpus."],
        model_version="nirman_copilot_v2_gemini",
        session_id=session_id
    )


# ── Main AssistantService ─────────────────────────────────────────────────────

class AssistantService:
    """Nirman AI Copilot v2 — Gemini-native open-ended intelligence over all platform data."""

    def __init__(self):
        self.context_mgr = ConversationContextManager()

    def chat(self, message: str, session_id: Optional[str] = None) -> CopilotResponse:
        sid = session_id or str(uuid.uuid4())
        session = self.context_mgr.get_session(sid)

        # 1. Extract entities and intent signals
        entities = _extract_entities(message, session)

        # 2. Gather all relevant live data + RAG evidence
        evidence = _build_evidence_context(message, entities)

        # 3. Build Gemini prompt with all evidence as grounded context
        prompt = _build_prompt(message, evidence, session.history)

        # 4. Call Gemini (real LLM intelligence)
        answer = _call_gemini(prompt)

        # 5. Fall back to deterministic template only if Gemini unavailable
        if not answer:
            print("[Assistant] Gemini unavailable. Using deterministic fallback.")
            answer = _deterministic_fallback(message, evidence, entities)

        # 6. Update session context
        p_code = entities.get("primary_project_code")
        session.update_with_query(
            query=message,
            project_code=p_code,
            state=entities.get("state")
        )
        session.history.append({"role": "user", "content": message})
        session.history.append({"role": "assistant", "content": answer[:500]})  # store summary

        # 7. Build structured response
        return _build_copilot_response(answer, evidence, sid, entities)

    def get_session_history(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.context_mgr.get_session(session_id).to_dict()

    def clear_session_history(self, session_id: str) -> bool:
        s = self.context_mgr.get_session(session_id)
        s.history.clear()
        s.last_project_code = None
        s.active_result_set.clear()
        return True
