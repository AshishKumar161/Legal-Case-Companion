import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.case_intelligence import (
    ClaimDefenseStatus,
    ClaimPositionType,
    DatePrecision,
    EvidenceGapStatus,
    EvidenceGapType,
    FactSourceType,
    FactVerificationStatus,
    IssueStatus,
    RiskSeverity,
)


class CaseFactBase(BaseModel):
    fact_text: str = Field(..., min_length=3, max_length=5000)
    category: str = Field(default="GENERAL", max_length=100)
    verification_status: FactVerificationStatus = FactVerificationStatus.AI_SUGGESTED
    source_type: FactSourceType = FactSourceType.CASE_EVIDENCE
    source_chunk_id: UUID | None = None
    source_document_id: UUID | None = None
    source_filename: str | None = None
    source_authority_id: str | None = None
    source_message_id: UUID | None = None
    document_version: int | None = None
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class CaseFactCreate(BaseModel):
    fact_text: str = Field(..., min_length=3, max_length=5000)
    category: str = Field(default="USER_REPORTED", max_length=100)
    source_type: FactSourceType = FactSourceType.USER_REPORTED


class CaseFactUpdate(BaseModel):
    fact_text: str | None = None
    category: str | None = None
    verification_status: FactVerificationStatus | None = None


class CaseFactResponse(CaseFactBase):
    id: UUID
    case_id: UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class LegalIssueBase(BaseModel):
    issue_text: str = Field(..., min_length=3, max_length=5000)
    category: str = Field(default="GENERAL", max_length=100)
    status: IssueStatus = IssueStatus.IDENTIFIED
    verification_status: FactVerificationStatus = FactVerificationStatus.AI_SUGGESTED
    supporting_fact_ids: list[UUID] = Field(default_factory=list)
    relevant_authority_ids: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class LegalIssueCreate(BaseModel):
    issue_text: str = Field(..., min_length=3, max_length=5000)
    category: str = Field(default="GENERAL", max_length=100)
    supporting_fact_ids: list[UUID] = Field(default_factory=list)
    relevant_authority_ids: list[str] = Field(default_factory=list)


class LegalIssueUpdate(BaseModel):
    issue_text: str | None = None
    category: str | None = None
    status: IssueStatus | None = None
    verification_status: FactVerificationStatus | None = None
    supporting_fact_ids: list[UUID] | None = None
    relevant_authority_ids: list[str] | None = None


class LegalIssueResponse(LegalIssueBase):
    id: UUID
    case_id: UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class CaseClaimDefenseBase(BaseModel):
    position_type: ClaimPositionType = ClaimPositionType.CLAIM
    party_role: str = Field(default="CLIENT", max_length=100)
    statement: str = Field(..., min_length=3, max_length=5000)
    status: ClaimDefenseStatus = ClaimDefenseStatus.ASSERTED
    verification_status: FactVerificationStatus = FactVerificationStatus.AI_SUGGESTED
    supporting_chunk_ids: list[UUID] = Field(default_factory=list)
    opposing_chunk_ids: list[UUID] = Field(default_factory=list)
    relevant_authority_ids: list[str] = Field(default_factory=list)


class CaseClaimDefenseCreate(BaseModel):
    position_type: ClaimPositionType = ClaimPositionType.CLAIM
    party_role: str = Field(default="CLIENT", max_length=100)
    statement: str = Field(..., min_length=3, max_length=5000)


class CaseClaimDefenseUpdate(BaseModel):
    statement: str | None = None
    status: ClaimDefenseStatus | None = None
    verification_status: FactVerificationStatus | None = None


class CaseClaimDefenseResponse(CaseClaimDefenseBase):
    id: UUID
    case_id: UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class CaseChronologyEventBase(BaseModel):
    event_date: datetime.date | None = None
    date_text: str | None = None
    date_precision: DatePrecision = DatePrecision.EXACT_DATE
    event_type: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., min_length=3, max_length=5000)
    is_conflicting: bool = False
    conflicting_source_details: list[dict] | None = None
    source_chunk_id: UUID | None = None
    source_document_id: UUID | None = None
    source_filename: str | None = None
    verification_status: FactVerificationStatus = FactVerificationStatus.AI_SUGGESTED


