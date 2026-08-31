import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationType
from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus


def _make_stripe_sig(
    payload: dict, secret: str = "whsec_test_secret_123", timestamp: int | None = None
) -> tuple[str, bytes]:
    raw_body = json.dumps(payload).encode("utf-8")
    if timestamp is None:
        timestamp = int(datetime.now(UTC).timestamp())
    signed_payload = f"{timestamp}.".encode() + raw_body
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}", raw_body


def _setup_user(
    client: TestClient,
    email: str,
    password: str = "Pass123!",
    role: str = "CLIENT",
    full_name: str = "Test User",
) -> tuple[str, dict[str, str]]:
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": role,
            "full_name": full_name,
        },
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return str(user_id), {"Authorization": f"Bearer {token}"}


# ============================================================================
# 1. CASE & TASK DOMAIN EVENT NOTIFICATIONS
# ============================================================================


def test_case_and_task_event_notifications(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "notif_owner@test.com", role="CLIENT")
    member_id, h_member = _setup_user(client, "notif_member@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(client, "notif_lawyer@test.com", role="LAWYER")

    # 1. Create Case -> CASE_CREATED notification for owner
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "IP Dispute Case", "description": "IP Infringement"},
        headers=h_owner,
    )
    assert res_case.status_code == 201
    case_id = res_case.json()["id"]

    res_notifs_owner = client.get("/api/v1/notifications", headers=h_owner)
    assert res_notifs_owner.status_code == 200
    items = res_notifs_owner.json()["items"]
    assert len(items) >= 1
    assert items[0]["type"] == NotificationType.CASE_CREATED.value

    # 2. Add Member -> PARTICIPANT_ADDED notification for member
    res_add_m = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": member_id, "participant_role": "VIEWER"},
        headers=h_owner,
    )
    assert res_add_m.status_code == 200

    res_notifs_m = client.get("/api/v1/notifications", headers=h_member)
    assert res_notifs_m.status_code == 200
    assert any(
        n["type"] == NotificationType.PARTICIPANT_ADDED.value
        for n in res_notifs_m.json()["items"]
    )

    # 3. Add Lawyer -> LAWYER_ASSIGNED notification for lawyer
    res_add_l = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    assert res_add_l.status_code == 200

    # 4. Update Case Status -> CASE_STATUS_CHANGED notification for member (not updating actor)
    res_up = client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "IN_PROGRESS"},
        headers=h_owner,
    )
    assert res_up.status_code == 200

    res_notifs_m2 = client.get("/api/v1/notifications", headers=h_member)
    assert any(
        n["type"] == NotificationType.CASE_STATUS_CHANGED.value
        for n in res_notifs_m2.json()["items"]
    )

    # 5. Create Task with Assignee -> TASK_ASSIGNED notification for member
    due = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    res_task = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={
            "title": "Draft Initial Notice",
            "owner_user_id": member_id,
            "due_date": due,
            "priority": "HIGH",
        },
        headers=h_owner,
    )
    assert res_task.status_code == 201
    task_id = res_task.json()["id"]

    res_notifs_m3 = client.get("/api/v1/notifications", headers=h_member)
    assert any(
        n["type"] == NotificationType.TASK_ASSIGNED.value and n["task_id"] == task_id
        for n in res_notifs_m3.json()["items"]
    )

    # 6. Complete Task -> TASK_COMPLETED notification for owner (task creator)
    res_task_done = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"status": "COMPLETED"},
        headers=h_lawyer,
    )
    assert res_task_done.status_code == 200

    res_notifs_owner2 = client.get("/api/v1/notifications", headers=h_owner)
    assert any(
        n["type"] == NotificationType.TASK_COMPLETED.value
        for n in res_notifs_owner2.json()["items"]
    )


# ============================================================================
# 2. CONSULTATION & PAYMENT DOMAIN EVENT NOTIFICATIONS
# ============================================================================


