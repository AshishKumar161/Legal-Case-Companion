import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.job import JobType
from app.domain.jobs.job_service import JobService
from app.domain.jobs.job_worker import JobWorker

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

        # 4. Enqueue Stale Video Meeting cleanup (10-minute bucket idempotency)
        ten_min_bucket = now.minute // 10
        job_meeting = job_svc.enqueue_job(
            job_type=JobType.STALE_MEETING_CLEANUP,
            payload={"max_idle_hours": 2},
            idempotency_key=f"sched_stale_meeting_cleanup_{hour_key}_{ten_min_bucket}",
        )

        # 5. Enqueue Recording Upload retry scan (15-minute bucket idempotency)
        fifteen_min_bucket = now.minute // 15
        job_rec_retry = job_svc.enqueue_job(
            job_type=JobType.RECORDING_UPLOAD_RETRY,
            payload={"max_age_minutes": 60, "grace_period_minutes": 5},
            idempotency_key=f"sched_recording_retry_{hour_key}_{fifteen_min_bucket}",
        )

        # 6. Enqueue Webhook Reprocessing scan (15-minute bucket idempotency)
        job_webhook = job_svc.enqueue_job(
            job_type=JobType.WEBHOOK_REPROCESS,
            payload={"stale_minutes": 10, "limit": 25},
            idempotency_key=f"sched_webhook_retry_{hour_key}_{fifteen_min_bucket}",
        )

        # 7. Enqueue Commercial Reconciliation check (hourly idempotency)
        job_reconcile = job_svc.enqueue_job(
            job_type=JobType.COMMERCIAL_RECONCILIATION,
            payload={},
            idempotency_key=f"sched_commercial_reconciliation_{hour_key}",
        )

        # 8. Enqueue Expired Session / Token cleanup (daily idempotency)
        day_key = now.strftime("%Y-%m-%d")
        job_session = job_svc.enqueue_job(
            job_type=JobType.EXPIRED_SESSION_CLEANUP,
            payload={"refresh_token_retention_days": 30, "verification_token_retention_days": 7},
            idempotency_key=f"sched_expired_session_cleanup_{day_key}",
        )

        return {
            "deadline_scan_job_id": str(job_dl.id),
            "task_scan_job_id": str(job_task.id),
            "stale_recovery_job_id": str(job_stale.id),
            "stale_meeting_cleanup_job_id": str(job_meeting.id),
            "recording_retry_job_id": str(job_rec_retry.id),
            "webhook_reprocess_job_id": str(job_webhook.id),
            "commercial_reconciliation_job_id": str(job_reconcile.id),
            "expired_session_cleanup_job_id": str(job_session.id),
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
