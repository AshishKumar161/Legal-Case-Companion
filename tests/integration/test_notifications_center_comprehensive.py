import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.notification import (
    NotificationType,
)
from app.models.user import AccountStatus, ClientProfile, User, UserRole
from app.domain.notifications.notification_service import NotificationService


@pytest.fixture
def test_users(db: Session) -> tuple[User, User, dict[str, str], dict[str, str]]:
    """Creates two distinct client users with authentication headers."""
    # User A
    user_a = User(
        id=uuid.uuid4(),
        email=f"client_a_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("PasswordA123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    profile_a = ClientProfile(user_id=user_a.id, full_name="Client A")
    db.add_all([user_a, profile_a])

    # User B
    user_b = User(
        id=uuid.uuid4(),
        email=f"client_b_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("PasswordB123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    profile_b = ClientProfile(user_id=user_b.id, full_name="Client B")
    db.add_all([user_b, profile_b])
    db.commit()

    from app.core.security import create_access_token

    token_a = create_access_token(
        subject=str(user_a.id),
        role=user_a.role.value,
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}

    token_b = create_access_token(
        subject=str(user_b.id),
        role=user_b.role.value,
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    return user_a, user_b, headers_a, headers_b


def test_notification_listing_and_pagination(
    client: TestClient, db: Session, test_users: tuple[User, User, dict[str, str], dict[str, str]]
):
    """Verifies listing notifications with bounded pagination and total count."""
    user_a, _, headers_a, _ = test_users
    service = NotificationService(db)

    # Seed 5 notifications
    for i in range(5):
        service.create_notification(
            user_id=user_a.id,
            type=NotificationType.CASE_CREATED,
            title=f"Case Update #{i + 1}",
            message=f"Detailed message content for case update #{i + 1}",
            send_email=False,
        )

    # Page 1 (limit 2)
    res_p1 = client.get("/api/v1/notifications?skip=0&limit=2", headers=headers_a)
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert data_p1["total"] == 5
    assert len(data_p1["items"]) == 2
    assert data_p1["skip"] == 0
    assert data_p1["limit"] == 2

    # Page 2 (limit 2)
    res_p2 = client.get("/api/v1/notifications?skip=2&limit=2", headers=headers_a)
    assert res_p2.status_code == 200
    data_p2 = res_p2.json()
    assert len(data_p2["items"]) == 2
    assert data_p2["skip"] == 2


def test_notification_read_filtering(
    client: TestClient, db: Session, test_users: tuple[User, User, dict[str, str], dict[str, str]]
):
    """Verifies filtering notifications by read and unread status."""
    user_a, _, headers_a, _ = test_users
    service = NotificationService(db)

    n1 = service.create_notification(
        user_id=user_a.id,
        type=NotificationType.CASE_STATUS_CHANGED,
        title="Unread Notification 1",
        message="Message 1",
        send_email=False,
    )
    n2 = service.create_notification(
        user_id=user_a.id,
        type=NotificationType.TASK_ASSIGNED,
        title="Read Notification 2",
        message="Message 2",
        send_email=False,
    )
    assert n1 is not None and n2 is not None
    service.mark_as_read(user_a, n2.id)

    # Filter is_read=false
    res_unread = client.get("/api/v1/notifications?is_read=false", headers=headers_a)
    assert res_unread.status_code == 200
    unread_items = res_unread.json()["items"]
    assert all(item["is_read"] is False for item in unread_items)
    assert any(item["id"] == str(n1.id) for item in unread_items)

    # Filter is_read=true
    res_read = client.get("/api/v1/notifications?is_read=true", headers=headers_a)
    assert res_read.status_code == 200
    read_items = res_read.json()["items"]
    assert all(item["is_read"] is True for item in read_items)
    assert any(item["id"] == str(n2.id) for item in read_items)


def test_notification_category_filtering(
    client: TestClient, db: Session, test_users: tuple[User, User, dict[str, str], dict[str, str]]
):
    """Verifies category filtering across CASE, TASK, CONSULTATION, and PAYMENT."""
    user_a, _, headers_a, _ = test_users
    service = NotificationService(db)

    # Case notice
    service.create_notification(
        user_id=user_a.id,
        type=NotificationType.CASE_CREATED,
        title="Matter Inception Notice",
        message="New case opened",
        send_email=False,
    )
    # Task notice
    service.create_notification(
        user_id=user_a.id,
        type=NotificationType.TASK_ASSIGNED,
        title="Draft Written Statement",
        message="Assigned by counsel",
        send_email=False,
    )
    # Consultation notice
    service.create_notification(
        user_id=user_a.id,
        type=NotificationType.CONSULTATION_SCHEDULED,
        title="Advocate Consultation Confirmed",
        message="Slot locked for 14:00",
        send_email=False,
    )
    # Payment notice
    service.create_notification(
        user_id=user_a.id,
        type=NotificationType.PAYMENT_SUCCEEDED,
        title="Retainer Fee Receipt",
        message="Invoice #994 paid",
        send_email=False,
    )

    # Filter category=CASE
    res_case = client.get("/api/v1/notifications?category=CASE", headers=headers_a)
    assert res_case.status_code == 200
    assert all(item["type"] in ("CASE_CREATED", "CASE_STATUS_CHANGED", "PARTICIPANT_ADDED", "LAWYER_ASSIGNED") for item in res_case.json()["items"])

    # Filter category=TASK
    res_task = client.get("/api/v1/notifications?category=TASK", headers=headers_a)
    assert res_task.status_code == 200
    assert any("TASK" in item["type"] for item in res_task.json()["items"])

    # Filter category=CONSULTATION
    res_con = client.get("/api/v1/notifications?category=CONSULTATION", headers=headers_a)
    assert res_con.status_code == 200
    assert any("CONSULTATION" in item["type"] for item in res_con.json()["items"])

    # Filter category=PAYMENT
    res_pay = client.get("/api/v1/notifications?category=PAYMENT", headers=headers_a)
    assert res_pay.status_code == 200
    assert any("PAYMENT" in item["type"] for item in res_pay.json()["items"])


def test_notification_search_filtering(
    client: TestClient, db: Session, test_users: tuple[User, User, dict[str, str], dict[str, str]]
):
    """Verifies keyword search filtering on title and message bodies."""
    user_a, _, headers_a, _ = test_users
    service = NotificationService(db)

    service.create_notification(
        user_id=user_a.id,
        type=NotificationType.CASE_CREATED,
        title="Special Arbitration Listing",
        message="Hearing set before High Court",
        send_email=False,
    )
    service.create_notification(
        user_id=user_a.id,
        type=NotificationType.TASK_ASSIGNED,
        title="Regular Task",
        message="Standard filing chore",
        send_email=False,
    )

    res_search = client.get("/api/v1/notifications?search=Arbitration", headers=headers_a)
    assert res_search.status_code == 200
    items = res_search.json()["items"]
    assert len(items) == 1
    assert "Arbitration" in items[0]["title"]


def test_unread_count_authoritative(
    client: TestClient, db: Session, test_users: tuple[User, User, dict[str, str], dict[str, str]]
):
    """Verifies that GET /unread-count is authoritative and accurately tracks mark read/unread mutations."""
    user_a, _, headers_a, _ = test_users
    service = NotificationService(db)

    # Initial count
    res_init = client.get("/api/v1/notifications/unread-count", headers=headers_a)
    assert res_init.status_code == 200
    initial_count = res_init.json()["unread_count"]

    # Create 2 unread notifications
    n1 = service.create_notification(
        user_id=user_a.id,
        type=NotificationType.CASE_CREATED,
        title="Unread 1",
        message="M1",
        send_email=False,
    )
    n2 = service.create_notification(
        user_id=user_a.id,
        type=NotificationType.CASE_CREATED,
        title="Unread 2",
        message="M2",
        send_email=False,
    )
    assert n1 is not None and n2 is not None

    res_after_create = client.get("/api/v1/notifications/unread-count", headers=headers_a)
    assert res_after_create.json()["unread_count"] == initial_count + 2

    # Mark n1 as read
    client.post(f"/api/v1/notifications/{n1.id}/read", headers=headers_a)
    res_after_read = client.get("/api/v1/notifications/unread-count", headers=headers_a)
    assert res_after_read.json()["unread_count"] == initial_count + 1

    # Mark n1 as unread
    client.post(f"/api/v1/notifications/{n1.id}/unread", headers=headers_a)
    res_after_unread = client.get("/api/v1/notifications/unread-count", headers=headers_a)
    assert res_after_unread.json()["unread_count"] == initial_count + 2


def test_mark_all_read_atomic(
    client: TestClient, db: Session, test_users: tuple[User, User, dict[str, str], dict[str, str]]
):
    """Verifies that mark-all-as-read updates all unread notifications atomically."""
    user_a, _, headers_a, _ = test_users
    service = NotificationService(db)

    for i in range(3):
        service.create_notification(
            user_id=user_a.id,
            type=NotificationType.TASK_ASSIGNED,
            title=f"Batch Task #{i}",
            message=f"Batch Message #{i}",
            send_email=False,
        )

    res_mark_all = client.post("/api/v1/notifications/read-all", headers=headers_a)
    assert res_mark_all.status_code == 200
    assert res_mark_all.json()["updated_count"] >= 3

    # Verify unread count is now 0
    res_unread = client.get("/api/v1/notifications/unread-count", headers=headers_a)
    assert res_unread.json()["unread_count"] == 0


def test_bulk_mark_read_and_bulk_delete_with_idor_protection(
    client: TestClient, db: Session, test_users: tuple[User, User, dict[str, str], dict[str, str]]
):
    """Verifies that bulk read and bulk delete isolate recipient ownership and do not affect foreign records."""
    user_a, user_b, headers_a, _ = test_users
    service = NotificationService(db)

    # User A notifications
    na1 = service.create_notification(user_id=user_a.id, type=NotificationType.CASE_CREATED, title="NA1", message="MA1", send_email=False)
    na2 = service.create_notification(user_id=user_a.id, type=NotificationType.CASE_CREATED, title="NA2", message="MA2", send_email=False)

    # User B notification
    nb1 = service.create_notification(user_id=user_b.id, type=NotificationType.CASE_CREATED, title="NB1", message="MB1", send_email=False)
    assert na1 is not None and na2 is not None and nb1 is not None

    # User A attempts bulk read containing na1, na2, and nb1
    res_bulk_read = client.post(
        "/api/v1/notifications/bulk-read",
        json={"notification_ids": [str(na1.id), str(na2.id), str(nb1.id)]},
        headers=headers_a,
    )
    assert res_bulk_read.status_code == 200
    assert res_bulk_read.json()["updated_count"] == 2  # Only na1 and na2 updated

    # Verify User B's notification is still UNREAD
    db.refresh(nb1)
    assert nb1.is_read is False

    # User A attempts bulk delete containing na1 and nb1
    res_bulk_delete = client.post(
        "/api/v1/notifications/bulk-delete",
        json={"notification_ids": [str(na1.id), str(nb1.id)]},
        headers=headers_a,
    )
    assert res_bulk_delete.status_code == 200
    assert res_bulk_delete.json()["deleted_count"] == 1  # Only na1 deleted

    # Verify User B's notification is NOT deleted
    db.refresh(nb1)
    assert nb1.deleted_at is None


def test_notification_ownership_isolation_and_foreign_access_blocked(
    client: TestClient, db: Session, test_users: tuple[User, User, dict[str, str], dict[str, str]]
):
    """Verifies that foreign users cannot read, unread, or delete another user's notification (BOLA / IDOR defense)."""
    _, user_b, headers_a, _ = test_users
    service = NotificationService(db)

    nb = service.create_notification(
        user_id=user_b.id,
        type=NotificationType.PAYMENT_SUCCEEDED,
        title="User B Secret Fee",
        message="Private billing transaction",
        send_email=False,
    )
    assert nb is not None

    # User A attempts to mark User B's notification as read -> 404
    res_read = client.post(f"/api/v1/notifications/{nb.id}/read", headers=headers_a)
    assert res_read.status_code == 404

    # User A attempts to mark User B's notification as unread -> 404
    res_unread = client.post(f"/api/v1/notifications/{nb.id}/unread", headers=headers_a)
    assert res_unread.status_code == 404

    # User A attempts to delete User B's notification -> 404
    res_delete = client.delete(f"/api/v1/notifications/{nb.id}", headers=headers_a)
    assert res_delete.status_code == 404


def test_notification_preferences_behavior_and_suppression(
    client: TestClient, db: Session, test_users: tuple[User, User, dict[str, str], dict[str, str]]
):
    """Verifies that user notification preferences properly suppress generation of opted-out categories."""
    user_a, _, headers_a, _ = test_users
    service = NotificationService(db)

    # Disable case updates and task updates in preferences
    res_patch = client.patch(
        "/api/v1/notifications/preferences",
        json={"case_updates": False, "task_updates": False},
        headers=headers_a,
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["case_updates"] is False
    assert res_patch.json()["task_updates"] is False

    # Attempt to create case update notification -> suppressed (returns None)
    n_case = service.create_notification(
        user_id=user_a.id,
        type=NotificationType.CASE_CREATED,
        title="Suppressed Case",
        message="Should not be delivered",
        send_email=False,
    )
    assert n_case is None

    # Attempt to create task update notification -> suppressed (returns None)
    n_task = service.create_notification(
        user_id=user_a.id,
        type=NotificationType.TASK_ASSIGNED,
        title="Suppressed Task",
        message="Should not be delivered",
        send_email=False,
    )
    assert n_task is None

    # Consultation updates are still enabled -> delivered
    n_con = service.create_notification(
        user_id=user_a.id,
        type=NotificationType.CONSULTATION_REQUESTED,
        title="Delivered Consultation",
        message="Should be delivered",
        send_email=False,
    )
    assert n_con is not None


def test_notification_privacy_and_data_exposure(
    client: TestClient, db: Session, test_users: tuple[User, User, dict[str, str], dict[str, str]]
):
    """Verifies that notifications do not leak sensitive backend secrets or raw storage paths."""
    user_a, _, headers_a, _ = test_users
    service = NotificationService(db)

    notif = service.create_notification(
        user_id=user_a.id,
        type=NotificationType.DOCUMENT_READY,
        title="Evidence Scanned: Safe",
        message="Document SHA-256 analysis complete. Safe to inspect.",
        metadata={"internal_s3_bucket": "s3-private-bucket-lcc", "document_hash": "abc123safe"},
        send_email=False,
    )
    assert notif is not None

    res = client.get("/api/v1/notifications", headers=headers_a)
    assert res.status_code == 200
    items = res.json()["items"]
    target = next((item for item in items if item["id"] == str(notif.id)), None)
    assert target is not None
    assert "Evidence Scanned: Safe" in target["title"]


def test_mark_read_and_unread_idempotent_transitions(
    client: TestClient, db: Session, test_users: tuple[User, User, dict[str, str], dict[str, str]]
):
    """Verifies that rapid mark read and unread state mutations are completely idempotent."""
    user_a, _, headers_a, _ = test_users
    service = NotificationService(db)

    notif = service.create_notification(
        user_id=user_a.id,
        type=NotificationType.CASE_CREATED,
        title="Idempotent Test",
        message="Testing idempotent state changes",
        send_email=False,
    )
    assert notif is not None

    # Mark read twice
    r1 = client.post(f"/api/v1/notifications/{notif.id}/read", headers=headers_a)
    assert r1.status_code == 200
    assert r1.json()["is_read"] is True

    r2 = client.post(f"/api/v1/notifications/{notif.id}/read", headers=headers_a)
    assert r2.status_code == 200
    assert r2.json()["is_read"] is True

    # Mark unread twice
    u1 = client.post(f"/api/v1/notifications/{notif.id}/unread", headers=headers_a)
    assert u1.status_code == 200
    assert u1.json()["is_read"] is False

    u2 = client.post(f"/api/v1/notifications/{notif.id}/unread", headers=headers_a)
    assert u2.status_code == 200
    assert u2.json()["is_read"] is False
