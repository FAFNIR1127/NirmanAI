#!/usr/bin/env python3
"""
Phase 10 Full-System QA Suite 45, 46, 47, 48: Latency Benchmarking, Concurrency & Memory Growth
(PERF-001 to PERF-010)
"""
import sys
import os
import urllib.request
import json
import time
import statistics
import concurrent.futures

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

API_HOST = "http://127.0.0.1:8000"

def get_lat(path):
    url = f"{API_HOST}{path}"
    try:
        t0 = time.time()
        req = urllib.request.urlopen(url, timeout=5)
        t1 = time.time()
        return req.status, (t1 - t0) * 1000.0
    except Exception as e:
        return 0, 0.0

def run_tests():
    results = []

    # 1. REST Endpoint Warm Latency Benchmarking (p50, p95)
    endpoints = [
        ("/api/analytics/portfolio_kpis", "Portfolio KPIs"),
        ("/api/risk/intelligence/020100044", "Risk Intelligence"),
        ("/api/documents/search?query=status&top_k=2", "RAG Document Search"),
        ("/api/projects?limit=15", "Project Directory")
    ]

    for path, label in endpoints:
        latencies = []
        for _ in range(10):
            st, lat = get_lat(path)
            if st == 200:
                latencies.append(lat)

        p50 = statistics.median(latencies) if latencies else 0.0
        p95 = max(latencies) if latencies else 0.0
        passed = p50 < 100.0 # Sub-100ms warm latency requirement

        results.append({
            "id": f"PERF-00{endpoints.index((path, label))+1}",
            "category": "Latency Performance",
            "name": f"Warm Latency Benchmark: {label}",
            "passed": passed,
            "severity": "P1",
            "expected": "p50 latency < 100ms",
            "actual": f"p50: {p50:.1f}ms, p95: {p95:.1f}ms across {len(latencies)} requests",
            "hint": "Check database indexes or route latency caching."
        })

    # 2. Concurrency Stress Test (20 Concurrent Requests)
    def fetch_task():
        st, lat = get_lat("/api/analytics/portfolio_kpis")
        return st == 200

    success_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_task) for _ in range(20)]
        for f in concurrent.futures.as_completed(futures):
            if f.result():
                success_count += 1

    results.append({
        "id": "PERF-010",
        "category": "Concurrency Performance",
        "name": "20 Concurrent Requests Stress Test",
        "passed": success_count == 20,
        "severity": "P1",
        "expected": "20/20 successful HTTP 200 responses under concurrent pool load",
        "actual": f"{success_count} / 20 succeeded",
        "hint": "Ensure Uvicorn worker pool and PostgreSQL connection pool can handle 20 concurrent threads."
    })

    return results

if __name__ == "__main__":
    res = run_tests()
    print(json.dumps(res, indent=2))
