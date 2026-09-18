"""
backend/app/services/conversation_context.py

Phase 13 — Multi-Turn Conversation & Active Context Tracker.
Tracks active project references, active result sets (R1), regional/sector filters,
and conversation history across turns per session_id.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

_SESSIONS: Dict[str, "SessionContext"] = {}


class SessionContext(BaseModel):
    session_id: str
    last_project_code: Optional[str] = None
    active_result_set: List[str] = Field(default_factory=list)  # R1 active result set
    active_state: Optional[str] = None
    active_sector: Optional[str] = None
    active_agency: Optional[str] = None
    last_query: Optional[str] = None
    history: List[Dict[str, str]] = Field(default_factory=list)

    def update_with_query(self, query: str, project_code: Optional[str] = None, result_set: Optional[List[str]] = None, state: Optional[str] = None):
        self.last_query = query
        if project_code:
            self.last_project_code = project_code
        if result_set is not None:
            self.active_result_set = result_set
        if state:
            self.active_state = state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "last_project_code": self.last_project_code,
            "last_result_set_count": len(self.active_result_set),
            "active_result_set": self.active_result_set[:10],
            "active_state": self.active_state,
            "active_sector": self.active_sector,
            "active_agency": self.active_agency,
            "last_query": self.last_query,
            "history_length": len(self.history)
        }


class ConversationContextManager:
    """In-memory session context tracker for multi-turn state persistence."""

    @staticmethod
    def get_session(session_id: str = "default_session") -> SessionContext:
        if session_id not in _SESSIONS:
            _SESSIONS[session_id] = SessionContext(session_id=session_id)
        return _SESSIONS[session_id]

    @staticmethod
    def update_session(session_id: str, **kwargs) -> SessionContext:
        session = ConversationContextManager.get_session(session_id)
        for k, v in kwargs.items():
            if hasattr(session, k) and v is not None:
                setattr(session, k, v)
        return session
