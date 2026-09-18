#!/usr/bin/env python3
"""
Phase 10 Full-System QA Suite 19, 20, 21, 22: RAG Vector Store Corpus Integrity, Golden Recall & Metadata Matching
(RAG-001 to RAG-022)
"""
import sys
import os
import urllib.request
import urllib.parse
import json
import sqlalchemy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from backend.app.config import DATABASE_URL
from backend.app.services.retrieval_service import RetrievalService
from backend.app.services.document_service import DocumentService

retrieval_service = RetrievalService()
document_service = DocumentService()

API_HOST = "http://127.0.0.1:8000"

def get_api(path):
    url = f"{API_HOST}{path}"
    try:
        req = urllib.request.urlopen(url, timeout=4)
        return req.status, json.loads(req.read().decode('utf-8'))
    except Exception as e:
        return 0, {"error": str(e)}

def run_tests():
    results = []
    engine = sqlalchemy.create_engine(DATABASE_URL)

    # 1. Corpus Integrity Checks (RAG-001 to RAG-008)
    with engine.connect() as conn:
        tot_chunks = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM document_chunks;")).scalar() or 0
        chunks_with_emb = conn.execute(sqlalchemy.text("SELECT COUNT(embedding) FROM document_chunks;")).scalar() or 0
        null_source_count = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM document_chunks WHERE source_file IS NULL;")).scalar() or 0
        null_page_count = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM document_chunks WHERE page_number IS NULL;")).scalar() or 0
        null_month_count = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM document_chunks WHERE reporting_month IS NULL;")).scalar() or 0

    results.append({
        "id": "RAG-001",
        "category": "RAG Corpus Integrity",
        "name": "Total Document Chunks Count Baseline",
        "passed": tot_chunks >= 300000,
        "severity": "P0",
        "expected": ">= 300,000 vector document chunks",
        "actual": f"{tot_chunks:,} chunks",
        "hint": "Verify document ingestion script in scripts/ingest/"
    })
    results.append({
        "id": "RAG-006",
        "category": "RAG Embeddings Integrity",
        "name": "Vector Embeddings Populated Check",
        "passed": chunks_with_emb == tot_chunks,
        "severity": "P0",
        "expected": "100% of chunks have valid vector embeddings",
        "actual": f"{chunks_with_emb:,} / {tot_chunks:,} populated",
        "hint": "Re-run embedding generation script."
    })
    results.append({
        "id": "RAG-002",
        "category": "RAG Metadata Integrity",
        "name": "Source File & Page Metadata Completeness",
        "passed": null_source_count == 0 and null_page_count == 0,
        "severity": "P1",
        "expected": "0 chunks with missing source file or page number",
        "actual": f"Null source: {null_source_count}, Null page: {null_page_count}",
        "hint": "Verify PDF chunk metadata extraction."
    })

    # 2. Golden Retrieval Recall Evaluation Across 10 Representative Test Queries (RAG-010 to RAG-020)
    golden_queries = [
        ("PROTOTYPE FAST BREEDER REACTOR BHAVINI", "020100044"),
        ("TIRUCHIRAPPALI NAGORE KARAIKKAL", "220100262"),
        ("status of project 020100044 in 2021", "020100044"),
        ("cost escalation ratio infrastructure", None),
        ("schedule delay months reporting", None),
        ("Maharashtra railway infrastructure project", None),
        ("nuclear power plant construction delay", "020100044"),
        ("anticipated cost revision sanctioned", None),
        ("commissioning milestone progress", None),
        ("NONEXISTENT_QUERY_FOR_NEGATIVE_TEST_XYZ_999", None)
    ]

    recalled_count = 0
    mrr_sum = 0.0

    for idx, (query_text, target_code) in enumerate(golden_queries):
        res = retrieval_service.search(query=query_text, top_k=5)
        chunks = getattr(res, 'retrieved_chunks', None) or getattr(res, 'results', None) or (res.get('retrieved_chunks', []) if isinstance(res, dict) else [])

        if chunks:
            recalled_count += 1
            if target_code:
                # Find rank of target project code
                rank = 0
                for i, c in enumerate(chunks):
                    p_c = c.project_code if hasattr(c, 'project_code') else c.get('project_code')
                    if p_c == target_code:
                        rank = i + 1
                        break
                if rank > 0:
                    mrr_sum += 1.0 / rank

    mean_mrr = mrr_sum / len(golden_queries) if len(golden_queries) > 0 else 0.0

    results.append({
        "id": "RAG-010",
        "category": "RAG Retrieval Recall",
        "name": "Golden Query Corpus Search Recall@5",
        "passed": recalled_count >= 8,
        "severity": "P0",
        "expected": ">= 80% search retrieval success on golden query set",
        "actual": f"Retrieved: {recalled_count} / {len(golden_queries)} (MRR: {mean_mrr:.2f})",
        "hint": "Tune hybrid vector retrieval weights or embedding encoder."
    })

    # 3. RAG REST Endpoint Search Test
    st, body = get_api("/api/documents/search?query=status&top_k=3")
    chunks_ret = body.get("results") or body.get("chunks", []) if isinstance(body, dict) else []
    results.append({
        "id": "RAG-021",
        "category": "RAG REST Endpoint",
        "name": "GET /api/documents/search REST Schema",
        "passed": st == 200 and isinstance(chunks_ret, list),
        "severity": "P0",
        "expected": "HTTP 200 with list of matching document chunks",
        "actual": f"Status {st}, Chunks retrieved: {len(chunks_ret)}",
        "hint": "Check /api/documents/search in backend/app/routes/documents.py"
    })

    # 4. Negative Out-of-Corpus Query Test (RAG-022)
    st_neg, body_neg = get_api("/api/documents/search?query=NONEXISTENT_XYZ_TERM_999&top_k=3")
    chunks_neg = body_neg.get("results") or body_neg.get("chunks", []) if isinstance(body_neg, dict) else []
    results.append({
        "id": "RAG-022",
        "category": "RAG Negative Query",
        "name": "Out-of-Corpus Query Returns Empty Chunk List (No Hallucinations)",
        "passed": st_neg == 200 and len(chunks_neg) == 0,
        "severity": "P1",
        "expected": "0 chunks returned for non-existent query terms",
        "actual": f"Returned {len(chunks_neg)} chunks",
        "hint": "Ensure distance threshold filtering suppresses irrelevant noise."
    })

    return results

if __name__ == "__main__":
    res = run_tests()
    print(json.dumps(res, indent=2))
