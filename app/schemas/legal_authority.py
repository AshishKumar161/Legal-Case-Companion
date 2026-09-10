from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.legal_authority import (
    AuthorityLevel,
    LegalAuthorityType,
    LegalJurisdiction,
    LegalSourceStatus,
)
from app.schemas.search import SearchMode


class LegalAuthorityProvisionCreate(BaseModel):
    canonical_provision_id: str = Field(..., description="Unique deterministic provision ID, e.g. IN-ACT-1881-26-SEC-138-V2018")
    section_number: str = Field(..., description="Section, Rule, Article, or Para identifier")
    version_label: str = Field(default="Current", description="Version description, e.g. 2018 Amendment, Original 1881")
    chapter_number: str | None = None
    title: str = Field(..., description="Heading or title of the provision/judgment holding")
    content: str = Field(..., min_length=5, description="Full authoritative provision or judgment excerpt text")
    effective_from: date | None = None
    effective_to: date | None = None
    is_current: bool = True
    metadata_: dict | None = Field(default=None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


LegalAuthorityIngestProvision = LegalAuthorityProvisionCreate


class LegalAuthorityIngestRequest(BaseModel):
    canonical_identifier: str = Field(..., description="Unique canonical source ID, e.g. IN-ACT-1881-26, IN-SC-2021-5-SCC-120")
    name: str = Field(..., min_length=2, max_length=255, description="Full formal name of Act or Case")
    short_title: str | None = Field(default=None, max_length=100)
    year: int = Field(..., ge=1800, le=2100)
    source_type: LegalAuthorityType = LegalAuthorityType.PRIMARY_LEGISLATION
    authority_level: int = AuthorityLevel.PRIMARY_STATUTE.value
    jurisdiction: str = LegalJurisdiction.INDIA_CENTRAL.value
    issuing_body: str | None = None
    publication_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    status: LegalSourceStatus = LegalSourceStatus.PUBLISHED
    citation_standard: str | None = None
    canonical_url: str | None = None
    metadata_: dict | None = Field(default=None, alias="metadata")
    provisions: list[LegalAuthorityProvisionCreate] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class LegalAuthorityProvisionResponse(BaseModel):
    id: UUID
    source_id: UUID
    canonical_provision_id: str
    section_number: str
    version_label: str
    chapter_number: str | None = None
    title: str
    content: str
    effective_from: date | None = None
    effective_to: date | None = None
    is_current: bool
    metadata_: dict | None = Field(default=None, validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LegalAuthorityResponse(BaseModel):
    id: UUID
    canonical_identifier: str
    name: str
    short_title: str | None = None
    year: int
    source_type: LegalAuthorityType
    authority_level: int
    jurisdiction: str
    issuing_body: str | None = None
    publication_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    status: LegalSourceStatus
    citation_standard: str | None = None
    canonical_url: str | None = None
    is_active: bool
    metadata_: dict | None = Field(default=None, validation_alias="metadata_")
    provisions: list[LegalAuthorityProvisionResponse] = Field(
        default_factory=list, validation_alias="versions"
    )
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RetrievedLegalAuthority(BaseModel):
    source_id: UUID
    version_id: UUID
    canonical_identifier: str
    canonical_provision_id: str
    name: str
    short_title: str | None = None
    section_number: str
    version_label: str
    title: str
    content: str
    source_type: LegalAuthorityType
    authority_level: int
    jurisdiction: str
    citation_standard: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    is_current: bool
    score: float
    lexical_score: float | None = None
    semantic_score: float | None = None
    metadata_: dict | None = Field(default=None, validation_alias="metadata_")

    model_config = ConfigDict(from_attributes=True)


class LegalAuthoritySearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    search_mode: SearchMode = SearchMode.HYBRID
    jurisdiction: str | None = None
    source_type: LegalAuthorityType | None = None
    effective_at: date | None = Field(default=None, description="Optional temporal cutoff date to query law as it stood at that point in time")
    min_authority_level: int | None = None
    min_score: float | None = Field(default=0.05, ge=0.0, le=1.0)


class LegalAuthoritySearchResponse(BaseModel):
    query: str
    search_mode: str
    total_results: int
    results: list[RetrievedLegalAuthority]

    model_config = ConfigDict(from_attributes=True)
