from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.profile import LawyerProfileResponse


class CaseCreate(BaseModel):
    title: str
    description: str
    model_config = {"extra": "forbid"}


class CaseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    model_config = {"extra": "forbid"}


class CaseResponse(BaseModel):
    id: UUID
    title: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ParticipantAdd(BaseModel):
    user_id: UUID
    participant_role: str
    model_config = {"extra": "forbid"}


class GrantLawyerAccessRequest(BaseModel):
    lawyer_user_id: UUID
    consultation_id: UUID | None = None
    model_config = {"extra": "forbid"}


class ParticipantUpdate(BaseModel):
    participant_role: str
    model_config = {"extra": "forbid"}


class ParticipantResponse(BaseModel):
    id: UUID
    case_id: UUID
    user_id: UUID
    participant_role: str
    status: str

    model_config = {"from_attributes": True}


class TimelineEventResponse(BaseModel):
    id: UUID
    case_id: UUID
    actor_user_id: UUID | None
    event_type: str
    description: str
    event_metadata: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseWorkspaceResponse(BaseModel):
    case: CaseResponse
    effective_permissions: list[str]
    participants: list[ParticipantResponse]
    lawyer: LawyerProfileResponse | None
    document_count: int
    documents_summary: dict = {}
    tasks_summary: dict = {}
    upcoming_deadlines: list[dict] = []
    notes_count: int = 0
    recent_activities: list[TimelineEventResponse]
    intelligence_summary: dict = {}

    model_config = {"from_attributes": True}
