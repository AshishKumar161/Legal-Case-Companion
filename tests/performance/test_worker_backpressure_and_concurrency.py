import time

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import JobType
from app.domain.jobs.job_scheduler import JobScheduler
from app.services.job_service import JobService


def _setup_perf_user(client: TestClient, email: str = "perf_worker@example.com") -> tuple[str, dict[str, str]]:
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "WorkerPassword123!", "role": "CLIENT", "full_name": "Worker User"},
    )
    user_id = reg_res.json()["id"]
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "WorkerPassword123!"})
    token = login_res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_worker_batch_throughput_under_backpressure(client: TestClient, db: Session):
    """Measures background job batch claiming and processing throughput under high queue backlog."""
    job_svc = JobService(db)

    # 1. Enqueue 30 background scan & reminder jobs
    for i in range(30):
        job_svc.enqueue_job(
            job_type=JobType.TASK_OVERDUE_SCAN,
            payload={},
            idempotency_key=f"perf_backpressure_job_{i}",
        )

    scheduler = JobScheduler(worker_id="perf-throughput-worker")

    # 2. Benchmark claiming and batch execution
    t0 = time.perf_counter()
    processed_count = scheduler.run_worker_batch(db, limit=30)
    batch_duration = time.perf_counter() - t0

    assert processed_count >= 10
    # 30 light scan jobs should process in < 2 seconds
    assert batch_duration < 2.0


def test_concurrent_api_requests(client: TestClient, db: Session):
    """Simulates high-throughput client requests across health, profile, and notification endpoints."""
    _, headers = _setup_perf_user(client, "perf_concurrency_user@example.com")

    statuses = []
    t0 = time.perf_counter()
    for i in range(30):
        if i % 3 == 0:
            res = client.get("/health/live")
        elif i % 3 == 1:
            res = client.get("/api/v1/profiles/me", headers=headers)
        else:
            res = client.get("/api/v1/notifications/unread-count", headers=headers)
        statuses.append(res.status_code)

    total_time = time.perf_counter() - t0
    assert all(code == 200 for code in statuses)
    assert total_time < 3.0  # 30 requests completed in < 3s (< 100ms avg)