class CaseChronologyEventCreate(BaseModel):
    event_date: datetime.date | None = None
    date_text: str | None = None
    date_precision: DatePrecision = DatePrecision.EXACT_DATE
    event_type: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., min_length=3, max_length=5000)


class CaseChronologyEventUpdate(BaseModel):
    event_date: datetime.date | None = None
    date_text: str | None = None
    date_precision: DatePrecision | None = None
    event_type: str | None = None
    description: str | None = None
    verification_status: FactVerificationStatus | None = None


class CaseChronologyEventResponse(CaseChronologyEventBase):
    id: UUID
    case_id: UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class CaseEvidenceGapBase(BaseModel):
    description: str = Field(..., min_length=3, max_length=5000)
    gap_type: EvidenceGapType = EvidenceGapType.MISSING_DOCUMENT
    severity: RiskSeverity = RiskSeverity.MEDIUM
    status: EvidenceGapStatus = EvidenceGapStatus.NOT_FOUND_IN_AVAILABLE_MATERIALS
    related_issue_id: UUID | None = None
    related_claim_id: UUID | None = None


class CaseEvidenceGapCreate(BaseModel):
    description: str = Field(..., min_length=3, max_length=5000)
    gap_type: EvidenceGapType = EvidenceGapType.MISSING_DOCUMENT
    severity: RiskSeverity = RiskSeverity.MEDIUM


class CaseEvidenceGapUpdate(BaseModel):
    description: str | None = None
    severity: RiskSeverity | None = None
    status: EvidenceGapStatus | None = None


class CaseEvidenceGapResponse(CaseEvidenceGapBase):
    id: UUID
    case_id: UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class CaseRiskIndicatorBase(BaseModel):
    risk_title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=3, max_length=5000)
    severity: RiskSeverity = RiskSeverity.MEDIUM
    mitigation_hint: str | None = None
    evidence_sources: list[dict] = Field(default_factory=list)
    verification_status: FactVerificationStatus = FactVerificationStatus.AI_SUGGESTED


class CaseRiskIndicatorCreate(BaseModel):
    risk_title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=3, max_length=5000)
    severity: RiskSeverity = RiskSeverity.MEDIUM
    mitigation_hint: str | None = None


class CaseRiskIndicatorUpdate(BaseModel):
    risk_title: str | None = None
    description: str | None = None
    severity: RiskSeverity | None = None
    mitigation_hint: str | None = None
    verification_status: FactVerificationStatus | None = None


class CaseRiskIndicatorResponse(CaseRiskIndicatorBase):
    id: UUID
    case_id: UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class CaseIntelligenceSummary(BaseModel):
    total_facts: int = 0
    verified_facts: int = 0
    user_reported_facts: int = 0
    open_issues: int = 0
    timeline_events: int = 0
    conflicting_timeline_events: int = 0
    active_claims: int = 0
    evidence_gaps: int = 0
    high_risks: int = 0
    critical_risks: int = 0


class CaseIntelligenceResponse(BaseModel):
    case_id: UUID
    facts: list[CaseFactResponse] = Field(default_factory=list)
    issues: list[LegalIssueResponse] = Field(default_factory=list)
    claims_defenses: list[CaseClaimDefenseResponse] = Field(default_factory=list)
    timeline: list[CaseChronologyEventResponse] = Field(default_factory=list)
    evidence_gaps: list[CaseEvidenceGapResponse] = Field(default_factory=list)
    risks: list[CaseRiskIndicatorResponse] = Field(default_factory=list)
    summary: CaseIntelligenceSummary = Field(default_factory=CaseIntelligenceSummary)
    last_refreshed_at: datetime.datetime | None = None


class RefreshIntelligenceRequest(BaseModel):
    force: bool = Field(default=False, description="Force re-extraction of all evidence")
    include_conversations: bool = Field(default=True, description="Scan verified conversation findings")
    include_statutory_analysis: bool = Field(default=True, description="Match relevant Indian statutory provisions")