def test_consultation_and_payment_notifications(client: TestClient, db: Session):
    _client_id, h_client = _setup_user(client, "notif_c_client@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(client, "notif_c_lawyer@test.com", role="LAWYER")

    # Verify lawyer
    lp = (
        db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    )
    assert lp is not None
    lp.consultation_fee = 3000.0
    ver = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number="NOTIF/101/2021",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()

    # 1. Request Consultation -> CONSULTATION_REQUESTED for lawyer
    fut = (datetime.now(UTC) + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_req = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut, "duration_minutes": 45},
        headers=h_client,
    )
    assert res_req.status_code == 201
    c_id = res_req.json()["id"]

    res_l_notifs = client.get("/api/v1/notifications", headers=h_lawyer)
    assert any(
        n["type"] == NotificationType.CONSULTATION_REQUESTED.value
        and n["consultation_id"] == c_id
        for n in res_l_notifs.json()["items"]
    )

    # 2. Lawyer Accepts Consultation -> CONSULTATION_ACCEPTED for client
    res_acc = client.post(f"/api/v1/consultations/{c_id}/accept", headers=h_lawyer)
    assert res_acc.status_code == 200

    res_cl_notifs = client.get("/api/v1/notifications", headers=h_client)
    assert any(
        n["type"] == NotificationType.CONSULTATION_ACCEPTED.value
        for n in res_cl_notifs.json()["items"]
    )

    # 3. Create Payment -> PAYMENT_CREATED for client
    res_pay = client.post(f"/api/v1/consultations/{c_id}/payments", headers=h_client)
    assert res_pay.status_code == 201
    payment_id = res_pay.json()["payment_id"]

    res_cl_notifs2 = client.get("/api/v1/notifications", headers=h_client)
    assert any(
        n["type"] == NotificationType.PAYMENT_CREATED.value
        for n in res_cl_notifs2.json()["items"]
    )

    # 4. Webhook Payment Success -> PAYMENT_SUCCEEDED for both client and lawyer
    payload = {
        "id": "evt_notif_1",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": f"pi_mock_{payment_id}"}},
    }
    sig_wh, raw_wh = _make_stripe_sig(payload)
    res_wh = client.post(
        "/api/v1/payments/webhooks/stripe",
        headers={"Stripe-Signature": sig_wh, "Content-Type": "application/json"},
        content=raw_wh,
    )
    assert res_wh.status_code == 200

    res_cl_notifs3 = client.get("/api/v1/notifications", headers=h_client)
    assert any(
        n["type"] == NotificationType.PAYMENT_SUCCEEDED.value
        for n in res_cl_notifs3.json()["items"]
    )

    res_l_notifs2 = client.get("/api/v1/notifications", headers=h_lawyer)
    assert any(
        n["type"] == NotificationType.PAYMENT_SUCCEEDED.value
        for n in res_l_notifs2.json()["items"]
    )

    # 5. Lawyer Confirms/Schedules -> CONSULTATION_SCHEDULED for client and lawyer
    res_conf = client.post(f"/api/v1/consultations/{c_id}/confirm", headers=h_lawyer)
    assert res_conf.status_code == 200

    res_cl_notifs4 = client.get("/api/v1/notifications", headers=h_client)
    assert any(
        n["type"] == NotificationType.CONSULTATION_SCHEDULED.value
        for n in res_cl_notifs4.json()["items"]
    )

    # 6. Complete Consultation -> CONSULTATION_COMPLETED for client
    res_comp = client.post(f"/api/v1/consultations/{c_id}/complete", headers=h_lawyer)
    assert res_comp.status_code == 200

    res_cl_notifs5 = client.get("/api/v1/notifications", headers=h_client)
    assert any(
        n["type"] == NotificationType.CONSULTATION_COMPLETED.value
        for n in res_cl_notifs5.json()["items"]
    )


# ============================================================================
# 3. IN-APP NOTIFICATION API, PAGINATION & READ STATE WORKFLOW
# ============================================================================


