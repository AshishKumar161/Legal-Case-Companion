from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    id: UUID
    consultation_id: UUID
    sender_id: UUID
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
