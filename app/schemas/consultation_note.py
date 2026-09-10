import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConsultationNoteCreate(BaseModel):
    summary: str = Field(..., min_length=5, description="Summary of legal advice and discussion")
    action_items: list[str] | None = Field(default=None, description="Actionable next steps recommended")
    client_shared: bool = Field(default=True, description="Whether the client can view this note")


class ConsultationNoteResponse(BaseModel):
    id: uuid.UUID
    consultation_id: uuid.UUID
    author_user_id: uuid.UUID
    summary: str
    action_items: list[str] | None = None
    client_shared: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
