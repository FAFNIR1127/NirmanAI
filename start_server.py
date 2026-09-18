#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import urllib.request

def main():
    print("=======================================================")
    print("       STARTING NIRMAN AI WEB PLATFORM SERVER          ")
    print("=======================================================")

    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    python_venv = os.path.join(project_root, ".venv", "bin", "python")
    if not os.path.exists(python_venv):
        python_venv = sys.executable

    print(f"Using Python runtime: {python_venv}")
    print("Starting FastAPI Uvicorn Server on http://0.0.0.0:8000 ...")

    # Launch uvicorn process
    cmd = [python_venv, "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    proc = subprocess.Popen(cmd, cwd=project_root)

    # Wait for server readiness
    health_url = "http://127.0.0.1:8000/api/health"
    ready = False
    for i in range(15):
        time.sleep(1)
        try:
            req = urllib.request.urlopen(health_url, timeout=2)
            if req.status == 200:
                ready = True
                break
        except Exception:
            pass

    if ready:
        print("\n✅ NIRMAN AI SERVER IS LIVE & READY!")
        print("   👉 Open in browser: http://localhost:8000/")
        print("   👉 REST API Docs:   http://localhost:8000/docs\n")
    else:
        print("\n⚠️ Server started, but health check is still initializing...")

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\nStopping server...")
        proc.terminate()

if __name__ == "__main__":
    main()
