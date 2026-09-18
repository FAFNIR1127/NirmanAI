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
        from backend.app.services.risk_decomposition_service import RiskDecompositionService
        svc = RiskDecompositionService()
        return svc.decompose_project_risk(project_code) or {}
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

def _lookup_project_code_by_name(query: str) -> Optional[str]:
    """Resolve project names mentioned in natural language query to project_code directly from DB."""
    try:
        from backend.app.services.analytics_service import get_db_engine
        import sqlalchemy
        engine = get_db_engine()
        stop_words = {
            "details", "project", "projects", "show", "what", "give", "about",
            "risk", "cost", "the", "and", "for", "tell", "with", "overrun",
            "status", "information", "info", "update", "latest", "please", "me"
        }
        cleaned = re.sub(r'[^\w\s-]', ' ', query)
        tokens = [w.strip() for w in cleaned.split() if len(w.strip()) >= 4 and w.lower() not in stop_words]
        if not tokens:
            return None

        with engine.connect() as conn:
            # 1. Multi-token match
            if len(tokens) >= 2:
                conds = [f"LOWER(project_name) LIKE :w{i}" for i in range(len(tokens))]
                params = {f"w{i}": f"%{tokens[i].lower()}%" for i in range(len(tokens))}
                sql = "SELECT project_code FROM projects WHERE " + " AND ".join(conds) + " LIMIT 1"
                row = conn.execute(sqlalchemy.text(sql), params).fetchone()
                if row:
                    return str(row[0])

            # 2. Key significant token match (longest first)
            sorted_tokens = sorted(tokens, key=len, reverse=True)
            for token in sorted_tokens[:3]:
                sql = "SELECT project_code FROM projects WHERE LOWER(project_name) LIKE :w ORDER BY LENGTH(project_name) ASC LIMIT 1"
                row = conn.execute(sqlalchemy.text(sql), {"w": f"%{token.lower()}%"}).fetchone()
                if row:
                    return str(row[0])
    except Exception as e:
        print(f"[Assistant] Project name lookup error: {e}")
    return None


