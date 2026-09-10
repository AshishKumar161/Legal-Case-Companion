import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


def _setup_user(
    client: TestClient,
    email: str,
    password: str = "SecurePass123!",
    role: str = "CLIENT",
    full_name: str = "Test User",
):
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
    return user_id, {"Authorization": f"Bearer {token}"}


def test_notification_recipient_isolation_and_idor_protection(client: TestClient):
    user_a_id, h_a = _setup_user(client, "notif_a@test.com", role="CLIENT")
    user_b_id, h_b = _setup_user(client, "notif_b@test.com", role="CLIENT")

    # 1. Create Case for User A -> generates CASE_CREATED for User A
    res_case_a = client.post(
        "/api/v1/cases",
        json={"title": "Case A Title", "description": "Case A Description"},
        headers=h_a,
    )
    res_case_a.json()["id"]

    # 2. Create Case for User B -> generates CASE_CREATED for User B
    res_case_b = client.post(
        "/api/v1/cases",
        json={"title": "Case B Title", "description": "Case B Description"},
        headers=h_b,
    )
    res_case_b.json()["id"]

    # 3. List Notifications: User A sees only A's notification, User B sees only B's
    items_a = client.get("/api/v1/notifications", headers=h_a).json()["items"]
    items_b = client.get("/api/v1/notifications", headers=h_b).json()["items"]

    assert len(items_a) >= 1
    assert all(n["user_id"] == user_a_id for n in items_a)
    items_a[0]["id"]

    assert len(items_b) >= 1
    assert all(n["user_id"] == user_b_id for n in items_b)
    notif_b_id = items_b[0]["id"]

    # 4. IDOR Protection: User A attempts to read/mark-read/delete User B's notification -> 404
    assert client.post(f"/api/v1/notifications/{notif_b_id}/read", headers=h_a).status_code == 404
    assert client.post(f"/api/v1/notifications/{notif_b_id}/unread", headers=h_a).status_code == 404
    assert client.delete(f"/api/v1/notifications/{notif_b_id}", headers=h_a).status_code == 404

    # 5. Non-existent UUID -> 404
    fake_uuid = str(uuid.uuid4())
    assert client.post(f"/api/v1/notifications/{fake_uuid}/read", headers=h_a).status_code == 404
    assert client.delete(f"/api/v1/notifications/{fake_uuid}", headers=h_a).status_code == 404


