from typing import List, Dict, Any, Tuple
from backend.app.schemas.assistant import CitationItem


class CitationService:
    """Builds deterministic, verifiable citation objects and formats evidence tags ([E1], [E2])."""

    def process_evidence(
        self,
        structured_evidence: List[Any],
        risk_evidence: List[Any],
        document_evidence: List[Any]
    ) -> Tuple[List[Dict[str, Any]], List[CitationItem]]:
        
        def _flatten(items):
            flat = []
            for it in items:
                if isinstance(it, list):
                    flat.extend(_flatten(it))
                elif isinstance(it, dict):
                    flat.append(it)
            return flat

        structured_evidence = _flatten(structured_evidence)
        risk_evidence = _flatten(risk_evidence)
        document_evidence = _flatten(document_evidence)

        formatted_evidence_blocks = []
        citation_items = []
        counter = 1

        # 1. Process Structured Database Evidence
        for idx, item in enumerate(structured_evidence):
            e_id = f"E{counter}"
            counter += 1
            
            p_code = item.get("project_code") or item.get("code")
            p_name = item.get("project_name") or item.get("name") or "Database Record"
            
            title = f"Nirman DB — {p_name}" + (f" ({p_code})" if p_code else "")
            
            cit = CitationItem(
                citation_id=e_id,
                title=title,
                project_code=p_code,
                snippet=str(item)[:250]
            )
            citation_items.append(cit)

            formatted_evidence_blocks.append({
                "id": e_id,
                "type": "STRUCTURED_DB",
                "title": title,
                "project_code": p_code,
                "data": item
            })

        # 2. Process ML Risk Engine Evidence
        for idx, item in enumerate(risk_evidence):
            e_id = f"E{counter}"
            counter += 1

            p_code = item.get("project_code")
            p_score = item.get("risk_score")
            p_cat = item.get("risk_category")
            
            title = f"Risk Engine v1 — Project {p_code} (Score: {p_score}/100, Category: {p_cat})"
            
            cit = CitationItem(
                citation_id=e_id,
                title=title,
                project_code=p_code,
                snippet=f"Risk Score: {p_score}/100 ({p_cat}). Top Drivers: {', '.join([d.get('feature','') for d in item.get('risk_drivers',[])[:3]])}"
            )
            citation_items.append(cit)

            formatted_evidence_blocks.append({
                "id": e_id,
                "type": "RISK_MODEL",
                "title": title,
                "project_code": p_code,
                "data": item
            })

        # 3. Process RAG Document Evidence
        for idx, item in enumerate(document_evidence):
            e_id = f"E{counter}"
            counter += 1

            src = item.get("source_file", "PAIMANA PDF")
            page = item.get("page_number", 1)
            month = item.get("reporting_month", "Unknown")
            p_code = item.get("project_code")
            doc_type = item.get("document_type", "PRIMARY_DETAILED")
            content = item.get("content", "")

            p_str = f" - Project {p_code}" if p_code else ""
            title = f"PAIMANA Report ({month}), File: {src}, Page {page}{p_str}"

            cit = CitationItem(
                citation_id=e_id,
                title=title,
                source_file=src,
                page_number=page,
                reporting_month=month,
                project_code=p_code,
                document_type=doc_type,
                snippet=content[:200]
            )
            citation_items.append(cit)

            formatted_evidence_blocks.append({
                "id": e_id,
                "type": "DOCUMENT_RAG",
                "title": title,
                "source_file": src,
                "page_number": page,
                "reporting_month": month,
                "project_code": p_code,
                "content": content
            })

        return formatted_evidence_blocks, citation_items
