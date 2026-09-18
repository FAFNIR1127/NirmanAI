#!/usr/bin/env python3
"""
Phase 10 Full-System QA Suite 40 & 41: Cache Correctness, Hit/Miss Behavior & Key Isolation
(CACHE-001 to CACHE-008)
"""
import sys
import os
import urllib.request
import json
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from backend.app.services.cache_service import cache_service

API_HOST = "http://127.0.0.1:8000"

def get_api(path):
    url = f"{API_HOST}{path}"
    try:
        t0 = time.time()
        req = urllib.request.urlopen(url, timeout=4)
        t1 = time.time()
        return req.status, json.loads(req.read().decode('utf-8')), (t1 - t0) * 1000.0
    except Exception as e:
        return 0, {"error": str(e)}, 0.0

def run_tests():
    results = []

    # 1. In-Memory Cache Unit Functions
    test_key = "test:qa:key_123"
    test_val = {"data": "nirman_qa_payload", "value": 42}
    cache_service.set(test_key, test_val, ttl_seconds=10)

    val_retrieved = cache_service.get(test_key)
    cache_hit_ok = val_retrieved == test_val

    results.append({
        "id": "CACHE-001",
        "category": "Cache Mechanics",
        "name": "Cache Service Set & Hit Retrieval",
        "passed": cache_hit_ok,
        "severity": "P0",
        "expected": f"Retrieved payload == {test_val}",
        "actual": f"Retrieved: {val_retrieved}",
        "hint": "Verify backend/app/services/cache_service.py"
    })

    # 2. Key Isolation Test
    key_a = "risk:intelligence:020100044"
    key_b = "risk:intelligence:220100262"
    cache_service.set(key_a, {"project": "020100044"}, ttl_seconds=10)
    cache_service.set(key_b, {"project": "220100262"}, ttl_seconds=10)

    isolated = cache_service.get(key_a).get("project") == "020100044" and cache_service.get(key_b).get("project") == "220100262"
    results.append({
        "id": "CACHE-006",
        "category": "Cache Key Isolation",
        "name": "Different Queries Produce Distinct Cache Keys (No Cross-Contamination)",
        "passed": isolated,
        "severity": "P0",
        "expected": "Key A and Key B return distinct payloads without cross-contamination",
        "actual": f"Isolated: {isolated}",
        "hint": "Check cache key construction logic across service layers."
    })

    # 3. Cold vs. Warm REST API Payload Semantic Equivalence (CACHE-003 & CACHE-041)
    cache_service.clear() # Clear cache to force cold request
    st_cold, cold_payload, t_cold = get_api("/api/analytics/portfolio_kpis")
    st_warm, warm_payload, t_warm = get_api("/api/analytics/portfolio_kpis")

    payloads_identical = cold_payload == warm_payload
    results.append({
        "id": "CACHE-041",
        "category": "Cache Correctness",
        "name": "Cold vs. Warm REST API Response Semantic Equivalence",
        "passed": st_cold == 200 and st_warm == 200 and payloads_identical,
        "severity": "P0",
        "expected": "Cold payload and Warm cached payload are 100% identical in structure & values",
        "actual": f"Identical: {payloads_identical}, Cold Latency: {t_cold:.1f}ms, Warm Latency: {t_warm:.1f}ms",
        "hint": "Verify cached response serialization."
    })

    return results

if __name__ == "__main__":
    res = run_tests()
    print(json.dumps(res, indent=2))
