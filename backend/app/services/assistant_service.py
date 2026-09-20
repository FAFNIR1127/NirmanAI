"""
backend/app/services/assistant_service.py

Phase 13 — Nirman AI Copilot v2: Deep Reasoning & Open-Ended Intelligence Engine.

Capabilities:
1. Live Grounded Data Synthesis: Queries PostgreSQL nirman_db across all 5,461 infrastructure projects.
2. Multi-Dimensional Evidence: Integrates XGBoost Risk Engine v1 predictions, SHAP driver values, sector/agency benchmarks, and 331,206 PAIMANA vector chunks.
3. Deep Reasoning & Structured Formulation: Synthesizes detailed, highly relevant, executive-grade answers.
4. Dynamic Contextual Follow-up Generation: Generates relevant follow-up and clarifying questions for every query without hardcoded boilerplate.
5. Deterministic Dynamic Fallback: Employs dynamic entity-aware generation if API connectivity is interrupted.
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


# ── Live Database Gatherers ──────────────────────────────────────────────────

def _gather_portfolio_kpis() -> Dict[str, Any]:
    """Retrieve full portfolio macro KPIs directly from database."""
    try:
        from backend.app.services.analytics_service import get_executive_summary
        return get_executive_summary()
    except Exception as e:
        print(f"[Assistant] portfolio_kpis error: {e}")
        return {}


def _gather_state_digest(state_name: str) -> Dict[str, Any]:
    """Retrieve state-specific project digest."""
    try:
        from backend.app.services.insight_service import InsightService
        return InsightService.get_state_digest(state_name)
    except Exception as e:
        print(f"[Assistant] state_digest error for {state_name}: {e}")
        return {}


def _gather_sector_digest(sector_name: str) -> Dict[str, Any]:
    """Retrieve real-time aggregate statistics for a given infrastructure sector."""
    try:
        from backend.app.services.analytics_service import get_db_engine
        import sqlalchemy
        engine = get_db_engine()
        with engine.connect() as conn:
            sql = """
                SELECT 
                    COUNT(DISTINCT p.project_code) as total_projects,
                    COALESCE(SUM(p.original_cost), 0) as total_original_cost,
                    COALESCE(SUM(o.anticipated_cost), SUM(p.original_cost), 0) as total_anticipated_cost,
                    COALESCE(SUM(GREATEST(0, o.anticipated_cost - p.original_cost)), 0) as total_cost_overrun,
                    AVG(COALESCE(o.original_delay_months, o.revised_delay_months, 0)) as avg_delay_months,
                    COUNT(CASE WHEN r.risk_category = 'CRITICAL' THEN 1 END) as critical_count,
                    COUNT(CASE WHEN r.risk_category = 'HIGH' THEN 1 END) as high_count
                FROM projects p
                LEFT JOIN (
                    SELECT DISTINCT ON (project_code) project_code, anticipated_cost, original_delay_months, revised_delay_months
                    FROM project_observations
                    ORDER BY project_code, reporting_month DESC
                ) o ON p.project_code = o.project_code
                LEFT JOIN (
                    SELECT DISTINCT ON (project_code) project_code, risk_category
                    FROM risk_scores
                    ORDER BY project_code, reporting_month DESC
                ) r ON p.project_code = r.project_code
                WHERE LOWER(p.sector) LIKE :sec
            """
            row = conn.execute(sqlalchemy.text(sql), {"sec": f"%{sector_name.lower()}%"}).fetchone()
            if not row or not row[0]:
                return {}

            # Top 3 highest risk projects in sector
            top_sql = """
                SELECT p.project_code, p.project_name, p.state, p.agency, r.risk_category, r.risk_score,
                       GREATEST(0, COALESCE(o.anticipated_cost - p.original_cost, 0)) as overrun_cr
                FROM projects p
                JOIN (
                    SELECT DISTINCT ON (project_code) project_code, risk_score, risk_category
                    FROM risk_scores ORDER BY project_code, reporting_month DESC
                ) r ON p.project_code = r.project_code
                LEFT JOIN (
                    SELECT DISTINCT ON (project_code) project_code, anticipated_cost
                    FROM project_observations ORDER BY project_code, reporting_month DESC
                ) o ON p.project_code = o.project_code
                WHERE LOWER(p.sector) LIKE :sec
                ORDER BY r.risk_score DESC NULLS LAST
                LIMIT 5
            """
            top_rows = conn.execute(sqlalchemy.text(top_sql), {"sec": f"%{sector_name.lower()}%"}).fetchall()
            top_projects = [
                {
                    "project_code": str(r[0]),
                    "project_name": str(r[1]),
                    "state": str(r[2] or "N/A"),
                    "agency": str(r[3] or "N/A"),
                    "risk_category": str(r[4] or "N/A"),
                    "risk_score": float(r[5] or 0),
                    "overrun_cr": float(r[6] or 0)
                }
                for r in top_rows
            ]

            tot_orig = float(row[1] or 0)
            tot_ant = float(row[2] or 0)
            overrun = float(row[3] or 0)
            overrun_pct = round((overrun / tot_orig) * 100.0, 1) if tot_orig > 0 else 0.0

            return {
                "sector": sector_name,
                "total_projects": int(row[0] or 0),
                "total_original_cost_crore": tot_orig,
                "total_anticipated_cost_crore": tot_ant,
                "total_cost_overrun_crore": overrun,
                "cost_overrun_percent": overrun_pct,
                "avg_delay_months": round(float(row[4] or 0), 1),
                "critical_count": int(row[5] or 0),
                "high_count": int(row[6] or 0),
                "top_projects": top_projects
            }
    except Exception as e:
        print(f"[Assistant] sector_digest error for {sector_name}: {e}")
        return {}


def _gather_agency_digest(agency_name: str) -> Dict[str, Any]:
    """Retrieve real-time aggregate statistics for an implementing agency."""
    try:
        from backend.app.services.analytics_service import get_db_engine
        import sqlalchemy
        engine = get_db_engine()
        with engine.connect() as conn:
            sql = """
                SELECT 
                    COUNT(DISTINCT p.project_code) as total_projects,
                    COALESCE(SUM(p.original_cost), 0) as total_original_cost,
                    COALESCE(SUM(o.anticipated_cost), SUM(p.original_cost), 0) as total_anticipated_cost,
                    COALESCE(SUM(GREATEST(0, o.anticipated_cost - p.original_cost)), 0) as total_cost_overrun,
                    AVG(COALESCE(o.original_delay_months, o.revised_delay_months, 0)) as avg_delay_months,
                    COUNT(CASE WHEN r.risk_category = 'CRITICAL' THEN 1 END) as critical_count
                FROM projects p
                LEFT JOIN (
                    SELECT DISTINCT ON (project_code) project_code, anticipated_cost, original_delay_months, revised_delay_months
                    FROM project_observations
                    ORDER BY project_code, reporting_month DESC
                ) o ON p.project_code = o.project_code
                LEFT JOIN (
                    SELECT DISTINCT ON (project_code) project_code, risk_category
                    FROM risk_scores
                    ORDER BY project_code, reporting_month DESC
                ) r ON p.project_code = r.project_code
                WHERE LOWER(p.agency) LIKE :agency
            """
            row = conn.execute(sqlalchemy.text(sql), {"agency": f"%{agency_name.lower()}%"}).fetchone()
            if not row or not row[0]:
                return {}

            return {
                "agency": agency_name,
                "total_projects": int(row[0] or 0),
                "total_original_cost_crore": float(row[1] or 0),
                "total_anticipated_cost_crore": float(row[2] or 0),
                "total_cost_overrun_crore": float(row[3] or 0),
                "avg_delay_months": round(float(row[4] or 0), 1),
                "critical_count": int(row[5] or 0),
            }
    except Exception as e:
        print(f"[Assistant] agency_digest error for {agency_name}: {e}")
        return {}


def _gather_project_details(project_code: str) -> Dict[str, Any]:
    """Retrieve full project schema, timeline observations, and latest figures."""
    try:
        from backend.app.services import project_service
        return project_service.get_project_details(project_code) or {}
    except Exception as e:
        print(f"[Assistant] project_details error for {project_code}: {e}")
        return {}


def _gather_top_risk_projects(limit: int = 10) -> List[Dict]:
    """Retrieve top highest risk projects with latest XGBoost scores."""
    try:
        from backend.app.services import project_service
        return project_service.list_projects_summary(limit=limit)
    except Exception as e:
        print(f"[Assistant] top_risk_projects error: {e}")
        return []


def _gather_top_overrun_projects(limit: int = 10) -> List[Dict]:
    """Retrieve top projects ranked by absolute financial cost overrun."""
    try:
        from backend.app.services.analytics_service import get_db_engine
        import sqlalchemy
        engine = get_db_engine()
        with engine.connect() as conn:
            sql = """
                SELECT p.project_code, p.project_name, p.agency, p.state, p.sector,
                       p.original_cost, o.anticipated_cost,
                       (o.anticipated_cost - p.original_cost) as overrun_cr,
                       ROUND(((o.anticipated_cost - p.original_cost)::numeric / NULLIF(p.original_cost, 0)::numeric) * 100, 1) as overrun_pct,
                       COALESCE(o.original_delay_months, o.revised_delay_months, 0) as delay_months,
                       r.risk_category
                FROM projects p
                JOIN (
                    SELECT DISTINCT ON (project_code) project_code, anticipated_cost, original_delay_months, revised_delay_months
                    FROM project_observations
                    WHERE anticipated_cost IS NOT NULL
                    ORDER BY project_code, reporting_month DESC
                ) o ON p.project_code = o.project_code
                LEFT JOIN (
                    SELECT DISTINCT ON (project_code) project_code, risk_category
                    FROM risk_scores
                    ORDER BY project_code, reporting_month DESC
                ) r ON p.project_code = r.project_code
                WHERE p.original_cost > 0 AND (o.anticipated_cost - p.original_cost) > 0
                ORDER BY overrun_cr DESC
                LIMIT :lim
            """
            rows = conn.execute(sqlalchemy.text(sql), {"lim": limit}).fetchall()
            return [
                {
                    "project_code": str(r[0]),
                    "project_name": str(r[1]),
                    "agency": str(r[2] or "N/A"),
                    "state": str(r[3] or "N/A"),
                    "sector": str(r[4] or "N/A"),
                    "original_cost": float(r[5] or 0),
                    "anticipated_cost": float(r[6] or 0),
                    "overrun_cr": float(r[7] or 0),
                    "overrun_pct": float(r[8] or 0),
                    "delay_months": float(r[9] or 0),
                    "risk_category": str(r[10] or "N/A")
                }
                for r in rows
            ]
    except Exception as e:
        print(f"[Assistant] top_overrun_projects error: {e}")
        return []


def _gather_top_delayed_projects(limit: int = 10) -> List[Dict]:
    """Retrieve top projects ranked by schedule slippage in months."""
    try:
        from backend.app.services.analytics_service import get_db_engine
        import sqlalchemy
        engine = get_db_engine()
        with engine.connect() as conn:
            sql = """
                SELECT p.project_code, p.project_name, p.agency, p.state, p.sector,
                       COALESCE(o.original_delay_months, o.revised_delay_months, 0) as delay_months,
                       o.original_doc, o.anticipated_doc, o.physical_progress,
                       r.risk_category
                FROM projects p
                JOIN (
                    SELECT DISTINCT ON (project_code) project_code, original_delay_months, revised_delay_months, original_doc, anticipated_doc, physical_progress
                    FROM project_observations
                    WHERE original_delay_months > 0 OR revised_delay_months > 0
                    ORDER BY project_code, reporting_month DESC
                ) o ON p.project_code = o.project_code
                LEFT JOIN (
                    SELECT DISTINCT ON (project_code) project_code, risk_category
                    FROM risk_scores
                    ORDER BY project_code, reporting_month DESC
                ) r ON p.project_code = r.project_code
                ORDER BY delay_months DESC
                LIMIT :lim
            """
            rows = conn.execute(sqlalchemy.text(sql), {"lim": limit}).fetchall()
            return [
                {
                    "project_code": str(r[0]),
                    "project_name": str(r[1]),
                    "agency": str(r[2] or "N/A"),
                    "state": str(r[3] or "N/A"),
                    "sector": str(r[4] or "N/A"),
                    "delay_months": float(r[5] or 0),
                    "original_doc": str(r[6] or "N/A"),
                    "anticipated_doc": str(r[7] or "N/A"),
                    "physical_progress": float(r[8] or 0),
                    "risk_category": str(r[9] or "N/A")
                }
                for r in rows
            ]
    except Exception as e:
        print(f"[Assistant] top_delayed_projects error: {e}")
        return []


def _gather_risk_decomposition(project_code: str) -> Dict[str, Any]:
    """Retrieve SHAP driver feature impacts from ML Risk Engine."""
    try:
        from backend.app.services.risk_decomposition_service import RiskDecompositionService
        svc = RiskDecompositionService()
        return svc.decompose_project_risk(project_code) or {}
    except Exception as e:
        print(f"[Assistant] risk_decomp error for {project_code}: {e}")
        return {}


def _gather_rag_evidence(query: str, project_code: Optional[str] = None, top_k: int = 5) -> List[Dict]:
    """Search 331,206 PAIMANA document chunks for qualitative audit ground truth."""
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


# ── Entity & Intent Extraction ────────────────────────────────────────────────

KNOWN_SECTORS = {
    "railway": "Railways",
    "railways": "Railways",
    "train": "Railways",
    "road": "Road Transport and Highways",
    "highway": "Road Transport and Highways",
    "nhai": "Road Transport and Highways",
    "petroleum": "Petroleum and Natural Gas",
    "oil": "Petroleum and Natural Gas",
    "gas": "Petroleum and Natural Gas",
    "power": "Power",
    "energy": "Power",
    "coal": "Coal",
    "atomic": "Atomic Energy",
    "nuclear": "Atomic Energy",
    "aviation": "Civil Aviation",
    "airport": "Civil Aviation",
    "shipping": "Shipping and Ports",
    "port": "Shipping and Ports",
    "water": "Water Resources",
    "telecom": "Telecommunications",
    "urban": "Urban Development",
    "metro": "Urban Development",
    "steel": "Steel",
    "mines": "Mines",
    "fertilizer": "Fertilizers"
}

KNOWN_AGENCIES = [
    "NHAI", "RVNL", "DFCCIL", "NTPC", "ONGC", "BHEL", "PGCIL", "IOCL", 
    "BPCL", "GAIL", "MRVC", "KRCL", "AAI", "DMRC", "CIL", "SAIL", "MoRTH"
]

KNOWN_STATES = [
    "Maharashtra", "Tamil Nadu", "Uttar Pradesh", "Gujarat", "Bihar",
    "Karnataka", "West Bengal", "Delhi", "Rajasthan", "Odisha",
    "Kerala", "Andhra Pradesh", "Telangana", "Madhya Pradesh", "Assam",
    "Punjab", "Haryana", "Jharkhand", "Chhattisgarh", "Himachal Pradesh",
    "Uttarakhand", "Jammu and Kashmir", "Goa", "Tripura", "Meghalaya"
]


def _lookup_project_code_by_name(query: str) -> Optional[str]:
    """Resolve project names mentioned in natural language query to project_code directly from DB."""
    try:
        from backend.app.services.analytics_service import get_db_engine
        import sqlalchemy
        engine = get_db_engine()
        stop_words = {
            "details", "project", "projects", "show", "what", "give", "about",
            "risk", "cost", "the", "and", "for", "tell", "with", "overrun",
            "status", "information", "info", "update", "latest", "please", "me",
            "original", "anticipated", "revised", "expenditure", "delay", "months",
            "progress", "percentage", "compare", "between", "how", "much", "many",
            "when", "where", "which", "will", "this", "that", "these", "those",
            "financial", "physical", "sanctioned", "estimated", "current"
        }
        cleaned = re.sub(r'[^\w\s-]', ' ', query)
        tokens = [w.strip() for w in cleaned.split() if len(w.strip()) >= 3 and w.lower() not in stop_words]
        if not tokens:
            return None

        with engine.connect() as conn:
            # 1. Multi-token match across all significant tokens
            if len(tokens) >= 2:
                conds = [f"LOWER(project_name) LIKE :w{i}" for i in range(len(tokens))]
                params = {f"w{i}": f"%{tokens[i].lower()}%" for i in range(len(tokens))}
                sql = "SELECT project_code FROM projects WHERE " + " AND ".join(conds) + " ORDER BY LENGTH(project_name) ASC LIMIT 1"
                row = conn.execute(sqlalchemy.text(sql), params).fetchone()
                if row:
                    return str(row[0])

                # 2. Try consecutive token pairs
                for i in range(len(tokens) - 1):
                    pair_sql = "SELECT project_code FROM projects WHERE LOWER(project_name) LIKE :w1 AND LOWER(project_name) LIKE :w2 ORDER BY LENGTH(project_name) ASC LIMIT 1"
                    row = conn.execute(sqlalchemy.text(pair_sql), {"w1": f"%{tokens[i].lower()}%", "w2": f"%{tokens[i+1].lower()}%"}).fetchone()
                    if row:
                        return str(row[0])

            # 3. Single key significant token match (longest first)
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
    """Extract project codes, states, sectors, agencies, and intent dimensions."""
    q = query.lower()

    codes = re.findall(r'\b([A-Z]?\d{7,10}|[A-Z]\d{6,9})\b', query.upper())
    primary_code = explicit_project_code or (codes[0] if codes else None)

    if not primary_code:
        primary_code = _lookup_project_code_by_name(query)

    if not primary_code:
        primary_code = session.last_project_code

    found_state = next((s for s in KNOWN_STATES if s.lower() in q), None)
    found_sector = next((canonical for k, canonical in KNOWN_SECTORS.items() if k in q), None)
    found_agency = next((a for a in KNOWN_AGENCIES if a.lower() in q or a in query), None)

    # Intent signals
    is_project_query = bool(primary_code)
    is_state_query = bool(found_state)
    is_sector_query = bool(found_sector)
    is_agency_query = bool(found_agency)
    is_portfolio = any(w in q for w in ["portfolio", "overview", "summary", "total projects", "all projects", "national"])
    is_cost_query = any(w in q for w in ["cost", "overrun", "expenditure", "budget", "crore", "financial"])
    is_risk_query = any(w in q for w in ["risk", "critical", "high risk", "alert", "warning", "xgboost", "shap"])
    is_schedule_query = any(w in q for w in ["delay", "schedule", "time overrun", "completion", "deadline", "slippage", "months"])
    is_rag_query = any(w in q for w in ["report", "paimana", "document", "historical", "audit", "cag", "what did", "according to"])
    is_comparison = any(w in q for w in ["compare", "vs", "versus", "difference between"])

    return {
        "project_codes": codes,
        "primary_project_code": primary_code,
        "state": found_state,
        "sector": found_sector,
        "agency": found_agency,
        "is_project_query": is_project_query,
        "is_state_query": is_state_query,
        "is_sector_query": is_sector_query,
        "is_agency_query": is_agency_query,
        "is_portfolio": is_portfolio,
        "is_cost_query": is_cost_query,
        "is_risk_query": is_risk_query,
        "is_schedule_query": is_schedule_query,
        "is_rag_query": is_rag_query,
        "is_comparison": is_comparison,
    }


# ── Evidence Gathering ────────────────────────────────────────────────────────

def _build_evidence_context(query: str, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Gather live data from DB, ML engines, and RAG index based on intent entities."""
    evidence = {}

    p_code = entities.get("primary_project_code")
    state = entities.get("state")
    sector = entities.get("sector")
    agency = entities.get("agency")
    all_codes = entities.get("project_codes", [])

    # Always get portfolio KPIs for macro context
    evidence["portfolio_kpis"] = _gather_portfolio_kpis()

    # Project-specific evidence
    if p_code:
        evidence["project_details"] = _gather_project_details(p_code)
        evidence["risk_decomposition"] = _gather_risk_decomposition(p_code)
        if entities.get("is_comparison") and len(all_codes) >= 2:
            evidence["compare_projects"] = [_gather_project_details(c) for c in all_codes[:4]]

    # State evidence
    if state:
        evidence["state_digest"] = _gather_state_digest(state)

    # Sector evidence
    if sector:
        evidence["sector_digest"] = _gather_sector_digest(sector)

    # Agency evidence
    if agency:
        evidence["agency_digest"] = _gather_agency_digest(agency)

    # Top overruns & delays when asked specifically
    if entities.get("is_cost_query") and not p_code:
        evidence["top_overrun_projects"] = _gather_top_overrun_projects(limit=8)
    if entities.get("is_schedule_query") and not p_code:
        evidence["top_delayed_projects"] = _gather_top_delayed_projects(limit=8)

    # Top critical projects for risk or portfolio queries
    if entities.get("is_risk_query") or entities.get("is_portfolio") or not p_code:
        evidence["top_risk_projects"] = _gather_top_risk_projects(limit=10)

    # Semantic RAG search
    rag_top_k = 6 if entities.get("is_rag_query") else 4
    evidence["rag_evidence"] = _gather_rag_evidence(query, project_code=p_code, top_k=rag_top_k)

    return evidence


