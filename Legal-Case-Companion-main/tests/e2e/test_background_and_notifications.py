from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.job_scheduler import JobScheduler


def test_background_worker_and_notifications_e2e(client: TestClient, db: Session):
    """E2E Test: Validates asynchronous job processing, scheduler worker loop, and notification delivery."""
    # 1. Register User
    email = "worker_notif_e2e@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "WorkerPass123!", "role": "CLIENT", "full_name": "Worker User"},
    )
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "WorkerPass123!"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Case
    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": "Background Job Case", "description": "Testing worker queues."},
    )
    _case_id = case_res.json()["id"]

    # 3. Trigger periodic scans via scheduler
    scheduler = JobScheduler(worker_id="test-e2e-worker")
    scan_results = scheduler.trigger_periodic_scans(db)
    assert "deadline_scan_job_id" in scan_results
    assert "task_scan_job_id" in scan_results

    # 4. Execute Worker Batch
    processed_count = scheduler.run_worker_batch(db, limit=10)
    assert processed_count >= 2

    # 5. Check Notifications endpoint
    notifs_res = client.get("/api/v1/notifications", headers=headers)
    assert notifs_res.status_code == 200
    items = notifs_res.json().get("items", [])
    assert isinstance(items, list)
    assert len(items) >= 1
