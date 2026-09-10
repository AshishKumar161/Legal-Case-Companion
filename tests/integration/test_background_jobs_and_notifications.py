from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.models.case import CaseParticipant, ParticipantRole, ParticipantStatus
from app.models.document import Document, DocumentSecurityStatus
from app.models.job import BackgroundJob, JobStatus, JobType
from app.models.notification import Notification, NotificationType
from app.models.task import CaseTask, TaskStatus
from app.models.user import User, UserRole
from app.models.workflow import CaseDeadline, DeadlineStatus, DeadlineType
from app.domain.jobs.job_scheduler import JobScheduler
from app.services.job_service import JobService
from app.domain.jobs.job_worker import JobWorker


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "dummy-test-key"
    yield
    settings.OPENAI_API_KEY = original_key


def _setup_user(client: TestClient, email: str, role: str = "CLIENT"):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": role, "full_name": "Job User"},
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_job_enqueue_and_lifecycle(client: TestClient, db: Session):
    """Verifies job creation, deduplication via idempotency_key, worker claiming, and successful execution."""
    job_svc = JobService(db)

    # 1. Enqueue job with idempotency key
    job1 = job_svc.enqueue_job(
        job_type=JobType.DOCUMENT_INDEXING,
        payload={"document_id": str(generate_uuid7())},
        idempotency_key="unique_index_key_001",
    )
    assert job1.status == JobStatus.PENDING
    assert job1.attempt_count == 0

    # 2. Duplicate enqueue returns existing job
    job2 = job_svc.enqueue_job(
        job_type=JobType.DOCUMENT_INDEXING,
        payload={"document_id": str(generate_uuid7())},
        idempotency_key="unique_index_key_001",
    )
    assert job1.id == job2.id

    # 3. Worker claims job
    claimed = job_svc.claim_jobs(worker_id="worker-1", limit=10, lease_seconds=30)
    claimed_ids = [j.id for j in claimed]
    assert job1.id in claimed_ids

    db.refresh(job1)
    assert job1.status == JobStatus.RUNNING
    assert job1.locked_by == "worker-1"
    assert job1.attempt_count == 1

    # 4. Worker executes job
    worker = JobWorker(db, worker_id="worker-1")
    executed = worker.execute_job(job1.id)
    assert executed.status == JobStatus.SUCCEEDED
    assert executed.completed_at is not None
    assert executed.locked_until is None


def test_job_concurrency_lease_locking(client: TestClient, db: Session):
    """Verifies that while worker A holds a job lease, worker B cannot claim the same job."""
    job_svc = JobService(db)
    job = job_svc.enqueue_job(
        job_type=JobType.NOTIFICATION_DELIVERY,
        payload={"target": "user@test.com"},
        idempotency_key="concurrent_claim_test",
    )

    # Worker 1 claims job for 60 seconds
    claimed_w1 = job_svc.claim_jobs(worker_id="worker-A", limit=5, lease_seconds=60)
    assert job.id in [j.id for j in claimed_w1]

    # Worker 2 attempts to claim -> gets 0 jobs (it is locked)
    claimed_w2 = job_svc.claim_jobs(worker_id="worker-B", limit=5, lease_seconds=60)
    assert job.id not in [j.id for j in claimed_w2]


