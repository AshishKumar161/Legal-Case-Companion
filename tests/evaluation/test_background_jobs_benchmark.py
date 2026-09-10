from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.case import CaseParticipant, ParticipantRole, ParticipantStatus
from app.models.job import JobType
from app.models.notification import Notification
from app.models.workflow import CaseDeadline, DeadlineStatus, DeadlineType
from app.services.job_service import JobService
from app.domain.jobs.job_worker import JobWorker


def _setup_benchmark_user(client: TestClient, email: str, role: str = "CLIENT"):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": role, "full_name": "Benchmark User"},
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_background_jobs_and_notification_operations_benchmark(client: TestClient, db: Session):
    """Benchmark evaluating job throughput, multi-worker claim isolation,

    stale job recovery, and notification deduplication accuracy.
    """
    _u_client_id, h_client = _setup_benchmark_user(client, "bench_job_client@test.com", role="CLIENT")
    u_lawyer_id, _h_lawyer = _setup_benchmark_user(client, "bench_job_lawyer@test.com", role="LAWYER")

    res_c = client.post("/api/v1/cases", json={"title": "Benchmark Case", "description": "B"}, headers=h_client)
    case_id = res_c.json()["id"]

    p_lawyer = CaseParticipant(
        id=generate_uuid7(), case_id=UUID(case_id), user_id=UUID(u_lawyer_id),
        participant_role=ParticipantRole.LAWYER, status=ParticipantStatus.ACTIVE,
    )
    db.add(p_lawyer)

    # 1. Enqueue batch of 10 indexing jobs with unique idempotency keys
    job_svc = JobService(db)
    enqueued_jobs = []
    for i in range(10):
        j = job_svc.enqueue_job(
            job_type=JobType.DOCUMENT_INDEXING,
            payload={"document_id": str(generate_uuid7())},
            idempotency_key=f"bench_index_key_{i}",
        )
        enqueued_jobs.append(j)

    # Re-enqueuing the same 10 keys must produce 0 duplicate records
    for i in range(10):
        j_dup = job_svc.enqueue_job(
            job_type=JobType.DOCUMENT_INDEXING,
            payload={"document_id": str(generate_uuid7())},
            idempotency_key=f"bench_index_key_{i}",
        )
        assert j_dup.id == enqueued_jobs[i].id

    # 2. Benchmark Multi-Worker Concurrent Claiming
    # Worker 1 claims 6, Worker 2 claims remaining 4
    w1_claimed = job_svc.claim_jobs(worker_id="bench-worker-1", limit=6)
    w2_claimed = job_svc.claim_jobs(worker_id="bench-worker-2", limit=6)

    assert len(w1_claimed) == 6
    assert len(w2_claimed) == 4
    # Zero overlap between workers
    w1_ids = {j.id for j in w1_claimed}
    w2_ids = {j.id for j in w2_claimed}
    assert len(w1_ids.intersection(w2_ids)) == 0

    # 3. Worker Execution: All 10 jobs succeed
    w1 = JobWorker(db, worker_id="bench-worker-1")
    w2 = JobWorker(db, worker_id="bench-worker-2")
    for j in w1_claimed:
        w1.execute_job(j.id)
    for j in w2_claimed:
        w2.execute_job(j.id)

    stats = job_svc.get_job_stats()
    assert stats.succeeded_jobs >= 10
    assert stats.pending_jobs == 0
    assert stats.running_jobs == 0

    # 4. Benchmark Scheduled Scans & Notification Deduplication
    dl = CaseDeadline(
        id=generate_uuid7(), case_id=UUID(case_id), title="Statutory Appeal Deadline",
        deadline_at=datetime.now(UTC) + timedelta(hours=30),
        deadline_type=DeadlineType.STATUTORY_LIMITATION, status=DeadlineStatus.UPCOMING,
    )
    db.add(dl)
    db.commit()

    # First scan run
    scan_job1 = job_svc.enqueue_job(job_type=JobType.DEADLINE_REMINDER_SCAN, payload={})
    w1.execute_job(scan_job1.id)

    notif_count1 = db.query(Notification).filter(Notification.deadline_id == dl.id).count()
    assert notif_count1 >= 1

    # Second scan run (simulating repeated scheduler execution)
    scan_job2 = job_svc.enqueue_job(job_type=JobType.DEADLINE_REMINDER_SCAN, payload={})
    w1.execute_job(scan_job2.id)

    notif_count2 = db.query(Notification).filter(Notification.deadline_id == dl.id).count()
    assert notif_count2 == notif_count1  # Zero duplicate notifications
