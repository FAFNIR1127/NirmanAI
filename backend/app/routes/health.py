from fastapi import APIRouter
from backend.app.services.risk_engine import risk_engine_service

router = APIRouter()


@router.get("/health")
@router.get("/api/health")
def health_check():

    return {
        "status": "healthy",
        "service": "Nirman Risk Intelligence Engine",
        "model_version": risk_engine_service.metadata.get("model_version", "risk_engine_v1"),
        "operational_threshold": risk_engine_service.operational_threshold,
        "database_status": "connected"
    }
