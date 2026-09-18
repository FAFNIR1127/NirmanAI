#!/usr/bin/env python3
"""
Phase 10 Full-System QA Suite 42 & 43: Security Test Matrix, Headers, Rate Limiting & Input Sanitization
(SEC-001 to SEC-015)
"""
import sys
import os
import urllib.request
import urllib.parse
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

API_HOST = "http://127.0.0.1:8000"

def get(path):
    url = f"{API_HOST}{path}"
    try:
        req = urllib.request.urlopen(url, timeout=4)
        return req.status, dict(req.headers), req.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode('utf-8')
    except Exception as e:
        return 0, {}, str(e)

def post_raw(path, body_bytes, headers_dict=None):
    url = f"{API_HOST}{path}"
    hdrs = {'Content-Type': 'application/json'}
    if headers_dict:
        hdrs.update(headers_dict)
    req = urllib.request.Request(url, data=body_bytes, headers=hdrs, method='POST')
    try:
        res = urllib.request.urlopen(req, timeout=4)
        return res.status, dict(res.headers), res.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode('utf-8')
    except Exception as e:
        return 0, {}, str(e)

def run_tests():
    results = []

    # 1. Security HTTP Headers (SEC-001)
    st, hdrs, body = get("/api/health")
    has_xcto = "x-content-type-options" in [k.lower() for k in hdrs.keys()]
    has_xfo = "x-frame-options" in [k.lower() for k in hdrs.keys()]

    results.append({
        "id": "SEC-001",
        "category": "Security HTTP Headers",
        "name": "Security Headers Present (X-Content-Type-Options & X-Frame-Options)",
        "passed": st == 200 and has_xcto and has_xfo,
        "severity": "P0",
        "expected": "HTTP headers contain X-Content-Type-Options and X-Frame-Options",
        "actual": f"Headers present: X-CTO={has_xcto}, X-FO={has_xfo}",
        "hint": "Check SecurityHeadersMiddleware in backend/app/middleware/security.py"
    })

    # 2. Rate Limiting Headers (SEC-002)
    has_rate_hdr = any("ratelimit" in k.lower() for k in hdrs.keys())
    results.append({
        "id": "SEC-002",
        "category": "Rate Limiting",
        "name": "Rate Limiting Response Headers Attached",
        "passed": st == 200 and has_rate_hdr,
        "severity": "P1",
        "expected": "HTTP headers contain X-RateLimit-Limit or X-RateLimit-Remaining",
        "actual": f"Rate limit headers attached: {has_rate_hdr}",
        "hint": "Check RateLimitingMiddleware in backend/app/middleware/security.py"
    })

    # 3. SQL Injection Security Test (SEC-003)
    sqli_string = urllib.parse.quote("SELECT * FROM projects WHERE project_code = '020100044' UNION SELECT 1,2,3;")
    st_sqli, hdrs_sqli, body_sqli = get(f"/api/projects/search?q={sqli_string}")
    passed_sqli = st_sqli == 200 and "Traceback" not in body_sqli

    results.append({
        "id": "SEC-003",
        "category": "Input Security",
        "name": "SQL Injection Attack Payload Resistance",
        "passed": passed_sqli,
        "severity": "P0",
        "expected": "HTTP 200 with sanitized query execution and zero SQL tracebacks",
        "actual": f"Status: {st_sqli}, Sanitized output verified: {passed_sqli}",
        "hint": "Ensure parameterized queries are used across query services."
    })

    # 4. Cross-Site Scripting (XSS) Input Test (SEC-004)
    xss_payload = urllib.parse.quote("<script>alert('XSS_ATTACK')</script>")
    st_xss, hdrs_xss, body_xss = get(f"/api/projects/search?q={xss_payload}")
    passed_xss = st_xss == 200 and "<script>" not in body_xss

    results.append({
        "id": "SEC-004",
        "category": "Input Security",
        "name": "XSS Script Injection Payload Resistance",
        "passed": passed_xss,
        "severity": "P0",
        "expected": "HTML tags sanitized or escaped",
        "actual": f"Status: {st_xss}, Unescaped script tags: {not passed_xss}",
        "hint": "Ensure query search escapes or strips HTML markup."
    })

    # 5. Path Traversal Guard (SEC-005)
    st_path, hdrs_path, body_path = get("/api/risk/intelligence/../../etc/passwd")
    passed_path = st_path in [404, 400, 422]

    results.append({
        "id": "SEC-005",
        "category": "Input Security",
        "name": "Directory Path Traversal Guard (`../../etc/passwd`)",
        "passed": passed_path,
        "severity": "P0",
        "expected": "HTTP 404/400 Path Traversal Blocked",
        "actual": f"Status: {st_path}",
        "hint": "Ensure route parameters block path traversal sequences."
    })

    # 6. Malformed JSON Body Guard (SEC-006)
    malformed_json_bytes = b'{"query": "test", invalid_json_syntax}'
    st_json, hdrs_json, body_json = post_raw("/api/assistant/query", malformed_json_bytes)
    passed_json = st_json == 422

    results.append({
        "id": "SEC-006",
        "category": "API Validation Security",
        "name": "Malformed JSON Request Body Validation (HTTP 422)",
        "passed": passed_json,
        "severity": "P1",
        "expected": "HTTP 422 Unprocessable Entity for invalid JSON payloads",
        "actual": f"Status: {st_json}",
        "hint": "Verify validation exception handler in backend/app/middleware/error_handler.py"
    })

    return results

if __name__ == "__main__":
    res = run_tests()
    print(json.dumps(res, indent=2))
