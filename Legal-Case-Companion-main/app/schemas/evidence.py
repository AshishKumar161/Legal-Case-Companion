import enum
import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.evidence import (
    EvidenceAccessLevel,
    EvidenceCategory,
    EvidenceCustodyAction,
    EvidenceIntegrityStatus,
    EvidenceScanStatus,
    EvidenceSensitivity,
    EvidenceStatus,
)


def normalize_tags(raw_tags: list[str] | None) -> list[str]:
    """Normalizes and validates a bounded list of tags:

    - Maximum 20 tags.
    - Each tag trimmed, lowercased, length between 1 and 50 chars.
    - Alphanumeric, hyphens, underscores, and spaces only.
    - Preserves deterministic ordering without duplicates.
    """
    if not raw_tags:
        return []
    if len(raw_tags) > 20:
        raise ValueError("Maximum 20 tags allowed per evidence item")

    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in raw_tags:
        if not isinstance(tag, str):
            continue
        trimmed = tag.strip().lower()
        if not trimmed:
            continue
        if len(trimmed) > 50:
            raise ValueError(f"Tag '{trimmed[:20]}...' exceeds maximum length of 50 characters")
        if not re.match(r"^[\w\s\-]+$", trimmed, re.UNICODE):
            raise ValueError(f"Tag '{trimmed}' contains invalid characters. Use alphanumeric, hyphens, or spaces.")
        if trimmed not in seen:
            seen.add(trimmed)
            cleaned.append(trimmed)
    return cleaned


class EvidenceUploadInitRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    original_filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=3, max_length=100)
    size_bytes: int = Field(..., gt=0)
    category: EvidenceCategory = EvidenceCategory.MISCELLANEOUS
    sensitivity: EvidenceSensitivity = EvidenceSensitivity.STANDARD
    description: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    retention_until: datetime | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str]:
        return normalize_tags(v)

    model_config = ConfigDict(extra="forbid")


class EvidenceUploadInitResponse(BaseModel):
    evidence_id: UUID
    version_id: UUID
    upload_url: str
    storage_key: str
    expires_in: int


class EvidenceCompleteRequest(BaseModel):
    version_id: UUID

    model_config = ConfigDict(extra="forbid")


class EvidenceVersionCreateRequest(BaseModel):
    original_filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=3, max_length=100)
    size_bytes: int = Field(..., gt=0)

    model_config = ConfigDict(extra="forbid")


class EvidenceVersionResponse(BaseModel):
    id: UUID
    evidence_id: UUID
    version_number: int
    uploaded_by_user_id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    scan_status: EvidenceScanStatus
    scan_details: str | None = None
    integrity_status: EvidenceIntegrityStatus
    last_verified_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidenceAccessGrantResponse(BaseModel):
    id: UUID
    evidence_id: UUID
    grantee_user_id: UUID
    granted_by_user_id: UUID
    grantee_name: str | None = None
    grantee_email: str | None = None
    access_level: EvidenceAccessLevel
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ShareableParticipantResponse(BaseModel):
    user_id: UUID
    full_name: str
    email: str
    role: str
    has_access: bool
    current_access_level: EvidenceAccessLevel | None = None
    grant_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class SharedEvidenceItemResponse(BaseModel):
    id: UUID
    case_id: UUID
    case_title: str
    title: str
    description: str | None = None
    category: EvidenceCategory
    original_filename: str
    mime_type: str
    size_bytes: int
    access_level: EvidenceAccessLevel
    granted_by_name: str
    granted_at: datetime
    expires_at: datetime | None = None
    version_number: int
    sha256: str

    model_config = ConfigDict(from_attributes=True)


class EvidenceCustodyEventResponse(BaseModel):
    id: UUID
    evidence_id: UUID
    version_id: UUID | None = None
    actor_user_id: UUID | None = None
    action: EvidenceCustodyAction
    previous_event_id: UUID | None = None
    metadata: dict | None = Field(default=None, validation_alias="event_metadata", serialization_alias="metadata")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CaseExhibitResponse(BaseModel):
    id: UUID
    case_id: UUID
    evidence_id: UUID
    version_id: UUID
    hearing_id: UUID | None = None
    exhibit_number: str
    title: str
    description: str | None = None
    relevant_date: datetime | None = None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    # Informational display fields
    evidence_title: str | None = None
    version_number: int | None = None
    original_filename: str | None = None
    sha256: str | None = None
    hearing_purpose: str | None = None
    court_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CaseExhibitCreateRequest(BaseModel):
    version_id: UUID | None = None
    hearing_id: UUID | None = None
    exhibit_number: str | None = Field(default=None, max_length=50)
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    relevant_date: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class CaseExhibitUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    hearing_id: UUID | None = None
    relevant_date: datetime | None = None
    exhibit_number: str | None = Field(default=None, max_length=50)

    model_config = ConfigDict(extra="forbid")


class EvidenceUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    category: EvidenceCategory | None = None
    sensitivity: EvidenceSensitivity | None = None
    tags: list[str] | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return normalize_tags(v)

    model_config = ConfigDict(extra="forbid")


class EvidenceResponse(BaseModel):
    id: UUID
    case_id: UUID
    created_by_user_id: UUID
    current_version_id: UUID | None = None
    title: str
    description: str | None = None
    category: EvidenceCategory
    status: EvidenceStatus
    sensitivity: EvidenceSensitivity
    original_filename: str
    tags: list[str] = Field(default_factory=list)
    legal_hold: bool = False
    legal_hold_reason: str | None = None
    retention_until: datetime | None = None
    created_at: datetime
    updated_at: datetime
    exhibit_numbers: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class EvidenceDetailResponse(EvidenceResponse):
    current_version: EvidenceVersionResponse | None = None
    versions: list[EvidenceVersionResponse] = []
    grants: list[EvidenceAccessGrantResponse] = []
    exhibits: list[CaseExhibitResponse] = []

    model_config = ConfigDict(from_attributes=True)


class EvidenceShareRequest(BaseModel):
    target_user_id: UUID
    access_level: EvidenceAccessLevel = EvidenceAccessLevel.VIEW
    expires_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class EvidenceRevokeRequest(BaseModel):
    target_user_id: UUID
    reason: str | None = Field(default=None, max_length=255)

    model_config = ConfigDict(extra="forbid")


class EvidenceLegalHoldRequest(BaseModel):
    legal_hold: bool
    reason: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class EvidenceIntegrityVerifyResponse(BaseModel):
    evidence_id: UUID
    version_id: UUID
    sha256_recorded: str
    sha256_computed: str
    integrity_status: EvidenceIntegrityStatus
    verified_at: datetime
    match: bool


class EvidenceSignedUrlResponse(BaseModel):
    url: str
    expires_in: int
    content_type: str
    filename: str


class EvidenceBatchAction(str, enum.Enum):
    ASSIGN_CATEGORY = "ASSIGN_CATEGORY"
    ADD_TAGS = "ADD_TAGS"
    REMOVE_TAGS = "REMOVE_TAGS"
    ARCHIVE = "ARCHIVE"
    RESTORE = "RESTORE"


class EvidenceBatchRequest(BaseModel):
    action: EvidenceBatchAction
    evidence_ids: list[UUID] = Field(..., min_length=1, max_length=50)
    category: EvidenceCategory | None = None
    tags: list[str] | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return normalize_tags(v)

    model_config = ConfigDict(extra="forbid")


class EvidenceBatchResponse(BaseModel):
    affected_count: int
    action: EvidenceBatchAction
    evidence_ids: list[UUID]
    details: str
