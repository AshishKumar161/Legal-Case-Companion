import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.workflow import (
    DeadlineSourceType,
    DeadlineStatus,
    DeadlineType,
    HearingSourceType,
    HearingStatus,
    ReminderStatus,
    ReminderTargetType,
)
from app.schemas.task import CaseTaskResponse


class CaseDeadlineBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    deadline_at: datetime
    deadline_type: DeadlineType = DeadlineType.GENERAL
    status: DeadlineStatus = DeadlineStatus.UPCOMING
    source_type: DeadlineSourceType = DeadlineSourceType.MANUAL
    source_reference: str | None = None
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    is_confirmed: bool = True
    linked_hearing_id: uuid.UUID | None = None
    retrieval_method: str | None = None
    retrieved_at: datetime | None = None


class CaseDeadlineCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    deadline_at: datetime
    deadline_type: DeadlineType = DeadlineType.GENERAL
    source_type: DeadlineSourceType = DeadlineSourceType.MANUAL
    source_reference: str | None = None
    is_confirmed: bool = True
    linked_hearing_id: uuid.UUID | None = None
    retrieval_method: str | None = None

    model_config = ConfigDict(extra="forbid")


class CaseDeadlineUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    deadline_at: datetime | None = None
    deadline_type: DeadlineType | None = None
    status: DeadlineStatus | None = None
    is_confirmed: bool | None = None
    linked_hearing_id: uuid.UUID | None = None

    model_config = ConfigDict(extra="forbid")


class CaseDeadlineResponse(CaseDeadlineBase):
    id: uuid.UUID
    case_id: uuid.UUID
    completed_at: datetime | None = None
    created_by_user_id: uuid.UUID | None = None
    confirmed_by_user_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseHearingBase(BaseModel):
    court_name: str = Field(..., min_length=2, max_length=255)
    hearing_at: datetime
    purpose: str = Field(..., min_length=2, max_length=255)
    status: HearingStatus = HearingStatus.SCHEDULED
    bench_or_coram: str | None = None
    court_number: str | None = None
    hearing_type: str | None = None
    next_date: datetime | None = None
    notes: str | None = None
    source_type: HearingSourceType = HearingSourceType.MANUAL
    source_reference: str | None = None
    is_confirmed: bool = True


class CaseHearingCreate(BaseModel):
    court_name: str = Field(..., min_length=2, max_length=255)
    hearing_at: datetime
    purpose: str = Field(..., min_length=2, max_length=255)
    bench_or_coram: str | None = None
    court_number: str | None = None
    hearing_type: str | None = None
    next_date: datetime | None = None
    notes: str | None = None
    source_type: HearingSourceType = HearingSourceType.MANUAL
    source_reference: str | None = None
    is_confirmed: bool = True

    model_config = ConfigDict(extra="forbid")


class CaseHearingUpdate(BaseModel):
    court_name: str | None = None
    hearing_at: datetime | None = None
    purpose: str | None = None
    status: HearingStatus | None = None
    bench_or_coram: str | None = None
    court_number: str | None = None
    hearing_type: str | None = None
    next_date: datetime | None = None
    notes: str | None = None
    is_confirmed: bool | None = None

    model_config = ConfigDict(extra="forbid")


class CaseHearingAdjournRequest(BaseModel):
    next_date: datetime = Field(..., description="Next hearing date upon adjournment")
    purpose: str | None = None
    notes: str | None = None

    model_config = ConfigDict(extra="forbid")


class CaseHearingCompleteRequest(BaseModel):
    notes: str | None = None
    orders_summary: str | None = None

    model_config = ConfigDict(extra="forbid")


class CaseHearingECourtsImportRequest(BaseModel):
    court_name: str = Field(..., min_length=2, max_length=255)
    hearing_at: datetime
    purpose: str = Field(..., min_length=2, max_length=255)
    bench_or_coram: str | None = None
    court_number: str | None = None
    hearing_type: str | None = None
    source_reference: str = Field(..., min_length=2, max_length=255, description="CNR or official cause-list reference")
    notes: str | None = None

    model_config = ConfigDict(extra="forbid")


class CaseHearingResponse(CaseHearingBase):
    id: uuid.UUID
    case_id: uuid.UUID
    created_by_user_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseReminderCreate(BaseModel):
    target_type: ReminderTargetType
    target_id: uuid.UUID
    remind_at: datetime

    model_config = ConfigDict(extra="forbid")


class CaseReminderResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    target_type: ReminderTargetType
    target_id: uuid.UUID
    remind_at: datetime
    status: ReminderStatus
    created_by_user_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseOperationsSummary(BaseModel):
    open_tasks_count: int = 0
    overdue_tasks_count: int = 0
    upcoming_deadlines_count: int = 0
    overdue_deadlines_count: int = 0
    next_hearing: CaseHearingResponse | None = None
    unconfirmed_suggestions_count: int = 0


class CaseWorkflowResponse(BaseModel):
    case_id: uuid.UUID
    tasks: list[CaseTaskResponse] = Field(default_factory=list)
    deadlines: list[CaseDeadlineResponse] = Field(default_factory=list)
    hearings: list[CaseHearingResponse] = Field(default_factory=list)
    operations_summary: CaseOperationsSummary = Field(default_factory=CaseOperationsSummary)
