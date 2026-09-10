import enum
from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentCategory
from app.schemas.search import SearchMode


class GroundingStatus(str, enum.Enum):
    SUPPORTED = "SUPPORTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    UNSUPPORTED = "UNSUPPORTED"


class ClaimSupportStatus(str, enum.Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNCERTAIN = "UNCERTAIN"


class ClaimSourceType(str, enum.Enum):
    CASE_EVIDENCE = "CASE_EVIDENCE"
    LEGAL_AUTHORITY = "LEGAL_AUTHORITY"
    SYNTHESIS = "SYNTHESIS"
    UNSUPPORTED = "UNSUPPORTED"


class VerifiedCitation(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_version: int = 1
    source_filename: str
    page_start: int | None = None
    page_end: int | None = None
    text_snippet: str
    relevance_score: float | None = None

    model_config = ConfigDict(from_attributes=True)


class VerifiedAuthorityCitation(BaseModel):
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


class VerifiedClaim(BaseModel):
    claim_text: str
    status: ClaimSupportStatus = ClaimSupportStatus.SUPPORTED
    source_type: ClaimSourceType = ClaimSourceType.CASE_EVIDENCE
    supporting_chunk_ids: list[UUID] = Field(default_factory=list)
    supporting_authority_ids: list[str] = Field(default_factory=list)
    explanation: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CaseAssistantQueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000, description="The legal question to answer against case materials")
    top_k: int = Field(default=8, ge=1, le=20, description="Maximum number of evidence chunks to retrieve")
    search_mode: SearchMode = Field(default=SearchMode.HYBRID, description="Retrieval mode: HYBRID, SEMANTIC, or LEXICAL")
    document_category: DocumentCategory | None = Field(default=None, description="Optional document category filter")
    document_id: UUID | None = Field(default=None, description="Optional single document filter")
    include_legal_authority: bool = Field(default=False, description="Whether to also retrieve authoritative statutes and binding judicial precedents")
    jurisdiction: str | None = Field(default=None, description="Optional jurisdiction constraint for legal authority search")
    temporal_date: date | None = Field(default=None, description="Optional temporal cutoff date to query law as it stood at that point in time")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0, description="LLM sampling temperature")
    verify_claims: bool = Field(default=True, description="Whether to execute post-generation factual claim verification")


class CaseAssistantQueryResponse(BaseModel):
    question: str
    answer: str
    grounding_status: GroundingStatus
    citations: list[VerifiedCitation] = Field(default_factory=list)
    authority_citations: list[VerifiedAuthorityCitation] = Field(default_factory=list)
    claims: list[VerifiedClaim] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = Field(
        default="This AI analysis is generated from authorized case materials and authoritative legal sources, intended for legal assistance, not as a replacement for legal counsel."
    )
    model: str
    latency_ms: float

    model_config = ConfigDict(from_attributes=True)
