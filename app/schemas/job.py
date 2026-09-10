import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import JobStatus, JobType


class JobCreate(BaseModel):
    job_type: JobType
    payload: dict = Field(default_factory=dict)
    idempotency_key: str | None = None
    scheduled_at: datetime | None = None
    max_attempts: int = 3
    case_id: uuid.UUID | None = None

    model_config = ConfigDict(extra="forbid")


class JobResponse(BaseModel):
    id: uuid.UUID
    job_type: JobType
    status: JobStatus
    idempotency_key: str | None = None
    payload: dict = Field(default_factory=dict)
    attempt_count: int
    max_attempts: int
    scheduled_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_error: str | None = None
    error_category: str | None = None
    case_id: uuid.UUID | None = None
    created_by_user_id: uuid.UUID | None = None
    result_metadata: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobStatsResponse(BaseModel):
    total_jobs: int = 0
    pending_jobs: int = 0
    running_jobs: int = 0
    succeeded_jobs: int = 0
    failed_jobs: int = 0
    retrying_jobs: int = 0