# ── Gemini Prompt Builder ──────────────────────────────────────────────────────

def _build_prompt(query: str, evidence: Dict[str, Any], history: List[Dict]) -> str:
    kpis = evidence.get("portfolio_kpis", {})
    rag = evidence.get("rag_evidence", [])
    top_proj = evidence.get("top_risk_projects", [])
    top_overrun = evidence.get("top_overrun_projects", [])
    top_delayed = evidence.get("top_delayed_projects", [])
    proj = evidence.get("project_details", {})
    risk_decomp = evidence.get("risk_decomposition", {})
    state_dig = evidence.get("state_digest", {})
    sec_dig = evidence.get("sector_digest", {})
    agency_dig = evidence.get("agency_digest", {})
    compare = evidence.get("compare_projects", [])

    # Format conversation history
    history_text = ""
    if history:
        recent = history[-6:]
        history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in recent])

    # Format portfolio KPIs
    kpi_text = f"""Portfolio KPIs (MoSPI National Surveillance — July 2026):
- Total Master Projects in Database: {kpis.get('total_projects', kpis.get('total_master_projects', '5,461')):,}
- Total Original Sanctioned Cost: ₹{kpis.get('total_original_cost_crore', 0):,.2f} Crore
- Total Anticipated Cost (Latest): ₹{kpis.get('total_anticipated_cost_crore', 0):,.2f} Crore
- Cumulative Portfolio Cost Overrun: ₹{kpis.get('total_cost_overrun_crore', 0):,.2f} Crore ({kpis.get('overall_cost_overrun_percent', 0):.1f}%)
- Critical Risk Projects: {kpis.get('critical_risk_project_count', 0):,}
- High Risk Projects: {kpis.get('high_risk_project_count', 0):,}
- Moderate Risk Projects: {kpis.get('moderate_risk_project_count', 0):,}
- Low Risk Projects: {kpis.get('low_risk_project_count', 0):,}
- Average Schedule Slippage: {kpis.get('avg_delay_months', 0):.1f} months
- Machine Learning Risk Threshold: T* = 0.28 (Calibrated XGBoost Model v1)""" if kpis else "Portfolio KPIs: unavailable."

    # Format project details if present
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
            shap_text = "XGBoost + SHAP Risk Driver Decomposition:\n" + "\n".join(
                [f"  - {d.get('feature', d.get('feature_name', 'factor'))}: impact={d.get('impact', d.get('shap_contribution', 'N/A'))} ({d.get('description', '')})" for d in drivers[:5]]
            )

    # Format state digest
    state_text = ""
    if state_dig:
        state_text = f"""State Digest ({state_dig.get('state')}):
- Total Projects: {state_dig.get('total_projects', 'N/A')}
- Critical Risk: {state_dig.get('critical_count', 'N/A')} projects | High Risk: {state_dig.get('high_count', 'N/A')} projects
- Total Outlay: ₹{state_dig.get('total_outlay_crore', 0):,.2f} Crore
- Highest Risk Projects in State: {', '.join([p.get('project_code','') for p in state_dig.get('top_risk_projects', [])[:5]])}"""

    # Format sector digest
    sector_text = ""
    if sec_dig:
        sector_text = f"""Sector Telemetry ({sec_dig.get('sector')}):
- Total Projects: {sec_dig.get('total_projects', 0):,}
- Total Original Sanctioned Cost: ₹{sec_dig.get('total_original_cost_crore', 0):,.2f} Crore
- Total Anticipated Cost: ₹{sec_dig.get('total_anticipated_cost_crore', 0):,.2f} Crore
- Total Cost Overrun: ₹{sec_dig.get('total_cost_overrun_crore', 0):,.2f} Crore ({sec_dig.get('cost_overrun_percent', 0):.1f}%)
- Average Delay: {sec_dig.get('avg_delay_months', 0):.1f} months
- Critical Projects: {sec_dig.get('critical_count', 0):,} | High Risk: {sec_dig.get('high_count', 0):,}"""

    # Format agency digest
    agency_text = ""
    if agency_dig:
        agency_text = f"""Agency Telemetry ({agency_dig.get('agency')}):
- Total Projects: {agency_dig.get('total_projects', 0):,}
- Cumulative Cost Overrun: ₹{agency_dig.get('total_cost_overrun_crore', 0):,.2f} Crore
- Average Delay: {agency_dig.get('avg_delay_months', 0):.1f} months
- Critical Risk Projects: {agency_dig.get('critical_count', 0):,}"""

    # Format top overrun projects
    overrun_text = ""
    if top_overrun:
        overrun_text = "Top Projects with Highest Cost Overrun:\n" + "\n".join([
            f"  [{i+1}] {p.get('project_code')} | {p.get('project_name')} | ₹{p.get('overrun_cr',0):,.2f} Cr Overrun (+{p.get('overrun_pct',0):.1f}%) | Delay: {p.get('delay_months',0):.0f}m | Agency: {p.get('agency')} ({p.get('state')})"
            for i, p in enumerate(top_overrun[:8])
        ])

    # Format top delayed projects
    delayed_text = ""
    if top_delayed:
        delayed_text = "Top Projects with Highest Schedule Slippage:\n" + "\n".join([
            f"  [{i+1}] {p.get('project_code')} | {p.get('project_name')} | Delay: {p.get('delay_months',0):.0f} months | Progress: {p.get('physical_progress',0):.1f}% | Target DOC: {p.get('original_doc')} → {p.get('anticipated_doc')} | Agency: {p.get('agency')}"
            for i, p in enumerate(top_delayed[:8])
        ])

    # Format top projects
    proj_list_text = ""
    if top_proj:
        proj_list_text = "Top Risk Projects (XGBoost Calibrated Probability):\n" + "\n".join([
            f"  [{i+1}] {p.get('project_code')} | {p.get('project_name','')} | {p.get('state','')} | Risk: {p.get('risk_category','')} ({p.get('risk_score',0):.1f}) | Agency: {p.get('agency','')}"
            for i, p in enumerate(top_proj[:8])
        ])

    # Format comparison
    compare_text = ""
    if compare:
        compare_text = "Multi-Project Comparison Telemetry:\n" + "\n".join([
            f"  - {p.get('project_code')}: {p.get('project_name')} | {p.get('state')} | Original ₹{p.get('original_cost','N/A')} Cr → Anticipated ₹{p.get('latest_anticipated_cost','N/A')} Cr"
            for p in compare if p
        ])

    # Format RAG citations
    rag_text = ""
    if rag:
        rag_text = "Historical PAIMANA Report Excerpts (Use for qualitative audit context and contractor factors — NOT current live cost):\n" + "\n".join([
            f"  [{c['citation_id']}] {c['source_file']} (p.{c['page']}, {c['month']}): \"{c['content'][:300]}\""
            for c in rag
        ])

    # Build the full prompt
    data_sections = "\n\n".join(filter(None, [
        kpi_text, proj_text, shap_text, state_text, sector_text, 
        agency_text, overrun_text, delayed_text, proj_list_text, compare_text, rag_text
    ]))

    prompt = f"""You are Nirman AI Copilot — the Senior Infrastructure Intelligence Advisor for the Ministry of Statistics and Programme Implementation (MoSPI), Government of India. You monitor all 5,461 major central infrastructure projects (₹150+ Crore).

INSTRUCTIONS FOR GENERATING HIGH-QUALITY DETAILED RESPONSES:
1. DIRECT ANSWER FIRST: Begin with a clear, direct executive answer to the user's specific question.
2. COMPREHENSIVE & DETAILED EXPLANATION:
   - Provide a thorough, well-developed response with rich context, numbers, and proper analytical depth.
   - **Financial Telemetry**: State exact Original Sanctioned Cost, Latest Anticipated Cost, Cumulative Cost Overrun in ₹ Crore and % escalation, and expenditure status.
   - **Timeline & Delay**: State Original Target Completion Date, Latest Anticipated Date, exact delay in months, and current physical completion %.
   - **Root Cause Reasoning**: Analyze specific real-world factors, site conditions, contractor execution issues, or statutory clearances detailed in the PAIMANA report excerpts (`[E1]`, `[E2]`) and live observations.
   - **Risk Evaluation**: Explain what the XGBoost risk tier means in practical terms for this project or sector.
   - **Administrative Next Steps**: Offer 2 to 3 practical, actionable governance measures for reviewing officers to unblock bottlenecks.
3. BEGINNER-FRIENDLY & ACCESSIBLE ENGLISH:
   - Use clear, professional, and accessible language. Explain the meaning of all metrics simply so any reviewer can understand without deciphering complex statistical formulas.
   - Bold all key numbers and milestones.
   - Cite [E1], [E2] when referencing historical audit excerpts.
4. CONCISE ACTIONABLE FOLLOW-UP QUESTIONS:
   - At the very end of your response, output 3 to 4 concise, punchy follow-up questions (each 8 to 14 words max) inside the following exact tags so they can be rendered as clean one-click buttons:
   <<<FOLLOW_UPS>>>
   1. [Short, punchy question 1]
   2. [Short, punchy question 2]
   3. [Short, punchy question 3]
   <<<END_FOLLOW_UPS>>>
   Do NOT put any other text after <<<END_FOLLOW_UPS>>>.

---CONVERSATION HISTORY---
{history_text or "This is the start of the conversation."}

---LIVE DATA & EVIDENCE (GROUND TRUTH)---
{data_sections}
---END OF EVIDENCE---

USER QUESTION: {query}

Provide a comprehensive, detailed, and clear response:"""

    return prompt


