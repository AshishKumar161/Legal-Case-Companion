"""Persistence repository for BackgroundJob entities."""

from uuid import UUID
from sqlalchemy.orm import Session

from app.models.job import BackgroundJob, JobStatus, JobType


class JobRepository:
    """Encapsulates persistence operations for BackgroundJob domain models."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, job_id: UUID) -> BackgroundJob | None:
        """Retrieves a job by UUID, excluding soft-deleted records."""
        return (
            self.db.query(BackgroundJob)
            .filter(BackgroundJob.id == job_id, BackgroundJob.deleted_at.is_(None))
            .first()
        )

    def get_by_idempotency_key(self, idempotency_key: str) -> BackgroundJob | None:
        """Retrieves a job by its unique idempotency key."""
        return (
            self.db.query(BackgroundJob)
            .filter(BackgroundJob.idempotency_key == idempotency_key)
            .first()
        )

    def list_by_status(
        self,
        status: JobStatus,
        job_type: JobType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BackgroundJob]:
        """Lists background jobs by execution status with optional job type filter."""
        query = self.db.query(BackgroundJob).filter(
            BackgroundJob.status == status,
            BackgroundJob.deleted_at.is_(None),
        )
        if job_type:
            query = query.filter(BackgroundJob.job_type == job_type)
        return query.order_by(BackgroundJob.created_at.desc()).offset(offset).limit(limit).all()

    def count_by_status(self, status: JobStatus) -> int:
        """Counts jobs currently in a given status."""
        return (
            self.db.query(BackgroundJob.id)
            .filter(BackgroundJob.status == status, BackgroundJob.deleted_at.is_(None))
            .count()
        )
