import enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentCategory


class SearchMode(str, enum.Enum):
    HYBRID = "HYBRID"
    SEMANTIC = "SEMANTIC"
    LEXICAL = "LEXICAL"


class CaseSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="Search query string")
    top_k: int = Field(default=10, ge=1, le=50, description="Maximum number of evidence chunks to return")
    search_mode: SearchMode = Field(default=SearchMode.HYBRID, description="Retrieval strategy: HYBRID, SEMANTIC, or LEXICAL")
    document_category: DocumentCategory | None = Field(default=None, description="Optional filter by document category")
    document_id: UUID | None = Field(default=None, description="Optional filter by specific document ID")
    min_score: float | None = Field(default=None, ge=0.0, le=1.0, description="Minimum relevance score threshold")


class RetrievedEvidence(BaseModel):
    chunk_id: UUID
    document_id: UUID
    case_id: UUID
    document_version: int
    document_category: str
    source_filename: str
    page_start: int
    page_end: int
    content: str
    score: float
    lexical_score: float | None = None
    semantic_score: float | None = None
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class CaseSearchResponse(BaseModel):
    query: str
    search_mode: str
    total_results: int
    results: list[RetrievedEvidence]
