import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.job import JobType
from app.services.job_service import JobService
from app.services.job_worker import JobWorker

logger = logging.getLogger(__name__)


class JobScheduler:
    """Manages scheduled periodic scans (deadlines, overdue tasks, stale job recovery)

    and orchestrates worker execution loops.
    """

    def __init__(self, worker_id: str = "scheduler-worker"):
        self.worker_id = worker_id

    def trigger_periodic_scans(self, db: Session) -> dict[str, str]:
        """Idempotently enqueues periodic maintenance and reminder jobs based on current time window."""
        job_svc = JobService(db)
        now = datetime.now(UTC)
        hour_key = now.strftime("%Y-%m-%d-%H")
        minute_bucket = now.minute // 5

        # 1. Enqueue Deadline scan (hourly idempotency)
        job_dl = job_svc.enqueue_job(
            job_type=JobType.DEADLINE_REMINDER_SCAN,
            payload={},
            idempotency_key=f"sched_deadline_scan_{hour_key}",
        )

        # 2. Enqueue Task overdue scan (hourly idempotency)
        job_task = job_svc.enqueue_job(
            job_type=JobType.TASK_OVERDUE_SCAN,
            payload={},
            idempotency_key=f"sched_task_scan_{hour_key}",
        )

        # 3. Enqueue Stale job recovery (5-minute bucket idempotency)
        job_stale = job_svc.enqueue_job(
            job_type=JobType.STALE_JOB_RECOVERY,
            payload={},
            idempotency_key=f"sched_stale_recovery_{hour_key}_{minute_bucket}",
        )

        return {
            "deadline_scan_job_id": str(job_dl.id),
            "task_scan_job_id": str(job_task.id),
            "stale_recovery_job_id": str(job_stale.id),
        }

    def run_worker_batch(self, db: Session, limit: int = 10, lease_seconds: int = 60) -> int:
        """Claims up to `limit` pending jobs and executes them sequentially.

        Returns total jobs processed in this batch.
        """
        job_svc = JobService(db)
        claimed = job_svc.claim_jobs(
            worker_id=self.worker_id,
            limit=limit,
            lease_seconds=lease_seconds,
        )

        if not claimed:
            return 0

        worker = JobWorker(db, worker_id=self.worker_id)
        processed = 0
        for job in claimed:
            try:
                worker.execute_job(job.id)
                processed += 1
            except Exception as e:  # noqa: BLE001
                logger.error(f"Worker batch execution failed for job {job.id}: {e}")

        return processed
