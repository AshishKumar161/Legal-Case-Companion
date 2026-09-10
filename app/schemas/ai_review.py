import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.ai_review import (
    AIReviewCategory,
    AIReviewOutcome,
    AIReviewSeverity,
    AIReviewStatus,
)


class AIReviewCreateRequest(BaseModel):
    category: AIReviewCategory
    severity: AIReviewSeverity = AIReviewSeverity.SEV3_MEDIUM
    review_outcome: AIReviewOutcome = AIReviewOutcome.CONFIRMED_DEFECT
    original_prompt_snippet: str | None = None
    original_answer_snippet: str | None = None
    corrected_interpretation: str | None = None
    message_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    model_version: str | None = "gpt-4o"
    retrieval_config_version: str | None = "v1.0"
    linked_release_id: str | None = None
    linked_incident_id: uuid.UUID | None = None


class AIReviewActionRequest(BaseModel):
    action_taken: str = Field(..., min_length=3)


class AIReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    review_id: str
    message_id: uuid.UUID | None
    conversation_id: uuid.UUID | None
    reviewer_user_id: uuid.UUID | None
    category: AIReviewCategory
    severity: AIReviewSeverity
    review_outcome: AIReviewOutcome
    status: AIReviewStatus
    original_prompt_snippet: str | None
    original_answer_snippet: str | None
    corrected_interpretation: str | None
    model_version: str | None
    retrieval_config_version: str | None
    linked_release_id: str | None
    linked_incident_id: uuid.UUID | None
    action_taken: str | None
    created_at: datetime