def test_unread_counts_and_mark_read_idempotency(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "unread_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(client, "unread_lawyer@test.com", role="LAWYER")

    # Initial unread count is 0
    assert client.get("/api/v1/notifications/unread-count", headers=h_owner).json()["unread_count"] == 0

    # 1. Create Case -> 1 unread notification for owner
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "IP Dispute", "description": "Patent infringement"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    count_owner = client.get("/api/v1/notifications/unread-count", headers=h_owner).json()["unread_count"]
    assert count_owner == 1

    # Lawyer unread count is unaffected
    count_lawyer = client.get("/api/v1/notifications/unread-count", headers=h_lawyer).json()["unread_count"]
    assert count_lawyer == 0

    # 2. Add Lawyer to Case -> Lawyer gets LAWYER_ASSIGNED notification
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    assert client.get("/api/v1/notifications/unread-count", headers=h_lawyer).json()["unread_count"] == 1

    # 3. Mark Owner's notification as read
    owner_notif = client.get("/api/v1/notifications", headers=h_owner).json()["items"][0]
    notif_id = owner_notif["id"]

    res_read = client.post(f"/api/v1/notifications/{notif_id}/read", headers=h_owner)
    assert res_read.status_code == 200
    assert res_read.json()["is_read"] is True
    assert res_read.json()["read_at"] is not None
    first_read_at = res_read.json()["read_at"]

    # Owner unread count becomes 0
    assert client.get("/api/v1/notifications/unread-count", headers=h_owner).json()["unread_count"] == 0

    # 4. Idempotency: Repeat mark_as_read -> Returns 200 without error
    res_read_repeat = client.post(f"/api/v1/notifications/{notif_id}/read", headers=h_owner)
    assert res_read_repeat.status_code == 200
    assert res_read_repeat.json()["is_read"] is True
    assert res_read_repeat.json()["read_at"] == first_read_at

    # 5. Mark as unread -> Unread count increments back to 1
    res_unread = client.post(f"/api/v1/notifications/{notif_id}/unread", headers=h_owner)
    assert res_unread.status_code == 200
    assert res_unread.json()["is_read"] is False
    assert res_unread.json()["read_at"] is None
    assert client.get("/api/v1/notifications/unread-count", headers=h_owner).json()["unread_count"] == 1


def test_bulk_mark_as_read_with_recipient_isolation(client: TestClient):
    _user_a_id, h_a = _setup_user(client, "bulk_a@test.com", role="CLIENT")
    _user_b_id, h_b = _setup_user(client, "bulk_b@test.com", role="CLIENT")

    # Generate 3 cases for User A -> 3 notifications
    notif_a_ids = []
    for i in range(3):
        res = client.post("/api/v1/cases", json={"title": f"Case A{i+1}", "description": "Desc"}, headers=h_a)
        res.json()["id"]
    items_a = client.get("/api/v1/notifications", headers=h_a).json()["items"]
    notif_a_ids = [n["id"] for n in items_a]
    assert len(notif_a_ids) == 3

    # Generate 2 cases for User B -> 2 notifications
    for i in range(2):
        client.post("/api/v1/cases", json={"title": f"Case B{i+1}", "description": "Desc"}, headers=h_b)
    items_b = client.get("/api/v1/notifications", headers=h_b).json()["items"]
    notif_b_ids = [n["id"] for n in items_b]
    assert len(notif_b_ids) == 2

    # User A calls bulk-read with: [A0, A1, B0 (foreign), fake_uuid, duplicate A0]
    fake_uuid = str(uuid.uuid4())
    payload = {
        "notification_ids": [notif_a_ids[0], notif_a_ids[1], notif_b_ids[0], fake_uuid, notif_a_ids[0]]
    }
    res_bulk = client.post("/api/v1/notifications/bulk-read", json=payload, headers=h_a)
    assert res_bulk.status_code == 200
    # Exactly 2 of User A's notifications were updated
    assert res_bulk.json()["updated_count"] == 2

    # Verify User A's unread count is now 1 (A2 remains unread)
    assert client.get("/api/v1/notifications/unread-count", headers=h_a).json()["unread_count"] == 1

    # Verify User B's unread count remains 2 (foreign notification was NOT updated)
    assert client.get("/api/v1/notifications/unread-count", headers=h_b).json()["unread_count"] == 2

    # User A calls read-all -> marks remaining 1 as read
    res_read_all = client.post("/api/v1/notifications/read-all", headers=h_a)
    assert res_read_all.status_code == 200
    assert res_read_all.json()["updated_count"] == 1
    assert client.get("/api/v1/notifications/unread-count", headers=h_a).json()["unread_count"] == 0


def test_user_notification_preferences_and_audit(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "pref_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(client, "pref_lawyer@test.com", role="LAWYER")

    # 1. Fetch Default Preferences (all True)
    res_pref = client.get("/api/v1/notifications/preferences", headers=h_lawyer)
    assert res_pref.status_code == 200
    pref_data = res_pref.json()
    assert pref_data["email_enabled"] is True
    assert pref_data["case_updates"] is True
    assert pref_data["task_updates"] is True
    assert pref_data["consultation_updates"] is True

    # 2. Lawyer opts out of task_updates
    res_update = client.patch(
        "/api/v1/notifications/preferences",
        json={"task_updates": False, "email_enabled": False},
        headers=h_lawyer,
    )
    assert res_update.status_code == 200
    assert res_update.json()["task_updates"] is False
    assert res_update.json()["email_enabled"] is False

    # Verify Audit Log recorded preference change
    audit_evt = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.actor_user_id == uuid.UUID(lawyer_id),
            AuditEvent.event_type == "NOTIFICATION_PREFERENCES_UPDATED",
        )
        .first()
    )
    assert audit_evt is not None
    assert "task_updates" in audit_evt.metadata_["updated_fields"]

    # 3. Create Case and assign Lawyer
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Preference Test Case", "description": "Testing category opt-out"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    # Lawyer received LAWYER_ASSIGNED (case_updates is True)
    notifs_lawyer = client.get("/api/v1/notifications", headers=h_lawyer).json()["items"]
    assert any(n["type"] == "LAWYER_ASSIGNED" for n in notifs_lawyer)

    # 4. Create Task assigned to Lawyer -> Notification is suppressed because task_updates=False
    client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Prepare Evidence Summary", "owner_user_id": lawyer_id},
        headers=h_owner,
    )
    notifs_after_task = client.get("/api/v1/notifications", headers=h_lawyer).json()["items"]
    assert not any(n["type"] == "TASK_ASSIGNED" for n in notifs_after_task)

    # 5. Re-enable task_updates -> subsequent tasks generate notifications
    client.patch(
        "/api/v1/notifications/preferences",
        json={"task_updates": True},
        headers=h_lawyer,
    )
    client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "File Rejoinder", "owner_user_id": lawyer_id},
        headers=h_owner,
    )
    notifs_after_re_enable = client.get("/api/v1/notifications", headers=h_lawyer).json()["items"]
    assert any(n["type"] == "TASK_ASSIGNED" for n in notifs_after_re_enable)


def test_notification_does_not_bypass_revoked_case_authorization(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "nav_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(client, "nav_lawyer@test.com", role="LAWYER")

    # 1. Create Case and assign Lawyer
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Confidential Arbitration", "description": "Arbitration proceedings"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )

    # 2. Lawyer has notification containing case_id
    notif = client.get("/api/v1/notifications", headers=h_lawyer).json()["items"][0]
    embedded_case_id = notif["case_id"]
    assert embedded_case_id == case_id

    # 3. Lawyer can initially access the case
    assert client.get(f"/api/v1/cases/{embedded_case_id}", headers=h_lawyer).status_code == 200

    # 4. Owner removes Lawyer from Case
    client.delete(f"/api/v1/cases/{case_id}/participants/{lawyer_id}", headers=h_owner)

    # 5. Lawyer still has the old notification, but attempting to navigate/access case returns 404
    assert client.get(f"/api/v1/cases/{embedded_case_id}", headers=h_lawyer).status_code == 404
    assert client.get(f"/api/v1/cases/{embedded_case_id}/workspace", headers=h_lawyer).status_code == 404