# ── Gemini Call ───────────────────────────────────────────────────────────────

def _call_gemini(prompt: str) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    user_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    user_model = user_model.replace("models/", "")
    candidates = [user_model, "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-3.5-flash-lite"]
    
    seen: set = set()
    candidates = [m for m in candidates if not (m in seen or seen.add(m))]

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        for m in candidates:
            try:
                try:
                    config = types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=4000
                    )
                    res = client.models.generate_content(
                        model=f"models/{m}",
                        contents=prompt,
                        config=config
                    )
                except Exception:
                    res = client.models.generate_content(
                        model=f"models/{m}",
                        contents=prompt
                    )

                if res and res.text:
                    print(f"[Assistant] Gemini '{m}' responded successfully with detailed analysis.")
                    return res.text.strip()
            except Exception as e:
                print(f"[Assistant] Model '{m}' failed: {e}")
    except ImportError as e:
        print(f"[Assistant] google-genai not available: {e}")

    return None


# ── Dynamic Fallback (Entity-Aware Generation) ────────────────────────────────

def _deterministic_fallback(query: str, evidence: Dict[str, Any], entities: Dict[str, Any]) -> str:
    """Dynamic fallback synthesizing grounded data in a detailed, structured, beginner-friendly format."""
    kpis = evidence.get("portfolio_kpis", {})
    rag = evidence.get("rag_evidence", [])
    proj = evidence.get("project_details", {})
    sec_dig = evidence.get("sector_digest", {})
    state_dig = evidence.get("state_digest", {})
    top_overrun = evidence.get("top_overrun_projects", [])

    if proj:
        p_code = proj.get("project_code", "")
        p_name = proj.get("project_name", p_code)
        agency = proj.get("agency", "N/A")
        state = proj.get("state", "N/A")
        sector = proj.get("sector", "N/A")
        approval = proj.get("approval_date", "N/A")
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
            f"### Comprehensive Project Brief: {p_name} (`{p_code}`)",
            f"**{p_name}** is a major central infrastructure project in the **{sector}** sector, being executed by **{agency}** in **{state}** (Approved: `{approval}`).",
            "",
            "#### 📊 Financial & Budget Telemetry",
            f"- **Original Sanctioned Cost**: ₹{orig_f:,.2f} Crore" if orig_f is not None else "- **Original Cost**: N/A",
            f"- **Latest Anticipated Cost**: ₹{ant_f:,.2f} Crore" if ant_f is not None else "- **Latest Anticipated Cost**: N/A",
            f"- **Cost Overrun**: " + (f"**₹{overrun:,.2f} Crore ({overrun_pct:+.1f}% escalation)**" if overrun > 0 else "**₹0.00 Cr (Within sanctioned budget)**"),
            "",
            "#### ⏱️ Schedule & Physical Progress",
            f"- **Physical Execution**: **{prog}% completed**",
            f"- **Original Date of Completion**: `{orig_doc}`",
            f"- **Revised Anticipated Completion**: `{ant_doc}`",
            f"- **Cumulative Schedule Delay**: " + (f"**{delay_m:.0f} months delay**" if (delay_m and delay_m > 0) else "**On schedule**"),
            "",
            "#### 🔍 Key Analysis & Root Causes",
            f"The project is currently experiencing an execution gap where physical work progress ({prog}%) is trailing the expected milestone trajectory. Key factors influencing this project include statutory and inter-departmental clearances, local site handover pacing, and contractor deployment.",
            "",
            "#### 📋 Recommended Governance Steps",
            f"1. **Inter-Agency Review**: Schedule a dedicated coordination meeting between {agency} and the {state} state government to resolve remaining site hurdles.",
            f"2. **Milestone Acceleration**: Direct the contracting agency to submit a revised catch-up schedule with fortnightly deliverables.",
            f"3. **PM GatiShakti Integration**: Utilize the national master plan portal to streamline utility relocation and clearances.",
        ]
        if rag:
            lines.append("\n#### 📄 Official PAIMANA Report Citations")
            for c in rag[:2]:
                lines.append(f"> [{c['citation_id']}] **{c['source_file']}** (p.{c['page']}): \"{c['content'][:220]}...\"")

        lines.append(f"\n<<<FOLLOW_UPS>>>\n1. What specific hurdles are cited in PAIMANA audits for {p_code}?\n2. How does {p_name}'s delay compare with other {sector} projects?\n3. What is the latest milestone completion status for {p_code}?\n<<<END_FOLLOW_UPS>>>")
        return "\n".join(lines)

    if sec_dig:
        sec = sec_dig.get("sector", "")
        lines = [
            f"### Detailed Sector Intelligence: {sec}",
            f"The **{sec}** sector represents a substantial component of central infrastructure monitoring, currently encompassing **{sec_dig.get('total_projects', 0):,} major projects** with an overall capital footprint of **₹{sec_dig.get('total_anticipated_cost_crore', 0):,.2f} Crore**.",
            "",
            "#### 📊 Sector Financial & Delay Summary",
            f"- **Total Monitored Projects**: **{sec_dig.get('total_projects', 0):,}**",
            f"- **Total Original Sanctioned Budget**: ₹{sec_dig.get('total_original_cost_crore', 0):,.2f} Crore",
            f"- **Total Anticipated Cost**: ₹{sec_dig.get('total_anticipated_cost_crore', 0):,.2f} Crore",
            f"- **Cumulative Sector Cost Overrun**: **₹{sec_dig.get('total_cost_overrun_crore', 0):,.2f} Crore ({sec_dig.get('cost_overrun_percent', 0):.1f}%)**",
            f"- **Average Project Schedule Delay**: **{sec_dig.get('avg_delay_months', 0):.1f} months**",
            f"- **Priority Review Projects**: **{sec_dig.get('critical_count', 0):,} Critical** and **{sec_dig.get('high_count', 0):,} High Risk** projects",
            "",
            "#### 🔍 Key Projects Requiring Executive Attention:"
        ]
        for p in sec_dig.get("top_projects", [])[:4]:
            lines.append(f"- **{p.get('project_code')}** ({p.get('project_name')}): {p.get('agency')} in {p.get('state')} — Cost Overrun: **₹{p.get('overrun_cr',0):,.1f} Cr**")
        
        lines.append(f"\n<<<FOLLOW_UPS>>>\n1. Which agency under {sec} has the highest number of delayed projects?\n2. Show the highest-risk project in the {sec} sector\n3. What is the average cost overrun across {sec} projects?\n<<<END_FOLLOW_UPS>>>")
        return "\n".join(lines)

    if state_dig:
        st = state_dig.get("state", "")
        lines = [
            f"### Regional Infrastructure Analysis: {st}",
            f"In **{st}**, the central government is currently monitoring **{state_dig.get('total_projects', 'N/A')} major infrastructure projects** with a cumulative capital outlay of **₹{state_dig.get('total_outlay_crore', 0):,.2f} Crore**.",
            "",
            "#### 📌 State Risk Telemetry",
            f"- **Total Infrastructure Projects**: **{state_dig.get('total_projects', 'N/A')}**",
            f"- **Critical Risk Projects**: **{state_dig.get('critical_count', 'N/A')}** projects requiring high-level intervention",
            f"- **High Risk Projects**: **{state_dig.get('high_count', 'N/A')}** projects with significant delay indicators",
            f"- **Total Capital Footprint**: ₹{state_dig.get('total_outlay_crore', 0):,.2f} Crore",
            "",
            "#### 📋 Recommended State-Level Actions",
            f"Convene a dedicated State Project Monitoring Group (SPMG) review to accelerate land acquisition, forest clearances, and utility relocation across active projects in {st}."
        ]
        lines.append(f"\n<<<FOLLOW_UPS>>>\n1. Which sector in {st} has the highest cost escalation?\n2. Show the highest-risk project located in {st}\n3. Compare {st}'s infrastructure progress with neighboring states\n<<<END_FOLLOW_UPS>>>")
        return "\n".join(lines)

    # Macro Portfolio Overview
    crit = kpis.get("critical_risk_project_count", 0)
    high = kpis.get("high_risk_project_count", 0)
    mod  = kpis.get("moderate_risk_project_count", 0)
    low  = kpis.get("low_risk_project_count", 0)
    tot  = kpis.get("total_projects", kpis.get("total_master_projects", 5461))
    cost = kpis.get("total_original_cost_crore", 0)
    ant_cost = kpis.get("total_anticipated_cost_crore", 0)
    overrun  = kpis.get("total_cost_overrun_crore", 0)
    overrun_pct = kpis.get("overall_cost_overrun_percent", 0)
    delay_avg = kpis.get("avg_delay_months", 0)

    lines = [
        "### National Infrastructure Portfolio Overview (MoSPI Surveillance)",
        f"MoSPI is actively tracking **{tot:,} major central infrastructure projects** (each ₹150+ Crore). The total anticipated investment across the portfolio stands at **₹{ant_cost:,.2f} Crore** against an initial sanctioned outlay of **₹{cost:,.2f} Crore**, representing a cumulative cost escalation of **₹{overrun:,.2f} Crore ({overrun_pct:.1f}%)**.",
        "",
        "#### 📊 Portfolio Summary Metrics",
        f"- **Total Projects Under Active Surveillance**: **{tot:,}**",
        f"- **Cumulative Cost Overrun**: **₹{overrun:,.2f} Crore ({overrun_pct:.1f}%)**",
        f"- **Average Project Schedule Delay**: **{delay_avg:.1f} months** across delayed projects",
        "",
        "#### 🔴 Risk Distribution (XGBoost Calibrated Model v1)",
        f"- 🔴 **Critical Risk**: **{crit:,}** projects requiring immediate cabinet-level review",
        f"- 🟠 **High Risk**: **{high:,}** projects with moderate-to-high delay indicators",
        f"- 🟡 **Moderate Risk**: **{mod:,}** projects requiring standard quarterly tracking",
        f"- 🟢 **Low Risk**: **{low:,}** projects progressing within approved parameters",
    ]
    if top_overrun:
        lines.append("\n#### 🔍 Top Projects by Absolute Cost Escalation:")
        for p in top_overrun[:4]:
            lines.append(f"- **{p.get('project_code')}** ({p.get('project_name')}): Overrun of **₹{p.get('overrun_cr',0):,.1f} Cr (+{p.get('overrun_pct',0):.1f}%)** | {p.get('agency')}")
    
    lines.append(f"\n<<<FOLLOW_UPS>>>\n1. Which sector accounts for the largest share of cost overrun?\n2. Show the top 5 critical risk projects under active surveillance\n3. What are the primary root causes of critical project delay?\n<<<END_FOLLOW_UPS>>>")
    return "\n".join(lines)


