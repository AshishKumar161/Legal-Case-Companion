import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.task import TaskPriority, TaskSourceType, TaskStatus


class CaseTaskCreate(BaseModel):
    title: str
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: datetime | None = None
    owner_user_id: uuid.UUID | None = None
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
    source_type: TaskSourceType = TaskSourceType.MANUAL
    source_reference: str | None = None
    is_confirmed: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
