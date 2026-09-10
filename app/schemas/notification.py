from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import NotificationType


class NotificationBase(BaseModel):
    type: NotificationType
    title: str = Field(..., max_length=255)
    message: str = Field(..., max_length=1000)
    case_id: UUID | None = None
    consultation_id: UUID | None = None
    task_id: UUID | None = None
    deadline_id: UUID | None = None
    hearing_id: UUID | None = None
    document_id: UUID | None = None
    event_id: str | None = None
    metadata: dict | None = Field(default=None, alias="metadata_")


class NotificationCreate(NotificationBase):
    user_id: UUID


class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: NotificationType
    title: str
    message: str
    case_id: UUID | None = None
    consultation_id: UUID | None = None
    task_id: UUID | None = None
    deadline_id: UUID | None = None
    hearing_id: UUID | None = None
    document_id: UUID | None = None
    event_id: str | None = None
    metadata: dict | None = Field(default=None, alias="metadata_")
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UnreadCountResponse(BaseModel):
    unread_count: int


class NotificationReadAllResponse(BaseModel):
    updated_count: int


class NotificationBulkReadRequest(BaseModel):
    notification_ids: list[UUID] = Field(..., max_length=100)
    model_config = ConfigDict(extra="forbid")


class NotificationBulkDeleteRequest(BaseModel):
    notification_ids: list[UUID] = Field(..., max_length=100)
    model_config = ConfigDict(extra="forbid")


class NotificationBulkDeleteResponse(BaseModel):
    deleted_count: int


class NotificationPreferenceResponse(BaseModel):
    email_enabled: bool
    case_updates: bool
    task_updates: bool
    consultation_updates: bool


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: bool | None = None
    case_updates: bool | None = None
    task_updates: bool | None = None
    consultation_updates: bool | None = None

    model_config = ConfigDict(extra="forbid")
