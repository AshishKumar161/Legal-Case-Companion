import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.job import BackgroundJob, JobStatus, JobType
from app.core.security import hash_password
from app.models.user import AccountStatus, User, UserRole
from app.domain.jobs.job_service import JobService
from app.domain.jobs.job_worker import JobWorker


def _setup_user(client: TestClient, db: Session, email: str, role: UserRole = UserRole.CLIENT) -> tuple[str, dict]:
    user = User(
        id=generate_uuid7(),
        email=email,
        password_hash=hash_password("SecurePassword123!"),
        role=role,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res.json()["access_token"]
    return str(user.id), {"Authorization": f"Bearer {token}"}


def test_multi_instance_worker_claiming_concurrency(db: Session):
    """
    Verify that when two workers claim jobs from the queue concurrently,
    no job is claimed more than once and the sets of claimed jobs are completely disjoint.
    """
    job_svc = JobService(db)

    # 1. Enqueue 8 distinct maintenance jobs
    job_ids = []
    for i in range(8):
        job = job_svc.enqueue_job(
            job_type=JobType.STALE_MEETING_CLEANUP,
            payload={"limit": 10, "stale_minutes": 60, "marker": i},
            idempotency_key=f"concurrency_test_claim_{i}_{uuid.uuid4().hex[:6]}",
        )
        job_ids.append(job.id)

    # 2. Worker Alpha claims 4 jobs
    claimed_alpha = job_svc.claim_jobs(worker_id="worker-alpha", limit=4, lease_seconds=60)
    alpha_ids = {j.id for j in claimed_alpha}
    assert len(alpha_ids) == 4

    # 3. Worker Beta claims remaining jobs
    claimed_beta = job_svc.claim_jobs(worker_id="worker-beta", limit=4, lease_seconds=60)
    beta_ids = {j.id for j in claimed_beta}
    assert len(beta_ids) == 4

    # 4. Strictly mutually exclusive: zero overlap
    assert alpha_ids.isdisjoint(beta_ids)
    assert alpha_ids.union(beta_ids) == set(job_ids)

    # 5. Worker Alpha cannot re-claim already locked jobs
    claimed_alpha_again = job_svc.claim_jobs(worker_id="worker-alpha", limit=4, lease_seconds=60)
    assert len(claimed_alpha_again) == 0

    # 6. Both workers execute their claimed batches cleanly
    worker_alpha = JobWorker(db, worker_id="worker-alpha")
    for j in claimed_alpha:
        res = worker_alpha.execute_job(j.id)
        assert res.status == JobStatus.SUCCEEDED

    worker_beta = JobWorker(db, worker_id="worker-beta")
    for j in claimed_beta:
        res = worker_beta.execute_job(j.id)
        assert res.status == JobStatus.SUCCEEDED


def test_worker_crash_lease_expiry_and_recovery(db: Session):
    """
    Verify that a worker that crashes while holding a RUNNING lease is safely
    reclaimed after locked_until expires, transitions to RETRYING, and can be
    claimed and completed by a healthy worker.
    """
    job_svc = JobService(db)

    # 1. Create a job simulating a worker crash mid-execution
    job = job_svc.enqueue_job(
        job_type=JobType.EXPIRED_SESSION_CLEANUP,
        payload={"refresh_token_retention_days": 30, "verification_token_retention_days": 7},
        idempotency_key=f"lease_crash_test_{uuid.uuid4().hex[:6]}",
    )
    job.status = JobStatus.RUNNING
    job.locked_by = "worker-crashed-node-42"
    job.locked_until = datetime.now(UTC) - timedelta(minutes=5)
    job.attempt_count = 1
    db.commit()

    # 2. Trigger stale job reclaim
    reclaimed_count = job_svc.reclaim_stale_jobs()
    assert reclaimed_count >= 1

    db.refresh(job)
    assert job.status == JobStatus.RETRYING
    assert job.locked_by is None
    assert job.locked_until is None

    # 3. Healthy worker claims and executes the reclaimed job
    healthy_claimed = job_svc.claim_jobs(worker_id="worker-healthy", limit=5, lease_seconds=60)
    assert job.id in [j.id for j in healthy_claimed]

    worker = JobWorker(db, worker_id="worker-healthy")
    completed = worker.execute_job(job.id)
    assert completed.status == JobStatus.SUCCEEDED
    assert completed.attempt_count == 2


def test_dead_letter_on_max_attempts_exceeded(db: Session):
    """
    Verify that a job exceeding max_attempts is transitioned to DEAD_LETTER
    and is never retried indefinitely.
    """
    job_svc = JobService(db)

    # 1. Create a job at max attempts limit
    job = job_svc.enqueue_job(
        job_type=JobType.NOTIFICATION_RETRY,
        payload={"limit": 5},
        idempotency_key=f"dead_letter_test_{uuid.uuid4().hex[:6]}",
    )
    job.status = JobStatus.RUNNING
    job.locked_by = "worker-failing-node"
    job.locked_until = datetime.now(UTC) - timedelta(minutes=15)
    job.attempt_count = job.max_attempts  # E.g. 5
    db.commit()

    # 2. Reclaim evaluates max_attempts exceeded
    job_svc.reclaim_stale_jobs()

    db.refresh(job)
    assert job.status == JobStatus.DEAD_LETTER
    assert job.error_category == "STALE_LEASE_EXHAUSTED"
    assert job.locked_by is None
    assert job.locked_until is None

    # 3. Verify queue claiming ignores dead-letter jobs
    claimed = job_svc.claim_jobs(worker_id="worker-new", limit=10, lease_seconds=60)
    assert job.id not in [j.id for j in claimed]


def test_admin_rbac_and_safe_manual_job_replay(client: TestClient, db: Session):
    """
    Verify that:
    1. Unauthorized (CLIENT or unauthenticated) callers cannot trigger job execution.
    2. Admin operators can re-trigger a failed or dead-letter job via the official endpoint.
    3. The replay executes through the same idempotent handler without bypassing domain invariants.
    """
    # 1. Setup users
    client_uid, client_headers = _setup_user(client, db, f"client_{uuid.uuid4().hex[:6]}@test.com", role=UserRole.CLIENT)
    admin_uid, admin_headers = _setup_user(client, db, f"admin_{uuid.uuid4().hex[:6]}@test.com", role=UserRole.ADMIN)

    # 2. Create a dead-letter maintenance job
    job_svc = JobService(db)
    job = job_svc.enqueue_job(
        job_type=JobType.COMMERCIAL_RECONCILIATION,
        payload={"lookback_days": 1},
        idempotency_key=f"admin_replay_test_{uuid.uuid4().hex[:6]}",
    )
    job.status = JobStatus.DEAD_LETTER
    job.error_category = "SIMULATED_FAIL"
    job.last_error = "Operator manual intervention required"
    db.commit()

    # 3. Unauthenticated request rejected
    res_anon = client.post(f"/api/v1/admin/jobs/{job.id}/execute")
    assert res_anon.status_code in (401, 403)

    # 4. Non-admin (Client) rejected with 403 Forbidden
    res_client = client.post(f"/api/v1/admin/jobs/{job.id}/execute", headers=client_headers)
    assert res_client.status_code == 403

    # 5. Admin executes replay safely
    res_admin = client.post(f"/api/v1/admin/jobs/{job.id}/execute", headers=admin_headers)
    assert res_admin.status_code == 200
    data = res_admin.json()
    assert data["status"] == JobStatus.SUCCEEDED.value
    assert data["id"] == str(job.id)

    db.refresh(job)
    assert job.status == JobStatus.SUCCEEDED