def test_notification_read_states_and_pagination(client: TestClient, db: Session):
    user_id, h_user = _setup_user(client, "notif_ops@test.com", role="CLIENT")

    # Manually populate multiple notifications for pagination and read state tests
    for i in range(5):
        notif = Notification(
            user_id=UUID(user_id),
            type=NotificationType.CASE_STATUS_CHANGED,
            title=f"Notification Title {i}",
            message=f"Detailed message description number {i}",
            is_read=False,
        )
        db.add(notif)
    db.commit()

    # 1. Unread count check
    res_cnt = client.get("/api/v1/notifications/unread-count", headers=h_user)
    assert res_cnt.status_code == 200
    assert res_cnt.json()["unread_count"] == 5

    # 2. Pagination check
    res_page = client.get("/api/v1/notifications?skip=0&limit=2", headers=h_user)
    assert res_page.status_code == 200
    p_data = res_page.json()
    assert p_data["total"] == 5
    assert len(p_data["items"]) == 2
    first_id = p_data["items"][0]["id"]

    # 3. Mark single notification as read
    res_read = client.post(f"/api/v1/notifications/{first_id}/read", headers=h_user)
    assert res_read.status_code == 200
    assert res_read.json()["is_read"] is True
    assert res_read.json()["read_at"] is not None

    # Idempotent re-mark as read
    assert (
        client.post(
            f"/api/v1/notifications/{first_id}/read", headers=h_user
        ).status_code
        == 200
    )

    # Verify unread count is now 4
    assert (
        client.get("/api/v1/notifications/unread-count", headers=h_user).json()[
            "unread_count"
        ]
        == 4
    )

    # 4. Mark single notification back to unread
    res_unread = client.post(f"/api/v1/notifications/{first_id}/unread", headers=h_user)
    assert res_unread.status_code == 200
    assert res_unread.json()["is_read"] is False
    assert res_unread.json()["read_at"] is None

    # 5. Mark all as read
    res_all = client.post("/api/v1/notifications/read-all", headers=h_user)
    assert res_all.status_code == 200
    assert res_all.json()["updated_count"] == 5

    # Verify unread count is 0
    assert (
        client.get("/api/v1/notifications/unread-count", headers=h_user).json()[
            "unread_count"
        ]
        == 0
    )

    # 6. Soft delete single notification
    res_del = client.delete(f"/api/v1/notifications/{first_id}", headers=h_user)
    assert res_del.status_code == 204

    # Deleted notification no longer in list
    res_after_del = client.get("/api/v1/notifications", headers=h_user)
    assert res_after_del.json()["total"] == 4


# ============================================================================
# 4. SECURITY & BOLA/IDOR MATRIX
# ============================================================================


def test_notification_security_and_bola_matrix(client: TestClient, db: Session):
    user_a_id, h_user_a = _setup_user(client, "notif_sec_a@test.com", role="CLIENT")
    _user_b_id, h_user_b = _setup_user(client, "notif_sec_b@test.com", role="CLIENT")

    # Create notification for User A
    notif_a = Notification(
        user_id=UUID(user_a_id),
        type=NotificationType.PAYMENT_SUCCEEDED,
        title="Private Financial Alert",
        message="Confidential payment confirmation details",
        is_read=False,
    )
    db.add(notif_a)
    db.commit()
    db.refresh(notif_a)
    notif_id = str(notif_a.id)

    # 1. User A -> Own Notification: ALLOW (200)
    res_a_read = client.post(f"/api/v1/notifications/{notif_id}/read", headers=h_user_a)
    assert res_a_read.status_code == 200

    # 2. User B -> User A's Notification read: DENY (404)
    res_b_read = client.post(f"/api/v1/notifications/{notif_id}/read", headers=h_user_b)
    assert res_b_read.status_code == 404

    # 3. User B -> User A's Notification unread: DENY (404)
    res_b_unread = client.post(
        f"/api/v1/notifications/{notif_id}/unread", headers=h_user_b
    )
    assert res_b_unread.status_code == 404

    # 4. User B -> User A's Notification delete: DENY (404)
    res_b_del = client.delete(f"/api/v1/notifications/{notif_id}", headers=h_user_b)
    assert res_b_del.status_code == 404

    # 5. User B listing notifications does not show User A's notifications
    res_b_list = client.get("/api/v1/notifications", headers=h_user_b)
    assert res_b_list.status_code == 200
    assert res_b_list.json()["total"] == 0
