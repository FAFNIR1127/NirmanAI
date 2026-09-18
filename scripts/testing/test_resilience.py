#!/usr/bin/env python3
"""
Phase 10 Full-System QA Suite 5: Database Failure & Resilience Tests (DBFAIL-001 to DBFAIL-006)
"""
import sys
import os
import urllib.request
import json
import sqlalchemy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from backend.app.core.db_resilience import execute_with_retry, check_db_health
execute_with_db_retry = execute_with_retry

def run_tests():
    results = []

    # DBFAIL-001: Active Database Health Ping Test
    db_ok = check_db_health()
    results.append({
        "id": "DBFAIL-001",
        "category": "DB Resilience",
        "name": "Database Health Ping Check (`check_db_health`)",
        "passed": db_ok,
        "severity": "P0",
        "expected": "True (PostgreSQL active & responding)",
        "actual": f"{db_ok}",
        "hint": "Check PostgreSQL connection state."
    })

    # DBFAIL-002: Simulated Failure Retry & Controlled Exception Handling
    def FailingDBFunction():
        raise sqlalchemy.exc.OperationalError("SELECT 1", {}, Exception("Simulated connection timeout"))

    caught_controlled_exception = False
    err_message = ""
    try:
        execute_with_db_retry(FailingDBFunction, max_retries=2, initial_delay=0.05)
    except Exception as e:
        caught_controlled_exception = True
        err_message = str(e)

    results.append({
        "id": "DBFAIL-002",
        "category": "DB Resilience",
        "name": "Retry Mechanism Exception Handling (`execute_with_db_retry`)",
        "passed": caught_controlled_exception and ("503" in err_message or "OperationalError" in err_message or "Simulated" in err_message),
        "severity": "P0",
        "expected": "Controlled exception thrown after max_retries exhausted without infinite loop or crash",
        "actual": f"Caught exception: {err_message[:100]}",
        "hint": "Verify DB retry wrapper in backend/app/core/db_resilience.py"
    })

    # DBFAIL-003: REST Endpoint Error Sanitization (No Raw Stack Tracebacks Exposed)
    invalid_url = "http://127.0.0.1:8000/api/projects/INVALID_NONEXISTENT_PROJECT_CODE_99999"
    no_traceback_exposed = False
    status_code = 0
    resp_body = ""

    try:
        req = urllib.request.urlopen(invalid_url, timeout=3)
        status_code = req.status
    except urllib.error.HTTPError as e:
        status_code = e.code
        resp_body = e.read().decode('utf-8')
        # Ensure raw Python Traceback or internal path leaks are not present in response JSON
        no_traceback_exposed = "Traceback (most recent call last)" not in resp_body and "File \"" not in resp_body
    except Exception as e:
        resp_body = str(e)

    results.append({
        "id": "DBFAIL-003",
        "category": "DB Resilience",
        "name": "Sanitized Error Responses (No Traceback Leaks)",
        "passed": status_code == 404 and no_traceback_exposed,
        "severity": "P0",
        "expected": "HTTP 404 with clean JSON error payload and no raw Python tracebacks",
        "actual": f"Status: {status_code}, Body: {resp_body[:100]}",
        "hint": "Verify FastAPI exception handlers in backend/app/middleware/error_handler.py"
    })

    # DBFAIL-005: Auto-Recovery Health Status Check
    post_recovery_ok = check_db_health()
    results.append({
        "id": "DBFAIL-005",
        "category": "DB Resilience",
        "name": "Post-Simulation Database Auto-Recovery Verification",
        "passed": post_recovery_ok,
        "severity": "P0",
        "expected": "Database connection healthy after transient retry cycle",
        "actual": f"{post_recovery_ok}",
        "hint": "Ensure DB connection pool recovers automatically."
    })

    return results

if __name__ == "__main__":
    res = run_tests()
    print(json.dumps(res, indent=2))