def test_job_retry_and_permanent_failure_classification(client: TestClient, db: Session):
    """Verifies that permanent domain errors fail immediately while transient errors undergo bounded retries."""
    job_svc = JobService(db)
    worker = JobWorker(db, worker_id="worker-test")

    # 1. Permanent error (missing document_id)
    job_perm = job_svc.enqueue_job(
        job_type=JobType.DOCUMENT_PROCESSING,
        payload={},  # Missing document_id triggers ValidationError
        max_attempts=3,
    )
    job_svc.claim_jobs(worker_id="worker-test", limit=5)
    res_perm = worker.execute_job(job_perm.id)
    assert res_perm.status in (JobStatus.FAILED, JobStatus.DEAD_LETTER)
    assert res_perm.error_category == "PERMANENT"

    # 2. Transient error simulation (unreachable host / exception)
    job_trans = job_svc.enqueue_job(
        job_type=JobType.DOCUMENT_INDEXING,
        payload={"document_id": str(generate_uuid7())},
        max_attempts=2,
    )
    # Patch handler to raise transient RuntimeError
    original_handler = worker._handle_document_indexing
    worker._handle_document_indexing = lambda j: (_ for _ in ()).throw(RuntimeError("Temporary DB timeout"))

    job_svc.claim_jobs(worker_id="worker-test", limit=5)
    res_trans1 = worker.execute_job(job_trans.id)
    assert res_trans1.status == JobStatus.RETRYING
    assert res_trans1.attempt_count == 1
    assert res_trans1.error_category == "TRANSIENT"

    # Second attempt claimed & executed -> exhausted
    job_trans.scheduled_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    job_svc.claim_jobs(worker_id="worker-test", limit=5)
    res_trans2 = worker.execute_job(job_trans.id)
    assert res_trans2.status in (JobStatus.FAILED, JobStatus.DEAD_LETTER)
    assert res_trans2.error_category == "TRANSIENT_EXHAUSTED"

    worker._handle_document_indexing = original_handler


def test_stale_job_recovery(client: TestClient, db: Session):
    """Verifies that jobs abandoned in RUNNING state past lease expiration are recovered."""
    job_svc = JobService(db)
    stale_job = job_svc.enqueue_job(
        job_type=JobType.DOCUMENT_INDEXING,
        payload={"document_id": str(generate_uuid7())},
        max_attempts=3,
    )
    # Simulate a crashed worker: marked RUNNING with expired locked_until
    stale_job.status = JobStatus.RUNNING
    stale_job.locked_by = "dead-worker"
    stale_job.locked_until = datetime.now(UTC) - timedelta(minutes=10)
    stale_job.attempt_count = 1
    db.commit()

    # Trigger stale job recovery
    recovery_job = job_svc.enqueue_job(job_type=JobType.STALE_JOB_RECOVERY, payload={})
    worker = JobWorker(db, worker_id="recovery-worker")
    worker.execute_job(recovery_job.id)

    db.refresh(stale_job)
    assert stale_job.status == JobStatus.RETRYING
    assert stale_job.locked_until is None


def test_scheduled_deadline_and_task_reminder_scans(client: TestClient, db: Session):
    """Verifies scheduled scanning for approaching deadlines, overdue deadlines, and overdue tasks with notification deduplication."""
    _u_client_id, h_client = _setup_user(client, "sched_client@test.com", role="CLIENT")
    u_lawyer_id, _h_lawyer = _setup_user(client, "sched_lawyer@test.com", role="LAWYER")

    res_c = client.post("/api/v1/cases", json={"title": "Scheduled Reminders Case", "description": "D"}, headers=h_client)
    case_id = res_c.json()["id"]

    # Add lawyer participant
    p_lawyer = CaseParticipant(
        id=generate_uuid7(), case_id=UUID(case_id), user_id=UUID(u_lawyer_id),
        participant_role=ParticipantRole.LAWYER, status=ParticipantStatus.ACTIVE,
    )
    db.add(p_lawyer)

    # 1. Seed upcoming deadline (in 24 hours)
    dl_appr = CaseDeadline(
        id=generate_uuid7(), case_id=UUID(case_id), title="Filing Rejoinder",
        deadline_at=datetime.now(UTC) + timedelta(hours=24), deadline_type=DeadlineType.COURT_FILING,
        status=DeadlineStatus.UPCOMING,
    )
    # 2. Seed overdue task
    task_ovrd = CaseTask(
        id=generate_uuid7(), case_id=UUID(case_id), title="Client Document Review",
        due_date=datetime.now(UTC) - timedelta(days=1), owner_user_id=UUID(u_lawyer_id),
        status=TaskStatus.IN_PROGRESS,
    )
    db.add_all([dl_appr, task_ovrd])
    db.commit()

    # 3. Trigger Scheduled Scans via Scheduler
    scheduler = JobScheduler(worker_id="test-scheduler")
    scheduler.trigger_periodic_scans(db)
    processed = scheduler.run_worker_batch(db, limit=10)
    assert processed >= 2

    # 4. Verify notifications delivered
    notifs_lawyer = db.query(Notification).filter(Notification.user_id == UUID(u_lawyer_id)).all()
    types = [n.type for n in notifs_lawyer]
    assert NotificationType.DEADLINE_APPROACHING in types
    assert NotificationType.TASK_OVERDUE in types

    # 5. Idempotency: re-running scan on same day produces zero duplicate notifications
    prev_count = len(notifs_lawyer)
    job_svc = JobService(db)
    scan_job = job_svc.enqueue_job(job_type=JobType.DEADLINE_REMINDER_SCAN, payload={})
    worker = JobWorker(db)
    worker.execute_job(scan_job.id)

    curr_count = db.query(Notification).filter(Notification.user_id == UUID(u_lawyer_id)).count()
    assert curr_count == prev_count


