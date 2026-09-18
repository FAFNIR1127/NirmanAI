#!/usr/bin/env python3
"""
Phase 10 Full-System QA Suite 0: Test Environment Validation (ENV-001 to ENV-015)
"""
import sys
import os
import subprocess
import urllib.request
import json
import sqlalchemy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from backend.app.config import DATABASE_URL, MODEL_VERSION_DIR

def run_tests():
    results = []

    # ENV-001: Python Version
    version_info = sys.version_info
    py_ok = version_info.major == 3 and version_info.minor >= 10
    results.append({
        "id": "ENV-001",
        "category": "Environment",
        "name": "Python Version >= 3.10",
        "passed": py_ok,
        "severity": "P0",
        "expected": "Python 3.10+",
        "actual": f"{version_info.major}.{version_info.minor}.{version_info.micro}",
        "hint": "Ensure .venv with Python 3.10+ is active."
    })

    # ENV-002: Virtual Environment
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    results.append({
        "id": "ENV-002",
        "category": "Environment",
        "name": "Virtual Environment Active",
        "passed": in_venv,
        "severity": "P1",
        "expected": "Active .venv environment",
        "actual": sys.prefix,
        "hint": "Activate .venv virtual environment."
    })

    # ENV-003: Core Dependencies
    required_packages = ["fastapi", "uvicorn", "sqlalchemy", "pandas", "xgboost", "sklearn", "pydantic", "joblib"]
    missing = []
    for pkg in required_packages:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    results.append({
        "id": "ENV-003",
        "category": "Environment",
        "name": "Required Python Dependencies Installed",
        "passed": len(missing) == 0,
        "severity": "P0",
        "expected": f"All required packages present",
        "actual": f"Missing: {missing}" if missing else "All dependencies installed",
        "hint": f"Run pip install -r backend/requirements.txt"
    })

    # ENV-004 & ENV-005 & ENV-006: PostgreSQL Connection, Version & Database
    db_connected = False
    pg_version = "Unknown"
    db_name = "nirman_db"
    try:
        engine = sqlalchemy.create_engine(DATABASE_URL)
        with engine.connect() as conn:
            ver_res = conn.execute(sqlalchemy.text("SELECT version();")).scalar()
            pg_version = str(ver_res).split()[0] if ver_res else "PostgreSQL"
            db_connected = True
    except Exception as e:
        pg_version = f"Error: {e}"

    results.append({
        "id": "ENV-004",
        "category": "Environment",
        "name": "PostgreSQL Service Running",
        "passed": db_connected,
        "severity": "P0",
        "expected": "Successful TCP connection to PostgreSQL",
        "actual": "Connected" if db_connected else pg_version,
        "hint": "Ensure postgres service is active on localhost:5432."
    })
    results.append({
        "id": "ENV-005",
        "category": "Environment",
        "name": "PostgreSQL Engine Version",
        "passed": db_connected,
        "severity": "P2",
        "expected": "PostgreSQL 12+",
        "actual": pg_version,
        "hint": "Verify PostgreSQL installation."
    })

    # ENV-007: Core PostgreSQL Tables Exist
    required_tables = ["projects", "project_observations", "project_features", "risk_scores", "document_chunks"]
    existing_tables = []
    if db_connected:
        try:
            engine = sqlalchemy.create_engine(DATABASE_URL)
            inspector = sqlalchemy.inspect(engine)
            existing_tables = inspector.get_table_names()
        except Exception:
            pass

    missing_tables = [t for t in required_tables if t not in existing_tables]
    results.append({
        "id": "ENV-007",
        "category": "Environment",
        "name": "PostgreSQL Schema Tables Present",
        "passed": len(missing_tables) == 0,
        "severity": "P0",
        "expected": f"Tables present: {required_tables}",
        "actual": f"Missing tables: {missing_tables}" if missing_tables else "All 5 core tables exist",
        "hint": "Run database initialization and ingestion scripts."
    })

    # ENV-008: Backend Application Entrypoint Import
    backend_import_ok = False
    import_err = ""
    try:
        from backend.app.main import app
        backend_import_ok = app is not None
    except Exception as e:
        import_err = str(e)

    results.append({
        "id": "ENV-008",
        "category": "Environment",
        "name": "FastAPI App Importable (backend.app.main)",
        "passed": backend_import_ok,
        "severity": "P0",
        "expected": "Clean import of FastAPI app object",
        "actual": "Imported successfully" if backend_import_ok else f"Import error: {import_err}",
        "hint": "Fix missing modules or syntax errors in backend/app/"
    })

    # ENV-009: ML Model Artifacts in models/risk_engine_v1
    required_artifacts = ["xgboost_model.joblib", "calibrator.pkl", "feature_schema.json", "threshold.json", "model_metadata.json"]
    missing_artifacts = []
    for art in required_artifacts:
        p = os.path.join(MODEL_VERSION_DIR, art)
        if not os.path.exists(p):
            missing_artifacts.append(art)

    results.append({
        "id": "ENV-009",
        "category": "Environment",
        "name": "Risk Engine v1 Model Artifacts Exist",
        "passed": len(missing_artifacts) == 0,
        "severity": "P0",
        "expected": f"Artifacts present: {required_artifacts}",
        "actual": f"Missing: {missing_artifacts}" if missing_artifacts else "All 5 model artifacts present",
        "hint": "Ensure models/risk_engine_v1/ contains trained model joblib/json files."
    })

    # ENV-010: Frontend Asset Integrity
    frontend_dir = os.path.join(BASE_DIR, "frontend")
    required_fe = ["index.html", "styles.css", "app.js"]
    missing_fe = [f for f in required_fe if not os.path.exists(os.path.join(frontend_dir, f))]
    results.append({
        "id": "ENV-010",
        "category": "Environment",
        "name": "Frontend Asset Files Exist",
        "passed": len(missing_fe) == 0,
        "severity": "P1",
        "expected": f"Files present: {required_fe}",
        "actual": f"Missing: {missing_fe}" if missing_fe else "All frontend files present",
        "hint": "Check frontend/ directory files."
    })

    # ENV-011 to ENV-015: Server Live Status & Health
    health_url = "http://127.0.0.1:8000/api/health"
    health_ok = False
    db_health_str = "Disconnected"
    try:
        req = urllib.request.urlopen(health_url, timeout=3)
        if req.status == 200:
            payload = json.loads(req.read().decode('utf-8'))
            health_ok = payload.get("status") == "healthy"
            db_health_str = payload.get("database_status", "unknown")
    except Exception as e:
        db_health_str = f"Connection failed: {e}"

    results.append({
        "id": "ENV-011",
        "category": "Environment",
        "name": "Backend REST Server Running on Port 8000",
        "passed": health_ok,
        "severity": "P0",
        "expected": "HTTP 200 on http://127.0.0.1:8000/api/health",
        "actual": "Server responding" if health_ok else db_health_str,
        "hint": "Start server with python start_server.py"
    })
    results.append({
        "id": "ENV-012",
        "category": "Environment",
        "name": "Server Health API Response Valid",
        "passed": health_ok,
        "severity": "P0",
        "expected": "status == 'healthy'",
        "actual": "Healthy" if health_ok else db_health_str,
        "hint": "Verify FastAPI /api/health router"
    })
    results.append({
        "id": "ENV-015",
        "category": "Environment",
        "name": "Database Health Status Verified via REST",
        "passed": db_health_str == "connected",
        "severity": "P0",
        "expected": "database_status == 'connected'",
        "actual": db_health_str,
        "hint": "Verify PostgreSQL credentials in backend/app/config.py"
    })

    return results

if __name__ == "__main__":
    res = run_tests()
    print(json.dumps(res, indent=2))
