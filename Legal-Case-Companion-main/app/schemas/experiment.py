import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.experiment import ExperimentStatus


class ExperimentCreateRequest(BaseModel):
    experiment_id: str = Field(..., min_length=3, max_length=100)
    hypothesis: str = Field(..., min_length=5)
    cohort: str = Field(..., min_length=2, max_length=100)
    success_metrics: dict = Field(default_factory=dict)
    failure_metrics: dict = Field(default_factory=dict)
    start_at: datetime | None = None
    end_at: datetime | None = None
    notes: str | None = None


class ExperimentTransitionRequest(BaseModel):
    new_status: ExperimentStatus
    decision: str | None = None
    notes: str | None = None


class ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: str
    hypothesis: str
    cohort: str
    status: ExperimentStatus
    start_at: datetime
    end_at: datetime | None
    success_metrics: dict
    failure_metrics: dict
    decision: str | None
    notes: str | None
    owner_user_id: uuid.UUID | None
    created_at: datetime
