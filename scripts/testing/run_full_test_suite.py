#!/usr/bin/env python3
"""
Project Nirman — Phase 10 Master Full-System QA Test Runner
Executes all 15 test suites, isolates defects layer-by-layer, and generates documentation/phase10_full_system_qa.md.
"""
import sys
import os
import time
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

import test_environment
import test_database
import test_data_integrity
import test_resilience
import test_api
import test_analytics
import test_risk_engine
import test_risk_intelligence
import test_rag
import test_assistant
import test_security
import test_cache
import test_frontend
import test_performance
import test_regression
import test_e2e

import subprocess
import urllib.request

def ensure_server_running():
    try:
        req = urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2)
        if req.status == 200:
            return
    except Exception:
        pass

    print("🚀 Starting FastAPI Uvicorn Server on http://0.0.0.0:8000 for QA Test Suite ...")
    cmd = [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    subprocess.Popen(cmd, cwd=BASE_DIR)
    time.sleep(4)

def main():
    print("===========================================================================")
    print("      PROJECT NIRMAN — PHASE 10 FULL SYSTEM QA & DEFECT ISOLATION          ")
    print("===========================================================================\n")

    ensure_server_running()

    suites = [
        ("0. Environment Validation", test_environment.run_tests),
        ("1. Database Schema & Indexes", test_database.run_tests),
        ("2. Data Integrity & Constraints", test_data_integrity.run_tests),
        ("3. Database Resilience", test_resilience.run_tests),
        ("4. REST API Contracts & Bounds", test_api.run_tests),
        ("5. Analytics Ground-Truth", test_analytics.run_tests),
        ("6. ML Risk Engine Invariants", test_risk_engine.run_tests),
        ("7. Risk Intelligence & Briefings", test_risk_intelligence.run_tests),
        ("8. RAG Vector Store & Recall", test_rag.run_tests),
        ("9. AI Assistant & Citations", test_assistant.run_tests),
        ("10. Security Test Matrix", test_security.run_tests),
        ("11. Cache Correctness", test_cache.run_tests),
        ("12. Frontend SPA Delivery", test_frontend.run_tests),
        ("13. Latency & Concurrency", test_performance.run_tests),
        ("14. Model Regression & Leakage", test_regression.run_tests),
        ("15. End-to-End User Journeys", test_e2e.run_tests)
    ]

    all_results = []
    category_summary = {}

    start_time = time.time()

    for suite_name, suite_fn in suites:
        print(f"▶ Running Suite: {suite_name} ...", end=" ", flush=True)
        try:
            res_list = suite_fn()
            all_results.extend(res_list)
            
            suite_passed = sum(1 for r in res_list if r["passed"])
            suite_total = len(res_list)
            category_summary[suite_name] = {"passed": suite_passed, "total": suite_total}

            status_str = f"✅ PASSED ({suite_passed}/{suite_total})" if suite_passed == suite_total else f"⚠️ ISSUES ({suite_passed}/{suite_total})"
            print(status_str)
        except Exception as e:
            print(f"❌ ERROR: {e}")
            category_summary[suite_name] = {"passed": 0, "total": 1, "error": str(e)}

    elapsed_sec = time.time() - start_time

    total_tests = len(all_results)
    total_passed = sum(1 for r in all_results if r["passed"])
    total_failed = total_tests - total_passed
    pass_rate = (total_passed / total_tests * 100.0) if total_tests > 0 else 0.0

    p0_failures = [r for r in all_results if not r["passed"] and r.get("severity") == "P0"]
    p1_failures = [r for r in all_results if not r["passed"] and r.get("severity") == "P1"]
    p2_failures = [r for r in all_results if not r["passed"] and r.get("severity") == "P2"]

    is_ready = total_failed == 0

    print("\n===========================================================================")
    print("                     NIRMAN FULL SYSTEM QA REPORT                           ")
    print("===========================================================================")
    print(f"Total Test Cases Run:   {total_tests}")
    print(f"Passed:                 {total_passed}")
    print(f"Failed:                 {total_failed}")
    print(f"Pass Rate:              {pass_rate:.2f}%")
    print(f"P0 Critical Failures:   {len(p0_failures)}")
    print(f"P1 High Failures:       {len(p1_failures)}")
    print(f"P2 Medium Failures:     {len(p2_failures)}")
    print(f"Execution Time:         {elapsed_sec:.2f} seconds")
    print("===========================================================================")
    if is_ready:
        print("STATUS: ✅ PRODUCTION READY — ALL STACK LAYERS VERIFIED 100%\n")
    else:
        print("STATUS: ❌ DEPLOYMENT BLOCKED — DEFECTS DETECTED\n")

    # Generate Report File: documentation/phase10_full_system_qa.md
    doc_dir = os.path.join(BASE_DIR, "documentation")
    os.makedirs(doc_dir, exist_ok=True)
    report_path = os.path.join(doc_dir, "phase10_full_system_qa.md")

    md_lines = []
    md_lines.append("# Project Nirman — Phase 10 Full-System QA & Defect-Isolation Report\n")
    md_lines.append(f"**Execution Timestamp**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    md_lines.append(f"**Overall System Status**: {'✅ **PRODUCTION READY**' if is_ready else '❌ **DEPLOYMENT BLOCKED**'}\n")
    md_lines.append(f"**Total Pass Rate**: `{pass_rate:.2f}%` ({total_passed}/{total_tests} Test Cases Passed)\n")
    md_lines.append("---\n")

    md_lines.append("## Executive Summary & Severity Breakdown\n")
    md_lines.append("| Metric | Value | Status |")
    md_lines.append("| :--- | :--- | :--- |")
    md_lines.append(f"| **Total Executed Tests** | `{total_tests}` | Complete |")
    md_lines.append(f"| **Passed Test Cases** | `{total_passed}` | {'✅ PASS' if total_passed == total_tests else '⚠️ ISSUES'} |")
    md_lines.append(f"| **Failed Test Cases** | `{total_failed}` | {'✅ ZERO' if total_failed == 0 else '❌ DEFECTS'} |")
    md_lines.append(f"| **P0 Critical Failures** | `{len(p0_failures)}` | {'✅ NONE' if len(p0_failures) == 0 else '❌ CRITICAL'} |")
    md_lines.append(f"| **P1 High Failures** | `{len(p1_failures)}` | {'✅ NONE' if len(p1_failures) == 0 else '⚠️ REVIEW'} |")
    md_lines.append(f"| **P2 Medium Failures** | `{len(p2_failures)}` | {'✅ NONE' if len(p2_failures) == 0 else 'ℹ️ MINOR'} |")
    md_lines.append(f"| **Execution Duration** | `{elapsed_sec:.2f}s` | Verified |\n")

    md_lines.append("## Suite-by-Suite Test Coverage Summary\n")
    md_lines.append("| Test Suite | Passed | Total | Pass Rate | Status |")
    md_lines.append("| :--- | :---: | :---: | :---: | :--- |")

    for s_name, s_info in category_summary.items():
        p_cnt = s_info["passed"]
        t_cnt = s_info["total"]
        pct = (p_cnt / t_cnt * 100.0) if t_cnt > 0 else 0.0
        st_icon = "✅ PASSED" if p_cnt == t_cnt else "❌ DEFECTS"
        md_lines.append(f"| **{s_name}** | {p_cnt} | {t_cnt} | {pct:.1f}% | {st_icon} |")

    md_lines.append("\n---\n")
    md_lines.append("## Comprehensive Test Cases Log\n")
    md_lines.append("| ID | Category | Test Case Name | Severity | Status | Actual Result / Diagnostic Hint |")
    md_lines.append("| :--- | :--- | :--- | :---: | :---: | :--- |")

    for r in all_results:
        st_badge = "✅ PASS" if r["passed"] else "❌ FAIL"
        sev = r.get("severity", "P2")
        actual_str = r.get("actual", "")
        hint_str = f" (*Hint: {r.get('hint')}*)" if not r["passed"] and r.get("hint") else ""
        md_lines.append(f"| `{r['id']}` | {r['category']} | {r['name']} | **{sev}** | {st_badge} | {actual_str}{hint_str} |")

    with open(report_path, "w") as f:
        f.write("\n".join(md_lines))

    print(f"📄 Detailed QA Report generated at: {report_path}\n")

if __name__ == "__main__":
    main()
