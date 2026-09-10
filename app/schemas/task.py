import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskPriority, TaskSourceType, TaskStatus


class CaseTaskCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: datetime | None = None
    owner_user_id: uuid.UUID | None = None
    linked_evidence_id: uuid.UUID | None = None
    linked_hearing_id: uuid.UUID | None = None
    linked_deadline_id: uuid.UUID | None = None
    source_type: TaskSourceType = TaskSourceType.MANUAL
    source_reference: str | None = None
    is_confirmed: bool = True

    model_config = ConfigDict(extra="forbid")


class CaseTaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: TaskPriority | None = None
    due_date: datetime | None = None
    owner_user_id: uuid.UUID | None = None
    linked_evidence_id: uuid.UUID | None = None
    linked_hearing_id: uuid.UUID | None = None
    linked_deadline_id: uuid.UUID | None = None
    status: TaskStatus | None = None
    is_confirmed: bool | None = None

    model_config = ConfigDict(extra="forbid")


class CaseTaskResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: datetime | None
    owner_user_id: uuid.UUID | None
    created_by_user_id: uuid.UUID | None
    completed_at: datetime | None
    linked_evidence_id: uuid.UUID | None = None
    linked_hearing_id: uuid.UUID | None = None
    linked_deadline_id: uuid.UUID | None = None
    source_type: TaskSourceType = TaskSourceType.MANUAL
    source_reference: str | None = None
    is_confirmed: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseTaskReassignRequest(BaseModel):
    owner_user_id: uuid.UUID

    model_config = ConfigDict(extra="forbid")


class CaseTaskBatchActionRequest(BaseModel):
    task_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)
    action: Literal["COMPLETE", "CANCEL", "REASSIGN", "CHANGE_PRIORITY"]
    owner_user_id: uuid.UUID | None = None
    priority: TaskPriority | None = None

    model_config = ConfigDict(extra="forbid")


class CaseWorkflowTemplateApplyRequest(BaseModel):
    template_name: Literal[
        "HEARING_PREPARATION",
        "POST_HEARING_FOLLOWUP",
        "EVIDENCE_PREPARATION",
        "NEW_CONSULTATION",
    ]
    hearing_id: uuid.UUID | None = None
    assignee_user_id: uuid.UUID | None = None

    model_config = ConfigDict(extra="forbid")


class CaseHealthSummaryResponse(BaseModel):
    case_id: uuid.UUID
    has_upcoming_hearing: bool
    next_hearing_date: datetime | None = None
    next_hearing_court: str | None = None
    overdue_tasks_count: int
    upcoming_deadlines_count: int
    unreviewed_evidence_count: int
    latest_activity_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