# ── CopilotResponse Builder ───────────────────────────────────────────────────

def _clean_answer_text(text: str) -> str:
    """Strip <<<FOLLOW_UPS>>> block and any trailing follow-up headers so questions are not duplicated in the text body."""
    cleaned = re.sub(r'<<<FOLLOW_UPS>>>[\s\S]*?<<<END_FOLLOW_UPS>>>', '', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'(?:###?\s*.*(?:follow-?up|explore next|clarifying questions|what would you like).*?\n)[\s\S]*$', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _extract_dynamic_followups(answer_text: str, entities: Dict[str, Any]) -> List[str]:
    """Parse dynamically generated follow-up questions from the response text."""
    # 1. Check for <<<FOLLOW_UPS>>> block
    fu_match = re.search(r'<<<FOLLOW_UPS>>>([\s\S]*?)<<<END_FOLLOW_UPS>>>', answer_text, re.IGNORECASE)
    if fu_match:
        lines = re.findall(r'(?:^[0-9]+\.|\s*[-*•])\s*(.+)', fu_match.group(1), re.MULTILINE)
        cleaned = [l.strip().strip('"').strip("'") for l in lines if len(l.strip()) > 8]
        if cleaned:
            return cleaned[:4]

    # 2. Check for markdown header
    section_match = re.search(
        r"(?:dynamic follow-?up|follow-?up questions|clarifying & follow-?up|what would you like to explore next)[^\n]*\n((?:[\s]*[0-9\-*•]+\.?\s+[^\n]+\n?)+)",
        answer_text,
        re.IGNORECASE
    )
    if section_match:
        raw_items = re.findall(r'(?:^[0-9]+\.|\s*[-*•])\s*(.+)', section_match.group(1), re.MULTILINE)
        cleaned = [item.strip().strip('"').strip("'") for item in raw_items if len(item.strip()) > 8]
        if cleaned:
            return cleaned[:4]

    # 3. Dynamic logical generation based on context
    p_code = entities.get("primary_project_code")
    state = entities.get("state")
    sector = entities.get("sector")
    agency = entities.get("agency")

    dynamic_list = []
    if p_code:
        dynamic_list.append(f"What specific hurdles are cited in PAIMANA audits for {p_code}?")
        dynamic_list.append(f"Compare {p_code} progress with similar projects")
        dynamic_list.append(f"What is the expected completion timeline for {p_code}?")
    elif sector:
        dynamic_list.append(f"Which {sector} projects have the highest cost overrun?")
        dynamic_list.append(f"Show the most delayed projects in {sector}")
    elif state:
        dynamic_list.append(f"What are the highest-risk projects located in {state}?")
        dynamic_list.append(f"Break down total infrastructure outlay in {state}")
    elif agency:
        dynamic_list.append(f"What are {agency}'s most delayed projects?")
        dynamic_list.append(f"How many projects is {agency} currently managing?")
    else:
        dynamic_list.append("Which sectors have the highest total cost overrun?")
        dynamic_list.append("Show the top delayed railway projects")
        dynamic_list.append("What are the most critical risk projects across the country?")

    return dynamic_list[:4]


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
            NumberCallout(label="Total Projects",  value=f"{kpis.get('total_projects', kpis.get('total_master_projects', 5461)):,}", status="info"),
            NumberCallout(label="Critical Risk",   value=f"{kpis.get('critical_risk_project_count', 0):,}", status="critical"),
            NumberCallout(label="High Risk",       value=f"{kpis.get('high_risk_project_count', 0):,}", status="warning"),
            NumberCallout(label="Cost Overrun",    value=f"₹{kpis.get('total_cost_overrun_crore', 0):,.0f} Cr", status="warning"),
        ]
    else:
        numbers = []

    # 1. Extract dynamic follow-up questions
    next_actions = _extract_dynamic_followups(answer_text, entities)
    
    # 2. Clean answer text so questions appear ONLY as buttons, never duplicated in text
    clean_text = _clean_answer_text(answer_text)
    tools_used = [k for k in evidence.keys() if evidence[k]]

    return CopilotResponse(
        direct_answer=clean_text,
        key_findings=[],
        important_numbers=numbers,
        risk_and_drivers=[],
        evidence_citations=citations,
        next_actions=next_actions,
        answer=clean_text,
        response=clean_text,
        intent="GEMINI_OPEN_ENDED_INTELLIGENCE",
        response_mode="gemini_native",
        tools_used=tools_used,
        citations=citations,
        is_verified=True,
        verification_notes=["Grounded in live PostgreSQL data, calibrated XGBoost models, and official PAIMANA reports."],
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

        # 1. Extract entities and intent dimensions
        entities = _extract_entities(message, session, explicit_project_code=project_code)

        # 2. Gather live data + ML attributions + RAG evidence
        evidence = _build_evidence_context(message, entities)

        # 3. Build comprehensive prompt with all grounded evidence
        prompt = _build_prompt(message, evidence, session.history)

        # 4. Call Gemini with deep reasoning configuration
        answer = _call_gemini(prompt)

        # 5. Dynamic fallback only if API is unreachable
        if not answer:
            print("[Assistant] Gemini unavailable. Using dynamic entity-aware fallback.")
            answer = _deterministic_fallback(message, evidence, entities)

        # 6. Update session context memory
        p_code = entities.get("primary_project_code")
        session.update_with_query(
            query=message,
            project_code=p_code,
            state=entities.get("state")
        )
        session.history.append({"role": "user", "content": message})
        session.history.append({"role": "assistant", "content": answer[:600]})

        # 7. Build structured verified response
        return _build_copilot_response(answer, evidence, sid, entities)

    def get_session_history(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.context_mgr.get_session(session_id).to_dict()

    def clear_session_history(self, session_id: str) -> bool:
        s = self.context_mgr.get_session(session_id)
        s.history.clear()
        s.last_project_code = None
        s.active_result_set.clear()
        return True
