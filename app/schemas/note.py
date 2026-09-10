import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CaseNoteCreate(BaseModel):
    title: str | None = None
    content: str
    visibility: str | None = None
    is_private: bool | None = None

    model_config = ConfigDict(extra="forbid")


class CaseNoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    visibility: str | None = None
    is_private: bool | None = None

    model_config = ConfigDict(extra="forbid")


class CaseNoteResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    author_user_id: uuid.UUID
    title: str | None
    content: str
    visibility: str
    is_private: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