def test_document_pipeline_to_job_and_notification(client: TestClient, db: Session):
    """Verifies that completed malware scan enqueues a background processing job that processes and notifies."""
    _u_id, headers = _setup_user(client, "doc_pipe@test.com", role="CLIENT")
    res_c = client.post("/api/v1/cases", json={"title": "Doc Job Case", "description": "D"}, headers=headers)
    case_id = res_c.json()["id"]

    # 1. Create document metadata
    res_doc = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "EvidenceDoc.pdf", "mime_type": "application/pdf", "file_size": 1024, "document_type": "EVIDENCE"},
        headers=headers,
    )
    assert res_doc.status_code == 201
    doc_id = res_doc.json()["document"]["id"]

    # 2. Simulate Scanner marking SAFE -> enqueues job
    doc = db.query(Document).filter(Document.id == UUID(doc_id)).first()
    doc.security_status = DocumentSecurityStatus.QUARANTINED
    db.commit()

    from app.domain.evidence.scanner_service import ScannerService
    scanner = ScannerService(db)
    scanner.simulate_scan(UUID(doc_id), is_safe=True)

    # 3. Verify BackgroundJob was created
    job = (
        db.query(BackgroundJob)
        .filter(BackgroundJob.job_type == JobType.DOCUMENT_PROCESSING, BackgroundJob.case_id == UUID(case_id))
        .first()
    )
    assert job is not None
    assert job.status == JobStatus.PENDING

    # 4. Worker executes processing job
    worker = JobWorker(db, worker_id="test-worker")
    worker.execute_job(job.id)

    db.refresh(job)
    assert job.status == JobStatus.SUCCEEDED

    # 5. Check DOCUMENT_READY notification was created
    doc_notif = (
        db.query(Notification)
        .filter(Notification.document_id == UUID(doc_id), Notification.type == NotificationType.DOCUMENT_READY)
        .first()
    )
    assert doc_notif is not None


def test_admin_job_visibility_and_rbac(client: TestClient, db: Session):
    """Verifies that only users with ADMIN role can inspect and trigger background jobs."""
    _u_admin_id, h_admin = _setup_user(client, "admin_jobs@test.com", role="CLIENT")
    # Upgrade user to ADMIN directly in database
    admin_user = db.query(User).filter(User.email == "admin_jobs@test.com").first()
    admin_user.role = UserRole.ADMIN
    db.commit()

    _u_client_id, h_client = _setup_user(client, "client_jobs@test.com", role="CLIENT")

    # Seed a job
    job_svc = JobService(db)
    job = job_svc.enqueue_job(job_type=JobType.DEADLINE_REMINDER_SCAN, payload={})

    # Client receives 403 Forbidden
    res_client = client.get("/api/v1/admin/jobs", headers=h_client)
    assert res_client.status_code == 403

    # Admin lists jobs
    res_admin = client.get("/api/v1/admin/jobs", headers=h_admin)
    assert res_admin.status_code == 200
    assert res_admin.json()["total"] >= 1

    # Admin gets stats
    res_stats = client.get("/api/v1/admin/jobs/stats", headers=h_admin)
    assert res_stats.status_code == 200
    assert res_stats.json()["total_jobs"] >= 1

    # Admin executes job
    res_exec = client.post(f"/api/v1/admin/jobs/{job.id}/execute", headers=h_admin)
    assert res_exec.status_code == 200
    assert res_exec.json()["status"] == JobStatus.SUCCEEDED.value
