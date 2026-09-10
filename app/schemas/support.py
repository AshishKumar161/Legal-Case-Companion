import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.support import SupportCaseSeverity, SupportCaseStatus


class SupportCaseCreateRequest(BaseModel):
    category: str = Field(..., min_length=2, max_length=50)
    workflow: str = Field(default="GENERAL", min_length=2, max_length=100)
    subject: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    severity: SupportCaseSeverity = SupportCaseSeverity.SEV3_MEDIUM
    metadata_: dict | None = None


class SupportCaseResolveRequest(BaseModel):
    resolution_code: str = Field(..., min_length=2, max_length=100)
    resolution_notes: str = Field(..., min_length=3)


class SupportCaseEscalateRequest(BaseModel):
    target_level: int = Field(..., ge=2, le=3)
    notes: str | None = None


class SupportCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    support_case_id: str
    user_id: uuid.UUID | None
    category: str
    severity: SupportCaseSeverity
    user_scope: str
    workflow: str
    subject: str
    description: str
    opened_at: datetime
    first_response_at: datetime | None
    resolved_at: datetime | None
    status: SupportCaseStatus
    resolution_code: str | None
    resolution_notes: str | None
    escalation_level: int
    linked_incident_id: uuid.UUID | None
    linked_release_id: str | None
