from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConsultationCreate(BaseModel):
    lawyer_id: UUID
    case_id: UUID | None = None
    scheduled_at: datetime
    duration_minutes: int = 30
    is_instant: bool = False

    model_config = ConfigDict(extra="forbid")


class ConsultationRejectRequest(BaseModel):
    reason: str | None = None

    model_config = ConfigDict(extra="forbid")


class ConsultationScheduleRequest(BaseModel):
    scheduled_at: datetime
    duration_minutes: int | None = None

    model_config = ConfigDict(extra="forbid")


class ConsultationRescheduleRequest(BaseModel):
    scheduled_at: datetime
    duration_minutes: int | None = None
    reason: str | None = None

    model_config = ConfigDict(extra="forbid")


class ConsultationCancelRequest(BaseModel):
    reason: str | None = None

    model_config = ConfigDict(extra="forbid")


class ConsultationNoShowRequest(BaseModel):
    reason: str | None = None

    model_config = ConfigDict(extra="forbid")


from app.schemas.video_meeting import VideoMeetingResponse


class ConsultationLinkCaseRequest(BaseModel):
    case_id: UUID
    assign_lawyer: bool = True

    model_config = ConfigDict(extra="forbid")


class ConsultationCreateCaseRequest(BaseModel):
    title: str = "Consultation Follow-up Matter"
    description: str | None = None
    practice_area: str | None = None
    court_jurisdiction: str | None = None

    model_config = ConfigDict(extra="forbid")


class ConsultationResponse(BaseModel):
    id: UUID
    client_id: UUID
    lawyer_id: UUID
    case_id: UUID | None
    scheduled_at: datetime
    duration_minutes: int
    fee_amount: float
    currency: str
    status: str
    completed_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    video_meeting: VideoMeetingResponse | None = None

    model_config = ConfigDict(from_attributes=True)
