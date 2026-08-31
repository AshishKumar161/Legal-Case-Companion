from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.case_collaboration import (
    CaseMessageType,
    MatterRequestStatus,
    MatterRequestType,
)


# ---------------------------------------------------------------------------
# CASE MESSAGES / FORMAL INBOX
# ---------------------------------------------------------------------------


class CaseMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    message_type: CaseMessageType = CaseMessageType.GENERAL
    linked_document_id: UUID | None = None
    linked_task_id: UUID | None = None
    is_counsel_only: bool = False

    model_config = ConfigDict(extra="forbid")


class CaseMessageSender(BaseModel):
    id: UUID
    email: str
    full_name: str | None = None
    role: str

    model_config = ConfigDict(from_attributes=True)


class CaseMessageResponse(BaseModel):
    id: UUID
    case_id: UUID
    sender_id: UUID
    sender_name: str
    sender_role: str
    content: str
    message_type: CaseMessageType
    linked_document_id: UUID | None = None
    linked_document_title: str | None = None
    linked_task_id: UUID | None = None
    linked_task_title: str | None = None
    is_counsel_only: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# MATTER REQUESTS & STRUCTURED WORKFLOW
# ---------------------------------------------------------------------------


class MatterRequestCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=3, max_length=5000)
    request_type: MatterRequestType = MatterRequestType.DOCUMENT_UPLOAD
    assigned_user_id: UUID | None = None
    due_date: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class MatterRequestSubmit(BaseModel):
    submitted_document_id: UUID | None = None
    response_notes: str | None = Field(None, max_length=5000)

    model_config = ConfigDict(extra="forbid")


class MatterRequestReview(BaseModel):
    review_notes: str | None = Field(None, max_length=5000)
    mark_status: MatterRequestStatus = MatterRequestStatus.REVIEWED

    model_config = ConfigDict(extra="forbid")


class MatterRequestResponse(BaseModel):
    id: UUID
    case_id: UUID
    requesting_user_id: UUID
    requesting_user_name: str
    assigned_user_id: UUID | None
    assigned_user_name: str | None
    title: str
    description: str
    request_type: MatterRequestType
    status: MatterRequestStatus
    due_date: datetime | None = None
    submitted_document_id: UUID | None = None
    submitted_document_title: str | None = None
    submitted_document_status: str | None = None
    response_notes: str | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    reviewed_by_user_id: UUID | None = None
    reviewed_by_user_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# PARTICIPANT DIRECTORY & BRIEF
# ---------------------------------------------------------------------------


class MatterParticipantDetailResponse(BaseModel):
    id: UUID
    user_id: UUID
    case_id: UUID
    participant_role: str
    status: str
    full_name: str
    email: str
    phone: str | None = None
    lawyer_bar_number: str | None = None
    lawyer_specialization: str | None = None
    lawyer_firm_name: str | None = None
    client_organization: str | None = None
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MatterBriefResponse(BaseModel):
    case_id: UUID
    title: str
    status: str
    created_at: datetime
    lead_counsel_name: str | None = None
    participants_count: int
    open_requests_count: int
    next_hearing_date: datetime | None = None
    next_hearing_court: str | None = None
    recent_documents_count: int
    pending_tasks_count: int

    model_config = ConfigDict(from_attributes=True)
