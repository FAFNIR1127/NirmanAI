import os
from typing import Dict, Any, Optional
from backend.app.schemas.assistant import EvidencePackageSchema

# Check for LLM Provider API Keys (dynamically checked on each call or init)
def get_api_keys():
    return {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY")
    }


class LLMService:
    """Orchestrates Gemini / OpenAI LLM providers with RAG evidence package grounding and deterministic fallback."""

    def __init__(self):
        self._log_provider_status()

    def _get_provider(self):
        keys = get_api_keys()
        if keys["GEMINI_API_KEY"]:
            return "gemini", keys["GEMINI_API_KEY"]
        elif keys["OPENAI_API_KEY"]:
            return "openai", keys["OPENAI_API_KEY"]
        return "deterministic_fallback", None

    def _log_provider_status(self):
        provider, _ = self._get_provider()
        print(f"[LLMService] Initialized with active LLM provider: {provider}")

    def generate_response(self, prompt_context: str, pkg: EvidencePackageSchema) -> str:
        """Generate grounded natural language answer from EvidencePackage via Gemini / OpenAI or Fallback."""
        
        # 1. Hallucination & Sufficiency Guard Check
        if pkg.evidence_sufficiency == "NONE":
            return (
                f"I could not find sufficient evidence in the Nirman database or historical PAIMANA reports "
                f"to answer your question regarding '{pkg.query}'. No matching project records or document excerpts were found."
            )

        provider, api_key = self._get_provider()

        # 2. Gemini LLM Integration (Free-Tier Compatible Models)
        if provider == "gemini" and api_key:
            # Free tier candidate models in preference order (Fastest & Free Tier Compliant)
            user_model = os.getenv("GEMINI_MODEL")
            candidate_models = [m for m in [user_model, "gemini-1.5-flash", "gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-pro"] if m]

            # Try new google-genai SDK first
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                
                system_instruction = (
                    "You are Nirman AI Copilot, an expert MoSPI infrastructure monitoring assistant. "
                    "Ground your answer strictly in the provided evidence package containing PostgreSQL database records, "
                    "XGBoost risk scores, SHAP feature attributions, and retrieved PAIMANA RAG document chunks. "
                    "Include document evidence citation tags like [E1], [E2] where applicable."
                )

                for model_name in candidate_models:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt_context,
                            config={"system_instruction": system_instruction, "temperature": 0.1}
                        )
                        if response and response.text:
                            return response.text.strip()
                    except Exception as model_err:
                        print(f"[LLMService] Gemini model '{model_name}' attempt failed ({model_err}). Trying fallback candidate...")
                        continue

            except ImportError:
                pass

            # Fallback to google.generativeai legacy SDK
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                for model_name in candidate_models:
                    try:
                        model = genai.GenerativeModel(model_name)
                        res = model.generate_content(prompt_context)
                        if res and res.text:
                            return res.text.strip()
                    except Exception:
                        continue
            except Exception as e:
                print(f"[LLMService] Gemini call failed ({e}). Falling back to Grounded Template Generator.")

        # 3. OpenAI Integration (Optional alternative)
        elif provider == "openai" and api_key:
            try:
                import openai
                client = openai.OpenAI(api_key=api_key)
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are Nirman AI Copilot, an expert infrastructure monitoring assistant. Answer grounded strictly in the provided evidence package and include citation tags like [E1], [E2]."},
                        {"role": "user", "content": prompt_context}
                    ],
                    temperature=0.1
                )
                return completion.choices[0].message.content.strip()
            except Exception as e:
                print(f"[LLMService] OpenAI call failed ({e}). Falling back to Grounded Template Generator.")

        # 4. Fallback: Deterministic Grounded Template Generator
        return self._generate_deterministic_template(pkg)

    def _generate_deterministic_template(self, pkg: EvidencePackageSchema) -> str:
        """Deterministic, template-driven grounded response generator for offline execution."""
        intent = pkg.intent
        p_code = pkg.entities.get("primary_project_code")

        lines = []

        if intent == "PROJECT_RISK_INFERENCE" or (intent == "HYBRID_MULTI_SOURCE" and pkg.risk_evidence):
            risk_item = pkg.risk_evidence[0] if pkg.risk_evidence else {}
            score = risk_item.get("risk_score", "N/A")
            cat = risk_item.get("risk_category", "N/A")
            prob = risk_item.get("risk_probability", "N/A")
            
            lines.append(f"Based on Nirman Risk Engine v1 analysis, project **{p_code}** has a risk score of **{score}/100** ({cat} risk level, probability: {prob}). [E1]")
            
            drivers = risk_item.get("risk_drivers", [])
            if drivers:
                top_d = []
                for d in drivers[:3]:
                    fname = d.get('feature_name') or d.get('feature_code') or d.get('feature', 'Risk Driver')
                    pts = d.get('points_added') or f"+{d.get('shap_impact', 0):.1f}"
                    top_d.append(f"{fname} ({pts})")
                lines.append(f"\n**Key Risk Drivers**: {', '.join(top_d)}.")

            protect = risk_item.get("protective_factors", [])
            if protect:
                top_p = []
                for p in protect[:2]:
                    fname = p.get('feature_name') or p.get('feature_code') or p.get('feature', 'Protective Factor')
                    pts = p.get('points_added') or f"{p.get('shap_impact', 0):.1f}"
                    top_p.append(f"{fname} ({pts})")
                lines.append(f"\n**Protective Factors**: {', '.join(top_p)}.")

            if pkg.document_evidence:
                doc = pkg.document_evidence[0]
                lines.append(f"\n\n**Historical Report Evidence**: According to {doc.get('source_file')} (Page {doc.get('page_number')}, {doc.get('reporting_month')}), historical observations show: \"{doc.get('content','')[:200]}...\" [E{len(pkg.structured_evidence)+len(pkg.risk_evidence)+1}]")

        elif intent == "STRUCTURED_ANALYTICS":
            data = pkg.structured_evidence[0] if pkg.structured_evidence else {}
            if "total_monitored_projects" in data:
                lines.append(f"Nirman Portfolio Executive Overview: Currently monitoring **{data.get('total_monitored_projects',0):,} projects** with total original cost of **₹{data.get('total_original_cost_cr',0):,.2f} Cr** and anticipated cost of **₹{data.get('total_anticipated_cost_cr',0):,.2f} Cr**. Total cost overrun stands at **{data.get('overall_cost_overrun_pct',0):.1f}%**. [E1]")
            elif "CRITICAL" in data or "HIGH" in data or "risk_categories" in str(data):
                lines.append(f"Project Risk Distribution across Portfolio: Total monitored projects categorized as Critical, High, Moderate, and Low risk based on ML Risk Engine v1 predictions. [E1]")
                for item in pkg.structured_evidence:
                    cat = item.get("risk_category")
                    if cat:
                        lines.append(f"- **{cat} Risk**: {item.get('project_count',0)} projects (Avg Score: {item.get('avg_risk_score',0):.1f}/100).")
            else:
                lines.append(f"Retrieved {len(pkg.structured_evidence)} structured data summaries matching your query. [E1]")

        elif intent == "COMPARATIVE_ANALYSIS":
            codes = pkg.entities.get("project_codes", [])
            lines.append(f"Comparative Analysis for Projects **{' vs '.join(codes)}**: [E1] [E2]")
            for item in pkg.structured_evidence:
                c = item.get("project_code") or item.get("code")
                n = item.get("project_name") or item.get("name")
                lines.append(f"\n- **Project {c} ({n})**: Sector: {item.get('sector','N/A')}, State: {item.get('state','N/A')}, Original Cost: ₹{item.get('original_cost',0)} Cr, Anticipated Cost: ₹{item.get('anticipated_cost',0)} Cr.")
            for item in pkg.risk_evidence:
                c = item.get("project_code")
                lines.append(f"  * Risk Score: **{item.get('risk_score')}/100** ({item.get('risk_category')}).")

        elif intent == "HISTORICAL_DOCUMENT_RAG" or intent == "EVIDENCE_CITATION":
            lines.append(f"Historical PAIMANA Report Search Results ({len(pkg.document_evidence)} document chunks retrieved):")
            for idx, doc in enumerate(pkg.document_evidence, start=len(pkg.structured_evidence)+len(pkg.risk_evidence)+1):
                lines.append(f"\n**[E{idx}] PAIMANA Report ({doc.get('reporting_month')}), Page {doc.get('page_number')}** ({doc.get('source_file')}):")
                lines.append(f"> \"{doc.get('content','')[:250]}...\"")

        else:
            lines.append(f"Retrieved grounded evidence matching '{pkg.query}'. [E1]")

        return "\n".join(lines)