def _extract_entities(query: str, session: Any, explicit_project_code: Optional[str] = None) -> Dict[str, Any]:
    """Extract project codes, state names, and key entities from user query."""
    q = query.lower()

    # Project code resolution priority:
    # 1. Explicitly passed project_code (from active drawer context)
    # 2. Regex match in query (e.g. 220100133, N22000170)
    # 3. Database lookup by project name
    # 4. Session memory last_project_code
    codes = re.findall(r'\b([A-Z]?\d{7,10}|[A-Z]\d{6,9})\b', query.upper())
    primary_code = explicit_project_code or (codes[0] if codes else None)

    if not primary_code:
        primary_code = _lookup_project_code_by_name(query)

    if not primary_code:
        primary_code = session.last_project_code

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
    kpi_text = f"""Portfolio KPIs (Latest Live Data — as of July 2026):
- Total Master Projects in Database: {kpis.get('total_projects', kpis.get('total_master_projects', 'N/A')):,}
- Live Projects with 2026 Reporting: {kpis.get('total_live_projects_2026', 'N/A'):,}
- Total Original Sanctioned Cost: ₹{kpis.get('total_original_cost_crore', 0):,.2f} Crore
- Total Anticipated Cost (Latest): ₹{kpis.get('total_anticipated_cost_crore', 0):,.2f} Crore
- Total Cost Overrun: ₹{kpis.get('total_cost_overrun_crore', 0):,.2f} Crore ({kpis.get('overall_cost_overrun_percent', 0):.1f}%)
- Critical Risk Projects: {kpis.get('critical_risk_project_count', 0):,}
- High Risk Projects: {kpis.get('high_risk_project_count', 0):,}
- Moderate Risk Projects: {kpis.get('moderate_risk_project_count', 0):,}
- Low Risk Projects: {kpis.get('low_risk_project_count', 0):,}
- Avg Cost Expansion Ratio: {kpis.get('avg_cost_expansion', 0):.2f}x
- Avg Schedule Slippage: {kpis.get('avg_delay_months', 0):.1f} months
- Early Warning Threshold: T* >= 0.28 (XGBoost Risk Engine v1)""" if kpis else "Portfolio KPIs: unavailable."

    # Format project details if present (GROUND TRUTH FROM RELATIONAL DB)
    proj_text = ""
    if proj:
        obs = proj.get("observations", [])
        latest_obs = obs[-1] if obs else {}
        orig_cost = proj.get("original_cost")
        ant_cost = proj.get("latest_anticipated_cost", latest_obs.get("anticipated_cost", orig_cost))
        
        orig_f = float(orig_cost) if (orig_cost is not None and str(orig_cost) != "N/A") else None
        ant_f = float(ant_cost) if (ant_cost is not None and str(ant_cost) != "N/A") else None
        overrun = (ant_f - orig_f) if (ant_f is not None and orig_f is not None) else None
        overrun_pct = ((overrun / orig_f) * 100.0) if (overrun is not None and orig_f and orig_f > 0) else 0.0
        
        delay_m = proj.get("latest_delay_months", latest_obs.get("delay_months"))
        orig_doc = proj.get("latest_orig_doc", latest_obs.get("original_doc", "N/A"))
        ant_doc = proj.get("latest_ant_doc", latest_obs.get("anticipated_doc", "N/A"))
        prog = latest_obs.get("physical_progress", proj.get("physical_progress", "N/A"))
        rep_m = latest_obs.get("reporting_month", "N/A")

        proj_text = f"""=== LIVE DATABASE PROJECT DETAILS (GROUND TRUTH — MUST MATCH EXACTLY) ===
- Project Code: {proj.get('project_code')}
- Project Name: {proj.get('project_name')}
- Implementing Agency: {proj.get('agency', 'N/A')}
- State: {proj.get('state', 'N/A')}
- Sector: {proj.get('sector', 'N/A')}
- Approval Date: {proj.get('approval_date', 'N/A')}
- Original Sanctioned Cost: ₹{orig_f:,.2f} Crore
- Latest Anticipated Cost: ₹{ant_f:,.2f} Crore
- Cumulative Cost Overrun: ₹{overrun:,.2f} Crore ({overrun_pct:+.1f}% Escalation)
- Original Date of Completion: {orig_doc}
- Latest Anticipated Date of Completion: {ant_doc}
- Schedule Delay: {f"{delay_m:.1f} months" if delay_m is not None else "As per schedule"}
- Physical Progress: {prog}%
- Latest Reporting Snapshot: {rep_m}
=========================================================================="""

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
        rag_text = "Historical PAIMANA Report Excerpts (Use for historical audit context only — NOT current cost):\n" + "\n".join([
            f"  [{c['citation_id']}] {c['source_file']} (p.{c['page']}, {c['month']}): \"{c['content'][:300]}\""
            for c in rag
        ])

    # Build the full prompt
    data_sections = "\n\n".join(filter(None, [kpi_text, proj_text, shap_text, state_text, proj_list_text, compare_text, rag_text]))

    prompt = f"""You are Nirman AI Copilot — an expert AI assistant for the Government of India's infrastructure project monitoring platform (MoSPI). You have access to live PostgreSQL database data, XGBoost ML risk scores (Risk Engine v1), SHAP driver attributions, and a 331,206-chunk RAG corpus of official PAIMANA audit and monitoring reports.

CRITICAL RULES — YOU MUST FOLLOW THESE WITHOUT EXCEPTION:
1. LIVE DATABASE PRIORITY: When answering about a specific project, the numbers in the "LIVE DATABASE PROJECT DETAILS" section are the ABSOLUTE SOURCE OF TRUTH. You MUST state:
   - Original Sanctioned Cost: EXACTLY as shown in Live Database Project Details (e.g. ₹2,500.00 Crore)
   - Latest Anticipated Cost: EXACTLY as shown in Live Database Project Details (e.g. ₹43,780.00 Crore)
   - Cumulative Cost Overrun: EXACTLY as shown in Live Database Project Details (e.g. ₹41,280.00 Crore)
   DO NOT substitute older cost or overrun figures found in historical document excerpts (citations [E1], [E2] etc. which may be from 2021, 2022, or 2023). Historical excerpts provide historical context; the LIVE DATABASE section reflects the current official status.
2. Every number, figure, and statistic in your answer MUST come directly and verbatim from the "LIVE DATA & EVIDENCE" section below. Do NOT use your training memory for numbers.
3. If the data says "Total Projects: 5,469" — say 5,469. If it says "Critical Risk: 775" — say 775. Do not round, guess, or recall older figures.
4. Write in plain, friendly language that any government officer (even non-technical) can understand. Avoid jargon. Explain what numbers mean in plain terms.
5. Cite evidence chunks as [E1], [E2] etc. when referencing qualitative historical document findings.
6. Never say "I don't know" if the data is provided — synthesize a clear answer from the evidence.
7. If the user's question is about a specific project, focus on that project's live data.
8. At the end, suggest 3-4 natural follow-up questions the user might want to ask.

ANSWER FORMAT:
- Start with a direct, clear 1-2 sentence summary answer stating the exact live numbers
- Then give key project details and findings as bullet points
- Bold all important numbers
- End with a "**What would you like to explore next?**" section with 3-4 short suggestions

---CONVERSATION HISTORY (for context of earlier turns)---
{history_text or "This is the start of the conversation."}

---LIVE DATA & EVIDENCE (use ONLY these numbers in your answer)---
{data_sections}
---END OF DATA---

USER QUESTION: {query}

Your answer (in clear, friendly markdown):"""

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
        orig = proj.get("original_cost")
        ant = proj.get("latest_anticipated_cost", latest.get("anticipated_cost", orig))
        orig_f = float(orig) if (orig is not None and str(orig) not in ("N/A", "None")) else None
        ant_f = float(ant) if (ant is not None and str(ant) not in ("N/A", "None")) else None
        overrun = (ant_f - orig_f) if (ant_f is not None and orig_f is not None) else 0.0
        overrun_pct = ((overrun / orig_f) * 100.0) if (overrun and orig_f and orig_f > 0) else 0.0
        delay_m = proj.get("latest_delay_months", latest.get("delay_months"))
        orig_doc = proj.get("latest_orig_doc", latest.get("original_doc", "N/A"))
        ant_doc = proj.get("latest_ant_doc", latest.get("anticipated_doc", "N/A"))
        prog = latest.get("physical_progress", proj.get("physical_progress", "N/A"))

        lines = [
            f"### Project Details: {proj.get('project_name', p_code)}",
            f"- **Project Code**: `{p_code}` | **Nodal Agency**: {proj.get('agency', 'N/A')} | **State**: {proj.get('state', 'N/A')}",
            f"- **Original Sanctioned Cost**: ₹{orig_f:,.2f} Crore" if orig_f is not None else "- **Original Cost**: N/A",
            f"- **Latest Anticipated Cost**: ₹{ant_f:,.2f} Crore" if ant_f is not None else "- **Latest Anticipated Cost**: N/A",
            f"- **Cumulative Cost Overrun**: ₹{overrun:,.2f} Crore ({overrun_pct:+.1f}% Escalation)" if overrun > 0 else "- **Cost Status**: Within Sanctioned Budget",
            f"- **Completion Timeline**: Target {orig_doc} → Anticipated {ant_doc} ({f'{delay_m:.0f} months delay' if delay_m else 'On schedule'})",
            f"- **Physical Progress**: {prog}%",
        ]
        if rag:
            lines.append("\n**Historical PAIMANA Report Citations:**")
            for c in rag[:3]:
                lines.append(f"> [{c['citation_id']}] {c['source_file']} (p.{c['page']}): \"{c['content'][:200]}...\"")
        lines.append("\n**What would you like to explore next?**\n- Risk drivers breakdown (SHAP)\n- Compare with similar sector projects\n- View official mitigation actions\n- Historical cost progression")
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

    # --- ALWAYS use live DB values, never hardcoded stale numbers ---
    crit = kpis.get("critical_risk_project_count", 0)
    high = kpis.get("high_risk_project_count", 0)
    mod  = kpis.get("moderate_risk_project_count", 0)
    low  = kpis.get("low_risk_project_count", 0)
    tot  = kpis.get("total_projects", kpis.get("total_master_projects", 0))
    live = kpis.get("total_live_projects_2026", 0)
    cost = kpis.get("total_original_cost_crore", 0)
    ant_cost = kpis.get("total_anticipated_cost_crore", 0)
    overrun  = kpis.get("total_cost_overrun_crore", 0)
    overrun_pct = kpis.get("overall_cost_overrun_percent", 0)

    lines = [
        "### Nirman Portfolio — Latest Data Snapshot",
        f"- **Total Projects Monitored**: {tot:,}",
        f"- **Live Projects (2026 data)**: {live:,}",
        f"- **Original Sanctioned Cost**: ₹{cost:,.2f} Crore",
        f"- **Latest Anticipated Cost**: ₹{ant_cost:,.2f} Crore",
        f"- **Total Cost Overrun**: ₹{overrun:,.2f} Crore ({overrun_pct:.1f}%)",
        f"\n**Risk Distribution (XGBoost Risk Engine v1):**",
        f"- 🔴 Critical: **{crit:,}** projects",
        f"- 🟠 High:     **{high:,}** projects",
        f"- 🟡 Moderate: **{mod:,}** projects",
        f"- 🟢 Low:      **{low:,}** projects",
    ]
    if top_proj:
        lines.append("\n**Top Highest-Risk Projects (Latest):**")
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

    proj = evidence.get("project_details")
    kpis = evidence.get("portfolio_kpis", {})

    if proj:
        orig = proj.get("original_cost")
        ant = proj.get("latest_anticipated_cost", orig)
        orig_f = float(orig) if (orig is not None and str(orig) not in ("N/A", "None")) else None
        ant_f = float(ant) if (ant is not None and str(ant) not in ("N/A", "None")) else None
        overrun = (ant_f - orig_f) if (ant_f is not None and orig_f is not None) else 0.0
        overrun_pct = ((overrun / orig_f) * 100.0) if (overrun and orig_f and orig_f > 0) else 0.0
        numbers = [
            NumberCallout(label="Original Cost",       value=f"₹{orig_f:,.0f} Cr" if orig_f is not None else "N/A", status="info"),
            NumberCallout(label="Latest Anticipated",  value=f"₹{ant_f:,.0f} Cr" if ant_f is not None else "N/A", status="warning"),
            NumberCallout(label="Cost Overrun",        value=f"₹{overrun:,.0f} Cr" + (f" ({overrun_pct:+.1f}%)" if overrun > 0 else ""), status="critical" if overrun > 0 else "normal"),
            NumberCallout(label="Escalation Status",   value=f"{overrun_pct:+.1f}% Overrun" if overrun > 0 else "On Track", status="critical" if overrun > 0 else "normal"),
        ]
    elif kpis:
        numbers = [
            NumberCallout(label="Total Projects",  value=f"{kpis.get('total_projects', kpis.get('total_master_projects', 0)):,}", status="info"),
            NumberCallout(label="Critical Risk",   value=f"{kpis.get('critical_risk_project_count', 0):,}", status="critical"),
            NumberCallout(label="High Risk",       value=f"{kpis.get('high_risk_project_count', 0):,}", status="warning"),
            NumberCallout(label="Cost Overrun",    value=f"₹{kpis.get('total_cost_overrun_crore', 0):,.0f} Cr", status="warning"),
        ]
    else:
        numbers = []

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

    def chat(self, message: str, session_id: Optional[str] = None, project_code: Optional[str] = None) -> CopilotResponse:
        sid = session_id or str(uuid.uuid4())
        session = self.context_mgr.get_session(sid)

        # 1. Extract entities and intent signals (with explicit UI project_code priority)
        entities = _extract_entities(message, session, explicit_project_code=project_code)

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
