from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class AdvocateVerificationDocumentResponse(BaseModel):
    id: UUID
    verification_id: UUID
    document_type: str
    original_filename: str
    file_size_bytes: int
    mime_type: str
    sha256_hash: str
    scan_status: str
    verification_status: str
    rejection_reason: str | None = None
    created_at: datetime
    uploaded_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AdvocateVerificationDocumentUploadResponse(BaseModel):
    id: UUID
    document_id: UUID
    document_type: str
    original_filename: str
    sha256_hash: str
    scan_status: str
    verification_status: str
    message: str


class AdvocateVerificationSubmitRequest(BaseModel):
    enrollment_number: str = Field(..., min_length=3, max_length=100)
    state_bar_council: str = Field(..., min_length=3, max_length=150)
    declared_practice_jurisdictions: list[str] = Field(default_factory=list)
    is_reverification: bool = False

    model_config = {"extra": "forbid"}


class VerificationReviewEventResponse(BaseModel):
    id: UUID
    reviewer_id: UUID | None = None
    from_status: str | None = None
    to_status: str
    decision: str
    verification_method: str | None = None
    verification_source: str | None = None
    source_reference: str | None = None
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdvocateVerificationDetailResponse(BaseModel):
    id: UUID
    lawyer_profile_id: UUID
    advocate_name: str
    advocate_email: str | None = None
    enrollment_number: str
    state_bar_council: str
    status: str
    declared_practice_jurisdictions: list[str] = Field(default_factory=list)
    verification_source: str | None = None
    source_reference: str | None = None
    verification_method: str | None = None
    verified_at: datetime | None = None
    expires_at: datetime | None = None
    last_reviewed_at: datetime | None = None
    reviewer_id: UUID | None = None
    reviewer_notes: str | None = None
    rejection_reason_category: str | None = None
    documents: list[AdvocateVerificationDocumentResponse] = Field(default_factory=list)
    review_events: list[VerificationReviewEventResponse] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LawyerVerificationQueueItem(BaseModel):
    id: UUID
    lawyer_profile_id: UUID
    advocate_name: str
    enrollment_number: str
    state_bar_council: str
    status: str
    documents_count: int
    missing_documents: list[str] = Field(default_factory=list)
    submitted_at: datetime
    last_reviewed_at: datetime | None = None
    reviewer_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class LawyerVerificationQueueResponse(BaseModel):
    items: list[LawyerVerificationQueueItem]
    total: int
    page: int
    page_size: int


class LawyerVerificationStartReviewRequest(BaseModel):
    notes: str | None = None

    model_config = {"extra": "forbid"}


class LawyerVerificationApproveRequest(BaseModel):
    verification_source: str = Field(..., min_length=3, max_length=255)
    source_reference: str = Field(..., min_length=3, max_length=255)
    verification_method: str = Field("STATE_BAR_COUNCIL_PORTAL_CHECK", max_length=100)
    validity_days: int = Field(365, ge=30, le=1825)
    notes: str | None = None

    model_config = {"extra": "forbid"}


class LawyerVerificationRejectRequest(BaseModel):
    rejection_category: str | None = Field(None, max_length=100)
    rejection_reason_category: str | None = Field(None, max_length=100)
    reason: str | None = Field(None, min_length=5, max_length=500)
    rejection_reason: str | None = Field(None, min_length=5, max_length=500)
    notes: str | None = None

    @model_validator(mode="after")
    def populate_rejection_fields(self) -> "LawyerVerificationRejectRequest":
        cat = self.rejection_category or self.rejection_reason_category
        reas = self.reason or self.rejection_reason
        if not cat:
            raise ValueError("Rejection category must be provided")
        if not reas:
            raise ValueError("Rejection reason must be provided")
        self.rejection_category = cat
        self.reason = reas
        return self

    model_config = {"extra": "forbid"}


class LawyerVerificationRequestInfoRequest(BaseModel):
    requested_documents: list[str] = Field(..., min_length=1)
    explanation: str = Field(..., min_length=5, max_length=1000)
    notes: str | None = None

    model_config = {"extra": "forbid"}


class LawyerVerificationRevokeRequest(BaseModel):
    revocation_reason: str = Field(..., min_length=5, max_length=500)
    notes: str | None = None

    model_config = {"extra": "forbid"}


class PublicAdvocateVerificationBadgeResponse(BaseModel):
    is_verified: bool
    badge_text: str
    verification_badge_text: str
    enrollment_state: str | None = None
    state_bar_council: str | None = None
    enrollment_number: str | None = None
    enrollment_number_masked: str | None = None
    identity_reviewed: bool = False
    verified_on: str | None = None
    verified_at: datetime | None = None
    verification_disclaimer: str
    compliance_declaration: str
    verification_method: str | None = None
    verification_source: str | None = None

    model_config = ConfigDict(from_attributes=True)
