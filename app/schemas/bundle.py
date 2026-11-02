import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.bundle import BundleStatus


class BundleItemCreate(BaseModel):
    evidence_id: uuid.UUID
    version_id: uuid.UUID | None = None
    exhibit_id: uuid.UUID | None = None
    custom_title: str | None = Field(None, max_length=255)
    order_index: int | None = Field(None, ge=0)

    model_config = ConfigDict(extra="forbid")


class BundleCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    hearing_id: uuid.UUID | None = None
    bates_prefix: str = Field("LCC", min_length=1, max_length=20)
    bates_start: int = Field(1, ge=1)
    items: list[BundleItemCreate] = Field(default_factory=list, max_length=100)

    model_config = ConfigDict(extra="forbid")


class BundleUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = None
    hearing_id: uuid.UUID | None = None
    bates_prefix: str | None = Field(None, min_length=1, max_length=20)
    bates_start: int | None = Field(None, ge=1)
    items: list[BundleItemCreate] | None = Field(None, max_length=100)

    model_config = ConfigDict(extra="forbid")


class BundleItemResponse(BaseModel):
    id: uuid.UUID
    bundle_id: uuid.UUID
    evidence_id: uuid.UUID
    version_id: uuid.UUID
    exhibit_id: uuid.UUID | None = None
    order_index: int
    exhibit_number: str | None = None
    custom_title: str | None = None
    bates_start_page: int | None = None
    bates_end_page: int | None = None
    sha256_hash: str
    file_size: int
    mime_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BundleResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    hearing_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    status: BundleStatus
    bates_prefix: str
    bates_start: int
    bates_end: int | None = None
    total_pages: int | None = None
    total_items: int
    sha256_hash: str | None = None
    file_size: int | None = None
    created_by_user_id: uuid.UUID
    finalized_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BundleDetailResponse(BundleResponse):
    items: list[BundleItemResponse] = Field(default_factory=list)
    manifest_json: dict | None = None


class BSACertificateCreateRequest(BaseModel):
    record_identification: str = Field(..., min_length=2, max_length=500)
    source_device_type: str = Field(..., min_length=2, max_length=255)
    source_device_details: str | None = None
    lawful_control_statement: str = Field(..., min_length=10)
    operational_condition_statement: str = Field(..., min_length=10)
    declarant_name: str = Field(..., min_length=2, max_length=255)
    declarant_designation: str = Field(..., min_length=2, max_length=255)
    declarant_organization: str | None = Field(None, max_length=255)
    place: str = Field(..., min_length=2, max_length=255)
    declaration_date: datetime
    is_confirmed: bool = Field(..., description="Explicit human confirmation of statutory facts")
    expert_examiner_name: str | None = Field(None, max_length=255, description="Name of expert under BSA Section 63(4) Schedule Part B")
    expert_examiner_designation: str | None = Field(None, max_length=255, description="Designation of expert examiner under BSA Section 63(4) Schedule Part B")
    expert_examination_details: str | None = Field(None, description="Summary of expert examination under BSA Section 63(4) Schedule Part B")

    model_config = ConfigDict(extra="forbid")


class BSACertificateResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    bundle_id: uuid.UUID | None = None
    evidence_id: uuid.UUID | None = None
    version_id: uuid.UUID | None = None
    record_identification: str
    source_device_type: str
    source_device_details: str | None = None
    lawful_control_statement: str
    operational_condition_statement: str
    hash_value: str
    hash_algorithm: str
    declarant_name: str
    declarant_designation: str
    declarant_organization: str | None = None
    place: str
    declaration_date: datetime
    is_confirmed: bool
    status: str
    storage_key: str | None = None
    expert_examiner_name: str | None = None
    expert_examiner_designation: str | None = None
    legal_counsel_advisory: str = "Statutory admissibility under BSA Section 63 must be evaluated by qualified Indian legal counsel."
    created_by_user_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
