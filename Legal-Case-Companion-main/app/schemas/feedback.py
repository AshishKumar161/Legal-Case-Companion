from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.feedback import FeedbackCategory


class PilotFeedbackCreate(BaseModel):
    category: FeedbackCategory = FeedbackCategory.OTHER
    description: str = Field(..., min_length=3, max_length=5000)
    page_url: str = Field(..., max_length=500)

    model_config = ConfigDict(extra="forbid")


class PilotFeedbackUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=50)  # NEW, TRIAGED, IN_PROGRESS, RESOLVED, CLOSED
    priority: str | None = Field(default=None, max_length=20)  # P0, P1, P2, P3
    resolution_notes: str | None = Field(default=None, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class PilotFeedbackResponse(BaseModel):
    id: UUID
    user_id: UUID | None = None
    user_email: str | None = None
    category: FeedbackCategory
    description: str
    page_url: str
    status: str
    priority: str | None = "P2"
    resolution_notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
