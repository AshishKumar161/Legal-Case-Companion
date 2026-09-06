from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class OperationalAttentionItem(BaseModel):
    item_id: str
    item_type: Literal[
        "OVERDUE_TASK",
        "OVERDUE_DEADLINE",
        "IMMINENT_HEARING",
        "APPROACHING_DEADLINE",
        "UNREVIEWED_EVIDENCE",
    ]
    title: str
    case_id: UUID
    case_title: str
    severity: Literal["URGENT", "WARNING", "INFO"]
    reason: str
    action_href: str
    action_label: str
    due_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TodayAgendaItem(BaseModel):
    id: str
    event_type: Literal["HEARING", "DEADLINE", "TASK", "CONSULTATION"]
    title: str
    scheduled_at: datetime
    time_display: str
    case_id: UUID | None = None
    case_title: str
    court_info: str | None = None
    status: str
    priority: str | None = None
    action_href: str
    action_label: str
    is_urgent: bool = False

    model_config = ConfigDict(from_attributes=True)


class UpcomingHearingSummary(BaseModel):
    hearing_id: UUID
    case_id: UUID
    case_title: str
    court_name: str
    courtroom: str | None = None
    bench: str | None = None
    purpose: str | None = None
    hearing_at: datetime
    time_display: str
    status: str
    preparation_tasks_total: int = 0
    preparation_tasks_completed: int = 0
    exhibits_count: int = 0
    bundle_status: str | None = None
    action_href: str

    model_config = ConfigDict(from_attributes=True)


class UpcomingDeadlineSummary(BaseModel):
    deadline_id: UUID
    case_id: UUID
    case_title: str
    title: str
    deadline_at: datetime
    time_display: str
    status: str
    source: str
    retrieval_method: str | None = None
    is_urgent: bool = False
    action_href: str

    model_config = ConfigDict(from_attributes=True)


class AssignedMatterSummary(BaseModel):
    case_id: UUID
    title: str
    case_number: str | None = None
    status: str
    court_name: str | None = None
    next_hearing_at: datetime | None = None
    next_hearing_purpose: str | None = None
    overdue_tasks_count: int = 0
    active_deadlines_count: int = 0
    unreviewed_evidence_count: int = 0
    bundle_status: str | None = None
    last_activity_at: datetime | None = None
    action_href: str

    model_config = ConfigDict(from_attributes=True)


class LawyerOperationalMetrics(BaseModel):
    active_cases_count: int = 0
    upcoming_hearings_count: int = 0
    overdue_tasks_count: int = 0
    upcoming_deadlines_count: int = 0
    pending_consultations_count: int = 0
    unread_notifications_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class LawyerDashboardResponse(BaseModel):
    metrics: LawyerOperationalMetrics
    today_agenda: list[TodayAgendaItem] = Field(default_factory=list)
    needs_attention: list[OperationalAttentionItem] = Field(default_factory=list)
    upcoming_hearings: list[UpcomingHearingSummary] = Field(default_factory=list)
    upcoming_deadlines: list[UpcomingDeadlineSummary] = Field(default_factory=list)
    high_priority_tasks: list[TodayAgendaItem] = Field(default_factory=list)
    assigned_matters: list[AssignedMatterSummary] = Field(default_factory=list)
    range_days: int = 7

    model_config = ConfigDict(from_attributes=True)
