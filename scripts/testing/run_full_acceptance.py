"""
scripts/testing/run_full_acceptance.py

Phase 13 Full Master System Acceptance Suite.
Runs all test suites across the Nirman platform (Phases 1-13) and produces a machine-readable summary.
"""

import os
import sys
import time
import urllib.request
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "scripts", "testing"))

import test_copilot_v2_eval
import test_database
import test_risk_engine
import test_rag
import test_api
import test_analytics
import test_assistant


def ensure_server_running():
    try:
        req = urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2)
        if req.status == 200:
            return
    except Exception:
        pass

    print("🚀 Starting FastAPI Uvicorn Server on http://0.0.0.0:8000 for Master Acceptance ...")
    cmd = [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    subprocess.Popen(cmd, cwd=BASE_DIR)
    time.sleep(3)


def run_all():
    print("======================================================================")
    print("          NIRMAN MASTER SYSTEM ACCEPTANCE TEST HARNESS               ")
    print("======================================================================")

    ensure_server_running()

    all_results = []
    suites = [
        ("Phase 13 AI Copilot v2 Intelligence (Categories A-K)", test_copilot_v2_eval.run_tests),
        ("Database Schema & PostgreSQL Integrity", test_database.run_tests),
        ("XGBoost Risk Engine v1 & SHAP Attribution", test_risk_engine.run_tests),
        ("RAG Hybrid Vector Search & RRF", test_rag.run_tests),
        ("REST API Contracts & Health", test_api.run_tests),
        ("Analytics Ground-Truth & KPIs", test_analytics.run_tests),
        ("Assistant Service Integration & Citations", test_assistant.run_tests),
    ]

    total_passed = 0
    total_failed = 0

    for name, runner_fn in suites:
        print(f"\n--- Running: {name} ---")
        try:
            res_list = runner_fn()
            p = sum(1 for r in res_list if (r.get("passed") is True or r.get("status") == "PASS"))
            f = sum(1 for r in res_list if not (r.get("passed") is True or r.get("status") == "PASS"))
            total_passed += p
            total_failed += f
            all_results.extend(res_list)
            print(f"Sub-suite Status: {p} Passed, {f} Failed.")
        except Exception as e:
            print(f"Sub-suite Execution Error: {e}")
            total_failed += 1

    total_tests = total_passed + total_failed
    pass_rate = (total_passed / total_tests) * 100.0 if total_tests > 0 else 0.0

    print("\n======================================================================")
    print(f"Total Master Tests Executed : {total_tests}")
    print(f"Master Tests Passed         : {total_passed}")
    print(f"Master Tests Failed         : {total_failed}")
    print(f"Master Pass Rate            : {pass_rate:.1f}%")
    print("======================================================================")

    if total_failed == 0:
        print("🎉 MASTER ACCEPTANCE SUCCESSFUL — ALL PHASES (1-13) PASSED VERIFICATION.")
        sys.exit(0)
    else:
        print("❌ MASTER ACCEPTANCE FAILED — RESOLVE TEST FAILURES BEFORE DEPLOYMENT.")
        sys.exit(1)


if __name__ == "__main__":
    run_all()
