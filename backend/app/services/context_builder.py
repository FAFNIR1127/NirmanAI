from typing import List, Dict, Any
from backend.app.schemas.assistant import EvidencePackageSchema, CitationItem
from backend.app.services.citation_service import CitationService


class ContextBuilder:
    """Assembles EvidencePackage, evaluates evidence sufficiency, and builds prompt context."""

    def __init__(self):
        self.citation_service = CitationService()

    def assess_sufficiency(
        self,
        intent: str,
        entities: Dict[str, Any],
        evidence_blocks: List[Dict[str, Any]]
    ) -> str:
        """Evaluates whether retrieved evidence is sufficient to ground the answer."""
        if not evidence_blocks:
            return "NONE"

        p_code = entities.get("primary_project_code")

        # If a specific project was queried but no block references it
        if p_code and intent in ["PROJECT_RISK_INFERENCE", "HISTORICAL_DOCUMENT_RAG", "HYBRID_MULTI_SOURCE"]:
            matching = [b for b in evidence_blocks if b.get("project_code") == p_code]
            if not matching:
                return "LOW"
            if len(matching) >= 2 or intent == "PROJECT_RISK_INFERENCE":
                return "HIGH"
            return "MEDIUM"

        if len(evidence_blocks) >= 3:
            return "HIGH"
        elif len(evidence_blocks) >= 1:
            return "MEDIUM"

        return "LOW"

    def build_package(
        self,
        query: str,
        intent: str,
        entities: Dict[str, Any],
        structured_evidence: List[Dict[str, Any]],
        risk_evidence: List[Dict[str, Any]],
        document_evidence: List[Dict[str, Any]]
    ) -> EvidencePackageSchema:
        
        blocks, citations = self.citation_service.process_evidence(
            structured_evidence=structured_evidence,
            risk_evidence=risk_evidence,
            document_evidence=document_evidence
        )

        sufficiency = self.assess_sufficiency(intent, entities, blocks)

        return EvidencePackageSchema(
            query=query,
            intent=intent,
            entities=entities,
            structured_evidence=structured_evidence,
            risk_evidence=risk_evidence,
            document_evidence=document_evidence,
            citations=citations,
            evidence_sufficiency=sufficiency
        )

    def format_prompt_context(self, pkg: EvidencePackageSchema) -> str:
        """Format evidence package into structured text prompt for the LLM."""
        if pkg.evidence_sufficiency in ["NONE", "LOW"] and not pkg.citations:
            return (
                "INSUFFICIENT EVIDENCE WARNING:\n"
                "No relevant records or document chunks were found in the Nirman database or PAIMANA reports.\n"
                "State explicitly that sufficient evidence is not available to answer the question."
            )

        context_lines = [
            f"=== EVIDENCE PACKAGE (Sufficiency: {pkg.evidence_sufficiency}) ===",
            f"User Query: {pkg.query}",
            f"Classified Intent: {pkg.intent}",
            ""
        ]

        for cit in pkg.citations:
            context_lines.append(f"[{cit.citation_id}] {cit.title}")
            if cit.snippet:
                context_lines.append(f"Snippet: {cit.snippet.strip()}")
            context_lines.append("")

        context_lines.append("=== INSTRUCTIONS FOR LLM GENERATION ===")
        context_lines.append("1. Answer the query strictly relying on the evidence tagged [E1], [E2] above.")
        context_lines.append("2. Include citation tags (e.g. [E1]) immediately after factual claims.")
        context_lines.append("3. Do NOT invent dates, costs, project names, or reasons not backed by evidence.")
        context_lines.append("4. If the evidence does not establish a fact (e.g. who was responsible for delay), state that explicitly.")

        return "\n".join(context_lines)
