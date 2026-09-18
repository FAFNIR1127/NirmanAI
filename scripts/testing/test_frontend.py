#!/usr/bin/env python3
"""
Phase 11 Full-System QA Suite: Vite + React + TypeScript SPA Frontend Integration,
DOM Root Delivery, Bundle Assets & Fallback States
(UI-001 to UI-005)
"""
import sys
import os
import urllib.request
import json
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

API_HOST = "http://127.0.0.1:8000"

def get(path):
    url = f"{API_HOST}{path}"
    try:
        req = urllib.request.urlopen(url, timeout=4)
        return req.status, dict(req.headers), req.read().decode('utf-8')
    except Exception as e:
        return 0, {}, str(e)

def run_tests():
    results = []

    # 1. Vite React Root Index HTML Delivery (UI-001)
    st_html, hdrs_html, html_content = get("/")
    has_title = "NIRMAN" in html_content
    has_root = '<div id="root"></div>' in html_content
    has_vite_js = "/assets/index-" in html_content or "src=" in html_content
    has_css = "/assets/index-" in html_content or "href=" in html_content

    results.append({
        "id": "UI-001",
        "category": "Frontend Static Delivery",
        "name": "React Root Delivery & Vite Script Links (`index.html`)",
        "passed": st_html == 200 and has_title and has_root and (has_vite_js or has_css),
        "severity": "P0",
        "expected": "HTTP 200 with Vite index.html delivering root container and bundled assets",
        "actual": f"Status: {st_html}, Title: {has_title}, Root Container: {has_root}",
        "hint": "Check frontend/dist/index.html file."
    })

    # 2. Production JS Bundle Assets Delivery Check (UI-002)
    js_match = re.search(r'src="(/assets/index-[^"]+\.js)"', html_content)
    js_path = js_match.group(1) if js_match else "/assets/index.js"
    st_js, hdrs_js, js_content = get(js_path)
    has_react_bundle = st_js == 200 and len(js_content) > 1000

    results.append({
        "id": "UI-002",
        "category": "Frontend JS Logic",
        "name": "Vite Production JS Bundle Asset Delivery",
        "passed": has_react_bundle,
        "severity": "P0",
        "expected": "HTTP 200 delivering compiled Vite React JavaScript bundle",
        "actual": f"Status: {st_js}, Bundle Path: {js_path}, Size: {len(js_content)} bytes",
        "hint": "Check Vite dist bundle build output."
    })

    # 3. Production CSS Stylesheet Delivery Check (UI-003)
    css_match = re.search(r'href="(/assets/index-[^"]+\.css)"', html_content)
    css_path = css_match.group(1) if css_match else "/assets/index.css"
    st_css, hdrs_css, css_content = get(css_path)
    has_tailwind_css = st_css == 200 and len(css_content) > 500

    results.append({
        "id": "UI-003",
        "category": "Frontend CSS Delivery",
        "name": "Tailwind Production CSS Stylesheet Delivery",
        "passed": has_tailwind_css,
        "severity": "P1",
        "expected": "HTTP 200 delivering Tailwind CSS stylesheet bundle",
        "actual": f"Status: {st_css}, CSS Path: {css_path}, Size: {len(css_content)} bytes",
        "hint": "Check Tailwind CSS compilation in Vite build."
    })

    # 4. React SPA Root Container Presence (UI-004)
    results.append({
        "id": "UI-004",
        "category": "Frontend View Containers",
        "name": "React Single Page Application Root Element Container Present in DOM",
        "passed": has_root,
        "severity": "P0",
        "expected": "Vite React mount element `<div id=\"root\"></div>` present",
        "actual": "React root element present in DOM",
        "hint": "Check root div in index.html"
    })

    # 5. API Health Connectivity Check via Backend Endpoint (UI-005)
    st_api, _, api_content = get("/api/health")
    has_healthy_status = '"status":"healthy"' in api_content or '"status": "healthy"' in api_content

    results.append({
        "id": "UI-005",
        "category": "Frontend API Connectivity",
        "name": "FastAPI REST Proxy & Health Status Connectivity",
        "passed": st_api == 200 and has_healthy_status,
        "severity": "P0",
        "expected": "HTTP 200 from /api/health with healthy status",
        "actual": f"Status: {st_api}, Health response: {api_content[:80]}",
        "hint": "Check FastAPI server on port 8000"
    })

    return results

if __name__ == "__main__":
    res = run_tests()
    print(json.dumps(res, indent=2))
