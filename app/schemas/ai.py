from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentCategory
from app.schemas.assistant import ClaimSourceType, ClaimSupportStatus, GroundingStatus
from app.schemas.search import SearchMode


class AIResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    jurisdiction: str | None = Field(
        default=None, description="E.g., India, Delhi High Court"
    )
    relevant_date: date | None = Field(
        default=None, description="Temporal constraint for the law"
    )


class Citation(BaseModel):
    chunk_id: UUID
    document_id: UUID
    text_snippet: str
    relevance_score: float | None = None

    model_config = ConfigDict(from_attributes=True)


class AIResearchResponse(BaseModel):
    answer: str
    citations: list[Citation]
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings such as insufficient evidence, OCR issues",
    )


class AIConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class AIConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=50)


class AIConversationResponse(BaseModel):
    id: UUID
    case_id: UUID
    user_id: UUID | None = None
    title: str | None = None
    status: str = "ACTIVE"
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIMessageRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="The legal question or follow-up query")
    include_legal_authority: bool = Field(default=False, description="Whether to retrieve external authoritative Indian statutes/precedents")
    jurisdiction: str | None = Field(default=None, description="Optional jurisdiction filter for legal authorities")
    temporal_date: date | None = Field(default=None, description="Optional temporal cutoff date for historical legal validity")
    document_category: DocumentCategory | None = Field(default=None, description="Optional document category filter")
    document_id: UUID | None = Field(default=None, description="Optional single document filter")
    top_k: int = Field(default=5, ge=1, le=20)
    search_mode: SearchMode = Field(default=SearchMode.HYBRID)
    idempotency_key: str | None = Field(default=None, max_length=100)


class AIMessageCitation(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_version: int = 1
    source_filename: str = ""
    page_start: int | None = None
    page_end: int | None = None
    text_snippet: str
    relevance_score: float | None = None

    model_config = ConfigDict(from_attributes=True)


class AIMessageAuthorityCitation(BaseModel):
    canonical_identifier: str
    canonical_provision_id: str
    act_or_judgment_name: str
    section_or_para: str
    source_type: str
    authority_level: int
    jurisdiction: str
    effective_from: date | None = None
    effective_to: date | None = None
    text_snippet: str
    relevance_score: float | None = None

    model_config = ConfigDict(from_attributes=True)


class AIMessageClaim(BaseModel):
    claim_text: str
    status: ClaimSupportStatus = ClaimSupportStatus.SUPPORTED
    source_type: ClaimSourceType = ClaimSourceType.CASE_EVIDENCE
    supporting_chunk_ids: list[UUID] = Field(default_factory=list)
    supporting_authority_ids: list[str] = Field(default_factory=list)
    explanation: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AIMessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    grounding_status: GroundingStatus | str | None = None
    citations: list[AIMessageCitation] | None = None
    authority_citations: list[AIMessageAuthorityCitation] | None = None
    claims: list[AIMessageClaim] | None = None
    uncertainties: list[str] | None = None
    warnings: list[str] | None = None
    model_version: str | None = None
    latency_ms: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
