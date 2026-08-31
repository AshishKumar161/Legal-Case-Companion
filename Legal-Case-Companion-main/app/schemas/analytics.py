from uuid import UUID
from pydantic import BaseModel, Field

from app.models.analytics import ProductEventType


class FunnelStepResponse(BaseModel):
    step: str
    count: int
    conversion_rate: float


class FunnelResponse(BaseModel):
    total_users: int
    funnel: list[FunnelStepResponse]


class AIEvaluationSummary(BaseModel):
    total_evaluations: int
    avg_grounding_score: float
    avg_citation_score: float
    failure_rate: float


class ProductEventCreate(BaseModel):
    event_type: ProductEventType
    case_id: UUID | None = None
    resource_id: UUID | None = None
    metadata_: dict | None = Field(default=None, alias="metadata")


class ProductHealthSummary(BaseModel):
    total_users: int
    active_matters: int
    total_documents_uploaded: int
    copilot_queries_count: int
    actions_completed_count: int
    funnel: list[FunnelStepResponse]
    ai_health: AIEvaluationSummary
    unresolved_feedback_p0_p1: int
    unresolved_feedback_total: int
