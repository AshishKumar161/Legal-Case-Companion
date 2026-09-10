from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ReportMetadataItem(BaseModel):
    report_id: UUID
    generated_at: datetime
    generated_by_user_id: UUID
    generated_by_name: str
    generated_by_role: str

    model_config = {"from_attributes": True}


class CaseOverviewReportItem(BaseModel):
    case_id: UUID
    case_number: str | None = None
    title: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ParticipantReportItem(BaseModel):
    id: UUID
    user_id: UUID
    full_name: str
    email: str | None = None
    participant_role: str
    status: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class HearingReportItem(BaseModel):
    id: UUID
    court_name: str
    bench_judge: str | None = None
    hearing_date: datetime
    purpose: str | None = None
    outcome: str | None = None
    status: str

    model_config = {"from_attributes": True}


class DeadlineReportItem(BaseModel):
    id: UUID
    title: str
    deadline_type: str
    deadline_at: datetime
    status: str
    description: str | None = None

    model_config = {"from_attributes": True}


class TaskReportItem(BaseModel):
    id: UUID
    title: str
    description: str | None = None
    priority: str
    status: str
    due_date: datetime | None = None
    completed_at: datetime | None = None
    assignee_name: str | None = None

    model_config = {"from_attributes": True}


class DocumentReportItem(BaseModel):
    id: UUID
    name: str
    category: str
    security_status: str
    mime_type: str | None = None
    file_size_bytes: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TimelineReportItem(BaseModel):
    id: UUID
    event_type: str
    description: str
    created_at: datetime
    actor_user_id: UUID | None = None

    model_config = {"from_attributes": True}


class ConsultationReportItem(BaseModel):
    id: UUID
    lawyer_name: str | None = None
    scheduled_at: datetime
    status: str
    duration_minutes: int | None = None
    fee_amount: float | None = None
    currency: str | None = None

    model_config = {"from_attributes": True}


class CommunicationsSummaryReportItem(BaseModel):
    total_messages: int
    total_requests: int
    latest_activity_at: datetime | None = None

    model_config = {"from_attributes": True}


class NoteReportItem(BaseModel):
    id: UUID
    title: str | None = None
    content: str
    visibility: str
    author_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseSummaryReportResponse(BaseModel):
    metadata: ReportMetadataItem
    case_overview: CaseOverviewReportItem
    participants: list[ParticipantReportItem]
    hearings: list[HearingReportItem]
    deadlines: list[DeadlineReportItem]
    tasks: list[TaskReportItem]
    documents: list[DocumentReportItem]
    timeline: list[TimelineReportItem]
    consultations: list[ConsultationReportItem]
    communications_summary: CommunicationsSummaryReportItem
    notes: list[NoteReportItem]

    model_config = {"from_attributes": True}
