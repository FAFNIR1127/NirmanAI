from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None


class CitationItem(BaseModel):
    citation_id: str  # "E1", "E2"
    title: str
    source_file: Optional[str] = None
    page_number: Optional[int] = None
    reporting_month: Optional[str] = None
    reporting_year: Optional[str] = None
    project_code: Optional[str] = None
    document_type: Optional[str] = None
    snippet: Optional[str] = None


class EvidencePackageSchema(BaseModel):
    query: str
    intent: str
    entities: Dict[str, Any] = Field(default_factory=dict)
    structured_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    risk_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    document_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[CitationItem] = Field(default_factory=list)
    evidence_sufficiency: str = "HIGH"  # HIGH, MEDIUM, LOW, NONE


class NumberCallout(BaseModel):
    label: str
    value: str
    unit: Optional[str] = None
    status: Optional[str] = None  # critical, warning, normal, info


class DriverCallout(BaseModel):
    label: str
    impact: Optional[str] = None  # e.g., "+0.34 risk score", "High Expenditure Gap"
    detail: Optional[str] = None


class CopilotResponse(BaseModel):
    direct_answer: str
    key_findings: List[str] = Field(default_factory=list)
    important_numbers: List[NumberCallout] = Field(default_factory=list)
    risk_and_drivers: List[DriverCallout] = Field(default_factory=list)
    evidence_citations: List[CitationItem] = Field(default_factory=list)
    next_actions: List[str] = Field(default_factory=list)

    # Metadata & compatibility
    answer: str = ""
    response: Optional[str] = None
    intent: str = "DYNAMIC_CAPABILITY_INTELLIGENCE"
    response_mode: str = "executive_analysis"
    entities: Dict[str, Any] = Field(default_factory=dict)
    tools_used: List[str] = Field(default_factory=list)
    citations: List[CitationItem] = Field(default_factory=list)
    evidence_sufficiency: str = "HIGH"
    is_verified: bool = True
    verification_notes: List[str] = Field(default_factory=list)
    model_version: str = "nirman_copilot_v2"
    session_id: str = "default_session"


class AssistantChatRequest(BaseModel):
    message: Optional[str] = None
    query: Optional[str] = None
    session_id: Optional[str] = None


class AssistantChatResponse(CopilotResponse):
    pass
