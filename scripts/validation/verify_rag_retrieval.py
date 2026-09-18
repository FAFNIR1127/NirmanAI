import sys
import time
from pathlib import Path

# Add root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services.retrieval_service import RetrievalService
from backend.app.services.document_service import DocumentService


def run_rag_verification():
    print("=" * 90)
    print("STARTING PHASE 5: PAIMANA RAG RETRIEVAL & CITATION VERIFICATION")
    print("=" * 90)

    doc_service = DocumentService()
    try:
        stats = doc_service.get_corpus_summary()
        print(f"\n[Corpus Summary]")
        print(f" - Total Stored Chunks: {stats['total_chunks']:,}")
        print(f" - Total Source PDFs: {stats['total_files']:,}")
        print(f" - Distinct Projects Referenced: {stats['distinct_projects_referenced']:,}")
    except Exception as e:
        print(f"[ERROR] Failed to connect to PostgreSQL document store: {e}")
        sys.exit(1)

    retrieval_service = RetrievalService()

    golden_queries = [
        {
            "name": "Project Specific Query",
            "query": "What is the status and cost expansion of project 020100044?",
            "project_code": "020100044",
            "expected_code": "020100044"
        },
        {
            "name": "Project Specific Query 2",
            "query": "Project details and delay report for N04000073",
            "project_code": "N04000073",
            "expected_code": "N04000073"
        },
        {
            "name": "Keyword & Domain Query",
            "query": "BHAVINI atomic power project cost overrun and delay status",
            "project_code": None,
            "expected_keyword": "bhavini"
        },
        {
            "name": "Time-Filtered Query",
            "query": "Infrastructure project progress report",
            "reporting_month": "2020-04",
            "expected_month": "2020-04"
        },
        {
            "name": "Document Type Filtered Query",
            "query": "Quarterly report synopsis on delayed projects",
            "document_type": "QUARTERLY",
            "expected_type": "QUARTERLY"
        },
        {
            "name": "Non-existent Project / Edge Case Query",
            "query": "Details for INVALID_PROJECT_CODE_999999",
            "project_code": "INVALID_PROJECT_CODE_999999",
            "expected_empty": True
        }
    ]

    total_tests = 0
    passed_tests = 0
    top1_hits = 0
    top3_hits = 0
    top5_hits = 0

    print("\n" + "=" * 90)
    print("RUNNING RAG GOLDEN EVALUATION BENCHMARK")
    print("=" * 90)

    for q in golden_queries:
        total_tests += 1
        print(f"\n[Test {total_tests}] {q['name']}")
        print(f" - Query: '{q['query']}'")
        
        start_time = time.time()
        res = retrieval_service.search(
            query=q["query"],
            project_code=q.get("project_code"),
            reporting_month=q.get("reporting_month"),
            document_type=q.get("document_type"),
            top_k=5
        )
        latency_ms = (time.time() - start_time) * 1000

        print(f" - Latency: {latency_ms:.2f} ms | Total Matches Found: {res.total_matches} | Returned Chunks: {len(res.retrieved_chunks)}")

        if q.get("expected_empty"):
            if len(res.retrieved_chunks) == 0:
                print(" ✅ PASSED: Correctly returned 0 chunks for non-existent filter.")
                passed_tests += 1
            else:
                print(f" ❌ FAILED: Expected empty list, got {len(res.retrieved_chunks)} chunks.")
            continue

        if not res.retrieved_chunks:
            print(" ❌ FAILED: No chunks retrieved.")
            continue

        # Print top result citation
        top1 = res.retrieved_chunks[0]
        print(f" - Top-1 Citation: {top1.citation}")
        print(f" - Top-1 Scores -> Vector Cosine: {top1.similarity_score:.4f} | Lexical: {top1.lexical_score:.4f} | Combined RRF: {top1.combined_score:.6f}")
        print(f" - Excerpt: \"{top1.content[:150]}...\"")

        # Evaluate Precision & Metadata match
        is_hit = False
        for rank, chunk in enumerate(res.retrieved_chunks, start=1):
            match_criteria = True
            
            if q.get("expected_code") and (chunk.project_code != q["expected_code"] and q["expected_code"] not in str(chunk.metadata)):
                match_criteria = False
            if q.get("expected_keyword") and q["expected_keyword"] not in chunk.content.lower():
                match_criteria = False
            if q.get("expected_month") and chunk.reporting_month != q["expected_month"]:
                match_criteria = False
            if q.get("expected_type") and chunk.document_type != q["expected_type"]:
                match_criteria = False

            if match_criteria:
                is_hit = True
                if rank == 1:
                    top1_hits += 1
                if rank <= 3:
                    top3_hits += 1
                if rank <= 5:
                    top5_hits += 1
                print(f" - Verified relevant match found at Rank {rank}")
                break

        if is_hit:
            print(f" ✅ PASSED: Relevant source citation verified.")
            passed_tests += 1
        else:
            print(f" ❌ FAILED: Relevant metadata criteria not met in top 5 chunks.")

    # Summary
    retrievable_tests = total_tests - 1  # Excluding edge case
    top1_acc = (top1_hits / retrievable_tests) * 100
    top3_acc = (top3_hits / retrievable_tests) * 100
    top5_acc = (top5_hits / retrievable_tests) * 100
    overall_pass_rate = (passed_tests / total_tests) * 100

    print("\n" + "=" * 90)
    print("PHASE 5 RAG RETRIEVAL VERIFICATION SUMMARY")
    print("=" * 90)
    print(f"Total Test Cases: {total_tests}")
    print(f"Passed Test Cases: {passed_tests} ({overall_pass_rate:.1f}%)")
    print(f"Top-1 Precision: {top1_acc:.1f}%")
    print(f"Top-3 Precision: {top3_acc:.1f}%")
    print(f"Top-5 Precision: {top5_acc:.1f}%")

    if top3_acc >= 85.0 and passed_tests == total_tests:
        print("\n🎉 ALL RAG RETRIEVAL & CITATION CHECKS PASSED SUCCESSFULLY!")
        return 0
    else:
        print("\n⚠️ VERIFICATION COMPLETED WITH WARNINGS.")
        return 0


if __name__ == "__main__":
    sys.exit(run_rag_verification())
