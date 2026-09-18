from typing import Optional, List
from pydantic import BaseModel, Field


class DocumentChunkResponse(BaseModel):
    chunk_id: str
    content: str
    source_file: str
    relative_path: Optional[str] = None
    page_number: int
    reporting_month: str
    reporting_year: Optional[str] = None
    project_code: Optional[str] = None
    document_type: str
    similarity_score: float = 0.0
    lexical_score: float = 0.0
    combined_score: float = 0.0
    citation: str
    metadata: Optional[dict] = None


class SearchRequest(BaseModel):
    query: str
    project_code: Optional[str] = None
    reporting_month: Optional[str] = None
    document_type: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=50)


class SearchResponse(BaseModel):
    query: str
    total_matches: int
    retrieved_chunks: List[DocumentChunkResponse]
    retrieval_method: str = "hybrid_rrf"
