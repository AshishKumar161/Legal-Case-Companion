import time

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.job import JobType
from app.services.job_service import JobService


def _setup_bench_user(client: TestClient, email: str, role: str = "CLIENT"):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": role, "full_name": "Perf User"},
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_performance_and_latency_benchmark(client: TestClient, db: Session):
    """Evaluates latency benchmarks for core endpoints and background job claiming operations."""
    _u_id, headers = _setup_bench_user(client, "perf_bench@test.com", role="CLIENT")

    # 1. Benchmark Case Creation & Workspace Aggregation Latency
    case_workspace_times = []

    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Performance Benchmark Case", "description": "Testing latency"},
        headers=headers,
    )
    assert res_case.status_code == 201
    case_id = res_case.json()["id"]

    for _ in range(10):
        t0 = time.perf_counter()
        res_ws = client.get(f"/api/v1/cases/{case_id}/workspace", headers=headers)
        t_ws = (time.perf_counter() - t0) * 1000.0
        assert res_ws.status_code == 200
        case_workspace_times.append(t_ws)

    avg_ws_latency = sum(case_workspace_times) / len(case_workspace_times)
    assert avg_ws_latency < 500.0  # Workspace aggregation must complete in < 500ms

    # 2. Benchmark Background Job Queue Claiming Latency
    job_svc = JobService(db)
    for i in range(20):
        job_svc.enqueue_job(
            job_type=JobType.DOCUMENT_INDEXING,
            payload={"document_id": str(generate_uuid7())},
            idempotency_key=f"perf_job_key_{i}",
        )

    t0 = time.perf_counter()
    claimed = job_svc.claim_jobs(worker_id="perf-worker", limit=20)
    t_claim = (time.perf_counter() - t0) * 1000.0
    assert len(claimed) == 20
    assert t_claim < 200.0  # Claiming batch of 20 jobs must complete in < 200ms

    # 3. Benchmark Public/Health Latency
    health_times = []
    for _ in range(20):
        t0 = time.perf_counter()
        res_h = client.get("/health/live")
        t_h = (time.perf_counter() - t0) * 1000.0
        assert res_h.status_code == 200
        health_times.append(t_h)

    avg_health_latency = sum(health_times) / len(health_times)
    assert avg_health_latency < 50.0  # Liveness probe must complete in < 50ms
