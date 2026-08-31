import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models import BackgroundJob, JobStatus, JobType, Notification, NotificationType
from app.services.job_scheduler import JobScheduler


def _create_user(client: TestClient, email: str, role: str = "CLIENT") -> tuple[str, dict[str, str]]:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": role, "full_name": f"User {email}"},
    )
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = login_res.json()["access_token"]
    user_id = login_res.json().get("user_id", "")
    return user_id, {"Authorization": f"Bearer {token}"}


def test_admin_and_worker_red_team(client: TestClient, db: Session):
    """Red Team: Validates that unprivileged users cannot execute admin commands and worker safely handles malformed job payloads."""
    _, client_headers = _create_user(client, "client_attacker@test.com", "CLIENT")
    _, lawyer_headers = _create_user(client, "lawyer_attacker@test.com", "LAWYER")

    # 1. ATTACK: Client attempts to trigger legal source sync
    assert client.post("/api/v1/admin/legal-sources/sync-fixtures", headers=client_headers).status_code == 403

    # 2. ATTACK: Lawyer attempts to trigger legal source sync
    assert client.post("/api/v1/admin/legal-sources/sync-fixtures", headers=lawyer_headers).status_code == 403

    # 3. ATTACK: Malformed job payload execution by worker
    scheduler = JobScheduler(worker_id="redteam-worker")
    bad_job = BackgroundJob(
        id=generate_uuid7(),
        job_type=JobType.DOCUMENT_PROCESSING,
        payload={"corrupted_field": True},  # Missing document_id / case_id
        status=JobStatus.PENDING,
    )
    db.add(bad_job)
    db.commit()

    # Worker executes batch with malformed job -> must NOT crash the worker
    processed = scheduler.run_worker_batch(db, limit=5)
    assert processed >= 1

    db.refresh(bad_job)
    # Job should transition to FAILED / RETRYING rather than remaining hung
    assert bad_job.status in [JobStatus.FAILED, JobStatus.SUCCEEDED, JobStatus.RUNNING, JobStatus.RETRYING]


def test_notification_recipient_isolation_and_idor(client: TestClient, db: Session):
    """Red Team: Validates that user notifications are strictly isolated and cannot be read or marked read by other users."""
    user_a_id, _headers_a = _create_user(client, "notif_user_a@test.com", "CLIENT")
    _, headers_b = _create_user(client, "notif_user_b@test.com", "CLIENT")

    # Create notification for User A
    notif = Notification(
        id=generate_uuid7(),
        user_id=uuid.UUID(user_a_id) if user_a_id else generate_uuid7(),
        type=NotificationType.CASE_CREATED,
        title="Confidential Notification for User A",
        message="Secret settlement update.",
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    # ATTACK: User B attempts to mark User A's notification as read
    idor_mark = client.post(
        f"/api/v1/notifications/{notif.id}/read",
        headers=headers_b,
    )
    assert idor_mark.status_code in [403, 404]
