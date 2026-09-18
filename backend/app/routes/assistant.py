from fastapi import APIRouter, HTTPException
from backend.app.schemas.assistant import AssistantChatRequest, CopilotResponse
from backend.app.services.assistant_service import AssistantService
from backend.app.services.capability_registry import CapabilityRegistry
from backend.app.services.insight_service import InsightService

router = APIRouter(prefix="/api/assistant", tags=["Nirman AI Assistant"])
assistant_service = AssistantService()


@router.post("/chat", response_model=CopilotResponse)
@router.post("/query", response_model=CopilotResponse)
def chat_with_assistant(req: AssistantChatRequest):
    """Conversational REST endpoint for Nirman AI Copilot v2 with dynamic capability planning and evidence verification."""
    msg = req.message or req.query or ""
    if not msg.strip():
        raise HTTPException(status_code=400, detail="Chat message cannot be empty.")

    try:
        res = assistant_service.chat(message=msg, session_id=req.session_id)
        res.response = res.answer
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assistant chat error: {str(e)}")


@router.get("/capabilities")
def list_capabilities():
    """Retrieve machine-readable list of registered capabilities exposed to Copilot Query Planner."""
    return CapabilityRegistry.list_capabilities()


@router.get("/surveillance")
def get_surveillance_snapshot():
    """Retrieve proactive morning surveillance snapshot across portfolio."""
    try:
        return InsightService.get_morning_surveillance()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Surveillance retrieval error: {str(e)}")


@router.get("/history/{session_id}")
def get_chat_history(session_id: str):
    """Retrieve chat session history and active entity memory."""
    history = assistant_service.get_session_history(session_id=session_id)
    if not history:
        raise HTTPException(status_code=404, detail=f"Session ID '{session_id}' not found.")
    return history


@router.delete("/history/{session_id}")
def clear_chat_history(session_id: str):
    """Clear chat session state."""
    success = assistant_service.clear_session_history(session_id=session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Session ID '{session_id}' not found.")
    return {"message": f"Session '{session_id}' cleared successfully."}
