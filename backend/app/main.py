from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
import os

from backend.app.core.logging_config import setup_logging, logger
from backend.app.core.db_resilience import check_db_health
from backend.app.middleware.security import SecurityHeadersMiddleware, RateLimitingMiddleware
from backend.app.middleware.error_handler import (
    http_exception_handler, validation_exception_handler, generic_exception_handler
)

from backend.app.routes import health, projects, risk, analytics, documents, assistant, risk_intelligence

# Initialize Structured Logging
setup_logging()

app = FastAPI(
    title="Project Nirman — Risk & Data Intelligence API",
    description="PAIMANA AI Infrastructure Monitoring Platform Data Intelligence & REST API",
    version="1.0.0"
)

# Register Security & Rate Limiting Middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Global Exception Handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Register REST Routers
app.include_router(health.router)
app.include_router(projects.router)
app.include_router(risk.router)
app.include_router(analytics.router)
app.include_router(documents.router)
app.include_router(assistant.router)
app.include_router(risk_intelligence.router)

from backend.app.services.cache_service import cache_service

# Startup Hook: Verify Database Vitality & Initialize Cache
@app.on_event("startup")
def on_startup():
    cache_service.clear()
    db_ok = check_db_health()
    if db_ok:
        logger.info("✅ Database connectivity verified on startup.")
    else:
        logger.warning("⚠️ Database connectivity ping unverified on startup.")


# Serve Frontend Integrated Web Platform Static Files
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
frontend_dist = os.path.join(base_dir, "frontend", "dist")
frontend_dir = os.path.join(base_dir, "frontend")

if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
elif os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)


