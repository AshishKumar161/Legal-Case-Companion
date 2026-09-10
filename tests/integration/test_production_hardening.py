import signal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User, UserRole
from app.domain.jobs.job_scheduler import JobScheduler


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "dummy-test-key"
    yield
    settings.OPENAI_API_KEY = original_key


def _setup_user(client: TestClient, email: str, role: str = "CLIENT"):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": role, "full_name": "Hardening User"},
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_root_health_and_readiness_probes(client: TestClient):
    """Verifies that root-level and versioned health/readiness endpoints respond correctly for load balancers."""
    # 1. Root liveness
    res_root_live = client.get("/health/live")
    assert res_root_live.status_code == 200
    assert res_root_live.json()["status"] == "alive"

    res_root_health = client.get("/health")
    assert res_root_health.status_code == 200
    assert res_root_health.json()["status"] == "alive"

    # 2. Root readiness
    res_root_ready = client.get("/health/ready")
    assert res_root_ready.status_code == 200
    assert res_root_ready.json()["status"] == "ready"
    assert res_root_ready.json()["database"] == "connected"

    res_ready_alias = client.get("/ready")
    assert res_ready_alias.status_code == 200

    # 3. Versioned probes (/api/v1/health/*)
    res_v1_live = client.get("/api/v1/health/live")
    assert res_v1_live.status_code == 200
    res_v1_ready = client.get("/api/v1/health/ready")
    assert res_v1_ready.status_code == 200


def test_security_headers_compliance(client: TestClient):
    """Verifies that all required production security headers are set on HTTP responses."""
    res = client.get("/health")
    assert res.status_code == 200
    headers = res.headers

    assert "Strict-Transport-Security" in headers
    assert "max-age=31536000" in headers["Strict-Transport-Security"]
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert "default-src 'none'" in headers.get("Content-Security-Policy", "")
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation=()" in headers.get("Permissions-Policy", "")


def test_request_id_correlation_propagation(client: TestClient):
    """Verifies request correlation ID preservation and injection into errors and responses."""
    custom_req_id = "test-corr-id-12345"
    res = client.get("/health", headers={"X-Request-ID": custom_req_id})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == custom_req_id

    # On error response
    res_err = client.get("/api/v1/cases/01912345-0000-7000-8000-000000000000", headers={"X-Request-ID": custom_req_id})
    assert res_err.status_code in (401, 404)
    assert res_err.headers.get("X-Request-ID") == custom_req_id
    err_body = res_err.json()
    assert "error" in err_body
    assert err_body["error"]["request_id"] == custom_req_id


def test_operational_metrics_collector_and_admin_endpoint(client: TestClient, db: Session):
    """Verifies that metrics collector aggregates HTTP activity and only admins can inspect metrics."""
    _u_admin_id, h_admin = _setup_user(client, "admin_metrics@test.com", role="CLIENT")
    admin_user = db.query(User).filter(User.email == "admin_metrics@test.com").first()
    admin_user.role = UserRole.ADMIN
    db.commit()

    _u_client_id, h_client = _setup_user(client, "client_metrics@test.com", role="CLIENT")

    # Generate some HTTP traffic
    client.get("/health")
    client.get("/health/ready")

    # Non-admin forbidden
    res_client = client.get("/api/v1/admin/metrics", headers=h_client)
    assert res_client.status_code == 403

    # Admin access
    res_admin = client.get("/api/v1/admin/metrics", headers=h_admin)
    assert res_admin.status_code == 200
    data = res_admin.json()
    assert "uptime_seconds" in data
    assert "total_http_requests" in data
    assert data["total_http_requests"] >= 2
    assert "latency_ms" in data
    assert "status_distribution" in data


def test_worker_and_scheduler_lifecycle(client: TestClient, db: Session):
    """Verifies standalone worker and scheduler components execute batches cleanly."""
    from app.scheduler import handle_shutdown as scheduler_shutdown
    from app.worker import handle_shutdown as worker_shutdown

    # Test signal handlers
    worker_shutdown(signal.SIGTERM, None)
    scheduler_shutdown(signal.SIGINT, None)

    # Test scheduler trigger and worker batch execution
    scheduler = JobScheduler(worker_id="test-hardening-scheduler")
    scan_results = scheduler.trigger_periodic_scans(db)
    assert "deadline_scan_job_id" in scan_results
    assert "task_scan_job_id" in scan_results

    processed = scheduler.run_worker_batch(db, limit=10)
    assert processed >= 2
