from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.evidence import (
    EvidenceAccessLevel,
    EvidenceCategory,
    EvidenceCustodyAction,
    EvidenceIntegrityStatus,
    EvidenceScanStatus,
    EvidenceSensitivity,
    EvidenceStatus,
)


class EvidenceUploadInitRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    original_filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=3, max_length=100)
    size_bytes: int = Field(..., gt=0)
    category: EvidenceCategory = EvidenceCategory.MISCELLANEOUS
    sensitivity: EvidenceSensitivity = EvidenceSensitivity.STANDARD
    description: str | None = Field(default=None, max_length=1000)
    retention_until: datetime | None = None

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
    access_level: EvidenceAccessLevel
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None

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
    legal_hold: bool = False
    legal_hold_reason: str | None = None
    retention_until: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidenceDetailResponse(EvidenceResponse):
    current_version: EvidenceVersionResponse | None = None
    versions: list[EvidenceVersionResponse] = []
    grants: list[EvidenceAccessGrantResponse] = []

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
