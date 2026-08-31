import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.core.identifiers import generate_uuid7
from app.models.job import BackgroundJob, JobStatus, JobType
from app.schemas.job import JobStatsResponse

logger = logging.getLogger(__name__)


class JobService:
    """Manages transactional lifecycle, enqueueing, querying, and claiming of background jobs."""

    def __init__(self, db: Session):
        self.db = db

    def enqueue_job(
        self,
        job_type: JobType,
        payload: dict,
        idempotency_key: str | None = None,
        scheduled_at: datetime | None = None,
        max_attempts: int = 3,
        case_id: uuid.UUID | None = None,
        created_by_user_id: uuid.UUID | None = None,
    ) -> BackgroundJob:
        """Transactionally enqueues a background job. If an idempotency key is provided,

        prevents duplicate enqueueing and returns the existing job.
        """
        now = datetime.now(UTC)
        if scheduled_at is None:
            scheduled_at = now
        elif scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=UTC)

        if idempotency_key:
            existing = (
                self.db.query(BackgroundJob)
                .filter(
                    BackgroundJob.idempotency_key == idempotency_key,
                    BackgroundJob.deleted_at.is_(None),
                )
                .first()
            )
            if existing:
                logger.info(
                    f"Job with idempotency_key {idempotency_key} already exists (ID {existing.id}). Returning existing."
                )
                return existing

        job = BackgroundJob(
            id=generate_uuid7(),
            job_type=job_type,
            status=JobStatus.PENDING,
            idempotency_key=idempotency_key,
            payload=payload,
            attempt_count=0,
            max_attempts=max_attempts,
            scheduled_at=scheduled_at,
            case_id=case_id,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def claim_jobs(
        self,
        worker_id: str,
        limit: int = 5,
        lease_seconds: int = 60,
    ) -> list[BackgroundJob]:
        """Atomically claims pending/retrying jobs for a worker instance.

        Uses SELECT ... FOR UPDATE SKIP LOCKED on PostgreSQL to prevent concurrency races.
        """
        now = datetime.now(UTC)
        query = (
            self.db.query(BackgroundJob)
            .filter(
                BackgroundJob.status.in_([JobStatus.PENDING, JobStatus.RETRYING]),
                BackgroundJob.scheduled_at <= now,
                or_(
                    BackgroundJob.locked_until.is_(None),
                    BackgroundJob.locked_until < now,
                ),
                BackgroundJob.deleted_at.is_(None),
            )
            .order_by(BackgroundJob.scheduled_at.asc(), BackgroundJob.id.asc())
        )

        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)

        claimed = query.limit(limit).all()

        lease_expiry = now + timedelta(seconds=lease_seconds)
        for job in claimed:
            job.status = JobStatus.RUNNING
            job.locked_by = worker_id
            job.locked_until = lease_expiry
            job.started_at = now
            job.attempt_count += 1

        if claimed:
            self.db.commit()
            for job in claimed:
                self.db.refresh(job)

        return claimed

    def get_job_by_id(self, job_id: uuid.UUID) -> BackgroundJob:
        job = (
            self.db.query(BackgroundJob)
            .filter(BackgroundJob.id == job_id, BackgroundJob.deleted_at.is_(None))
            .first()
        )
        if not job:
            raise ResourceNotFoundError("Job not found")
        return job

    def list_jobs(
        self,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
        case_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        limit = min(max(limit, 1), 100)
        query = self.db.query(BackgroundJob).filter(BackgroundJob.deleted_at.is_(None))

        if status is not None:
            query = query.filter(BackgroundJob.status == status)
        if job_type is not None:
            query = query.filter(BackgroundJob.job_type == job_type)
        if case_id is not None:
            query = query.filter(BackgroundJob.case_id == case_id)

        total = query.count()
        items = (
            query.order_by(BackgroundJob.created_at.desc(), BackgroundJob.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def get_job_stats(self) -> JobStatsResponse:
        rows = (
            self.db.query(BackgroundJob.status, func.count(BackgroundJob.id))
            .filter(BackgroundJob.deleted_at.is_(None))
            .group_by(BackgroundJob.status)
            .all()
        )
        counts = {status: count for status, count in rows}
        total = sum(counts.values())
        return JobStatsResponse(
            total_jobs=total,
            pending_jobs=counts.get(JobStatus.PENDING, 0),
            running_jobs=counts.get(JobStatus.RUNNING, 0),
            succeeded_jobs=counts.get(JobStatus.SUCCEEDED, 0),
            failed_jobs=counts.get(JobStatus.FAILED, 0),
            retrying_jobs=counts.get(JobStatus.RETRYING, 0),
        )
