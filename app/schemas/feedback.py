from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.feedback import FeedbackCategory, FeedbackType


class PilotFeedbackCreate(BaseModel):
    category: FeedbackCategory = FeedbackCategory.OTHER
    feedback_type: FeedbackType = FeedbackType.USABILITY
    severity: str | None = Field(default=None, max_length=50)
    workflow: str | None = Field(default=None, max_length=100)
    sentiment: str | None = Field(default=None, max_length=50)
    reproducibility: str | None = Field(default=None, max_length=50)
    description: str = Field(..., min_length=3, max_length=5000)
    page_url: str = Field(..., max_length=500)
    linked_release_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class PilotFeedbackUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=50)  # NEW, TRIAGED, IN_PROGRESS, RESOLVED, CLOSED
    priority: str | None = Field(default=None, max_length=20)  # P0, P1, P2, P3
    product_priority: str | None = Field(default=None, max_length=20)
    resolution_notes: str | None = Field(default=None, max_length=2000)
    linked_incident_id: UUID | None = None

    model_config = ConfigDict(extra="forbid")


class PilotFeedbackResponse(BaseModel):
    id: UUID
    user_id: UUID | None = None
    user_email: str | None = None
    category: FeedbackCategory
    feedback_type: FeedbackType
    severity: str | None = None
    workflow: str | None = None
    sentiment: str | None = None
    reproducibility: str | None = None
    description: str
    page_url: str
    status: str
    priority: str | None = "P2"
    product_priority: str | None = "P2"
    resolution_notes: str | None = None
    linked_incident_id: UUID | None = None
    linked_release_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
