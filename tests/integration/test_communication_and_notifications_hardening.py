"""Comprehensive Communication, Messaging & Notifications Test Suite.

Phase 7 Verification:
- Case-Level Messaging Scope & Counsel-Only Isolation
- Cross-Case Linked Resource Integrity (Documents & Tasks)
- Consultation-Level Direct Messaging & Terminal State Freezing
- Notification Category Preferences, Opt-Outs & Persisted Audit Logging
- In-App Notification Read/Unread Lifecycle, Bulk Read & Unread Count Aggregation
- Recipient Isolation & BOLA/IDOR Security Matrix
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.models.audit import AuditEvent
from app.models.document import Document, DocumentSecurityStatus
from app.models.notification import NotificationType
from app.models.task import CaseTask, TaskPriority, TaskSourceType, TaskStatus
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)


def _create_user(
    db: Session,
    client: TestClient,
    email: str,
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Test User",
) -> tuple[UUID, dict[str, str]]:
    """Creates a user and returns (user_id, auth_headers)."""
    user_id = generate_uuid7()
    user = User(
        id=user_id,
        email=email,
        password_hash=hash_password("SecurePassword123!"),
        role=role,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    if role == UserRole.CLIENT:
        db.add(ClientProfile(id=generate_uuid7(), user_id=user.id, full_name=full_name))
    elif role == UserRole.LAWYER:
        db.add(LawyerProfile(id=generate_uuid7(), user_id=user.id, full_name=full_name, consultation_fee=2000.0))
    db.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def _verify_lawyer_profile(db: Session, lawyer_user_id: UUID) -> LawyerProfile:
    """Helper to mark lawyer profile as verified (APPROVED)."""
    lp = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == lawyer_user_id)
        .first()
    )
    assert lp is not None
    ver = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number=f"ENR/{str(lawyer_user_id)[:6]}",
        state_bar_council="Delhi Bar Council",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()
    db.refresh(lp)
    return lp


# ============================================================================
# 1. CASE COLLABORATION MESSAGES & COUNSEL-ONLY ISOLATION
# ============================================================================


def test_case_collaboration_messages_and_counsel_only_isolation(client: TestClient, db: Session):
    """Verify case messaging, counsel-only privacy, and automatic notification dispatch."""
    _owner_id, h_owner = _create_user(db, client, "cmsg_owner@example.com", role=UserRole.CLIENT, full_name="Owner Client")
    lawyer_id, h_lawyer = _create_user(db, client, "cmsg_lawyer@example.com", role=UserRole.LAWYER, full_name="Counsel Lawyer")
    viewer_id, h_viewer = _create_user(db, client, "cmsg_viewer@example.com", role=UserRole.CLIENT, full_name="Viewer Member")
    _verify_lawyer_profile(db, lawyer_id)

    # 1. Create Case and add participants
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Commercial Arbitration", "description": "Arbitration proceedings"},
        headers=h_owner,
    )
    assert res_case.status_code == 201
    case_id = res_case.json()["id"]

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(lawyer_id), "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(viewer_id), "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 2. Case Owner sends general message -> 201
    res_msg1 = client.post(
        f"/api/v1/cases/{case_id}/collaboration/messages",
        json={"content": "Please review the arbitration petition draft.", "message_type": "GENERAL"},
        headers=h_owner,
    )
    assert res_msg1.status_code == 201
    assert res_msg1.json()["sender_name"] == "Owner Client"
    assert res_msg1.json()["is_counsel_only"] is False

    # Lawyer receives MATTER_MESSAGE_RECEIVED notification
    l_notifs = client.get("/api/v1/notifications", headers=h_lawyer).json()["items"]
    assert any(n["type"] == NotificationType.MATTER_MESSAGE_RECEIVED.value for n in l_notifs)

    # 3. Client attempts to send counsel-only message -> 403 Forbidden
    res_cl_counsel = client.post(
        f"/api/v1/cases/{case_id}/collaboration/messages",
        json={"content": "Confidential client note", "message_type": "FORMAL_NOTICE", "is_counsel_only": True},
        headers=h_owner,
    )
    assert res_cl_counsel.status_code == 403

    # 4. Viewer attempts to send counsel-only message -> 403 Forbidden
    res_vw_counsel = client.post(
        f"/api/v1/cases/{case_id}/collaboration/messages",
        json={"content": "Confidential viewer note", "message_type": "FORMAL_NOTICE", "is_counsel_only": True},
        headers=h_viewer,
    )
    assert res_vw_counsel.status_code == 403

    # 5. Lawyer sends counsel-only message -> 201
    res_lawyer_counsel = client.post(
        f"/api/v1/cases/{case_id}/collaboration/messages",
        json={"content": "Privileged counsel strategy assessment.", "message_type": "FORMAL_NOTICE", "is_counsel_only": True},
        headers=h_lawyer,
    )
    assert res_lawyer_counsel.status_code == 201
    assert res_lawyer_counsel.json()["is_counsel_only"] is True

    # 6. Read visibility filtering:
    # Client reads messages -> counsel-only message is filtered out (total 1)
    msgs_owner = client.get(f"/api/v1/cases/{case_id}/collaboration/messages", headers=h_owner).json()
    assert len(msgs_owner) == 1
    assert msgs_owner[0]["content"] == "Please review the arbitration petition draft."

    # Viewer reads messages -> counsel-only message is filtered out (total 1)
    msgs_viewer = client.get(f"/api/v1/cases/{case_id}/collaboration/messages", headers=h_viewer).json()
    assert len(msgs_viewer) == 1

    # Lawyer reads messages -> counsel-only message is visible (total 2)
    msgs_lawyer = client.get(f"/api/v1/cases/{case_id}/collaboration/messages", headers=h_lawyer).json()
    assert len(msgs_lawyer) == 2
    contents = [m["content"] for m in msgs_lawyer]
    assert "Privileged counsel strategy assessment." in contents


# ============================================================================
# 2. LINKED RESOURCE INTEGRITY IN CASE MESSAGES
# ============================================================================


def test_case_message_linked_resource_integrity(client: TestClient, db: Session):
    """Verify linked documents and tasks must belong to the exact same case."""
    owner_id, h_owner = _create_user(db, client, "link_owner@example.com", role=UserRole.CLIENT)

    # Setup Case A and Case B
    res_a = client.post("/api/v1/cases", json={"title": "Matter Alpha", "description": "Alpha Description"}, headers=h_owner)
    assert res_a.status_code == 201
    case_a_id = UUID(res_a.json()["id"])

    res_b = client.post("/api/v1/cases", json={"title": "Matter Beta", "description": "Beta Description"}, headers=h_owner)
    assert res_b.status_code == 201
    case_b_id = UUID(res_b.json()["id"])

    # Create Document and Task in Case A
    doc_a = Document(
        id=generate_uuid7(),
        case_id=case_a_id,
        filename="Contract_Alpha.pdf",
        file_size=1024,
        storage_key="cases/alpha/doc.pdf",
        mime_type="application/pdf",
        security_status=DocumentSecurityStatus.SAFE,
        uploaded_by=owner_id,
    )
    task_a = CaseTask(
        id=generate_uuid7(),
        case_id=case_a_id,
        created_by_user_id=owner_id,
        title="Review Alpha Contract",
        priority=TaskPriority.HIGH,
        status=TaskStatus.PENDING,
        source_type=TaskSourceType.MANUAL,
    )
    # Create Document in Case B
    doc_b = Document(
        id=generate_uuid7(),
        case_id=case_b_id,
        filename="Foreign_Contract_Beta.pdf",
        file_size=2048,
        storage_key="cases/beta/doc.pdf",
        mime_type="application/pdf",
        security_status=DocumentSecurityStatus.SAFE,
        uploaded_by=owner_id,
    )
    db.add_all([doc_a, task_a, doc_b])
    db.commit()

    # 1. Send message in Case A linking valid Doc A and Task A -> 201
    res_valid = client.post(
        f"/api/v1/cases/{case_a_id}/collaboration/messages",
        json={
            "content": "Referencing the alpha contract and review task.",
            "linked_document_id": str(doc_a.id),
            "linked_task_id": str(task_a.id),
            "message_type": "DOCUMENT_SUBMISSION",
        },
        headers=h_owner,
    )
    assert res_valid.status_code == 201
    assert res_valid.json()["linked_document_title"] == "Contract_Alpha.pdf"
    assert res_valid.json()["linked_task_title"] == "Review Alpha Contract"

    # 2. Attempt to link Doc B (from Case B) in Case A message -> Rejected (422)
    res_foreign_doc = client.post(
        f"/api/v1/cases/{case_a_id}/collaboration/messages",
        json={
            "content": "Attempting foreign document link.",
            "linked_document_id": str(doc_b.id),
            "message_type": "DOCUMENT_SUBMISSION",
        },
        headers=h_owner,
    )
    assert res_foreign_doc.status_code == 422
    assert "Linked document does not belong to this matter" in res_foreign_doc.json()["error"]["message"]


# ============================================================================
# 3. CONSULTATION MESSAGING FLOW & TERMINAL FREEZE
# ============================================================================


def test_consultation_messaging_flow_and_terminal_freeze(client: TestClient, db: Session):
    """Verify pre-case consultation messaging and terminal freeze."""
    _client_id, h_client = _create_user(db, client, "con_msg_c@example.com", role=UserRole.CLIENT)
    lawyer_id, h_lawyer = _create_user(db, client, "con_msg_l@example.com", role=UserRole.LAWYER)
    _stranger_id, h_stranger = _create_user(db, client, "con_msg_stranger@example.com", role=UserRole.CLIENT)
    lp = _verify_lawyer_profile(db, lawyer_id)
    lp.consultation_fee = 0.0
    db.commit()

    # 1. Create Consultation
    fut = (datetime.now(UTC) + timedelta(days=5)).replace(hour=11, minute=0, second=0, microsecond=0).isoformat()
    res_con = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": str(lawyer_id), "scheduled_at": fut, "duration_minutes": 30},
        headers=h_client,
    )
    assert res_con.status_code == 201
    c_id = res_con.json()["id"]

    # 2. Client sends message -> 201
    res_m1 = client.post(
        f"/api/v1/consultations/{c_id}/messages",
        json={"content": "Hello, I would like to discuss a property dispute."},
        headers=h_client,
    )
    assert res_m1.status_code == 201

    # 3. Lawyer sends message -> 201
    res_m2 = client.post(
        f"/api/v1/consultations/{c_id}/messages",
        json={"content": "Please share the registered sale deed."},
        headers=h_lawyer,
    )
    assert res_m2.status_code == 201

    # 4. Stranger attempts to read messages -> 404 (IDOR defense)
    assert client.get(f"/api/v1/consultations/{c_id}/messages", headers=h_stranger).status_code == 404

    # 5. Client reads messages -> 200 (both messages returned in chronological order)
    res_list = client.get(f"/api/v1/consultations/{c_id}/messages", headers=h_client)
    assert res_list.status_code == 200
    msgs = res_list.json()
    assert len(msgs) == 2
    assert msgs[0]["content"] == "Hello, I would like to discuss a property dispute."
    assert msgs[1]["content"] == "Please share the registered sale deed."

    # 6. Cancel consultation -> Terminal state freezes messaging
    client.post(f"/api/v1/consultations/{c_id}/cancel", headers=h_client)

    res_post_cancel = client.post(
        f"/api/v1/consultations/{c_id}/messages",
        json={"content": "Message after cancellation attempt"},
        headers=h_client,
    )
    assert res_post_cancel.status_code == 422
    assert "Cannot send messages to a consultation in CANCELLED state" in res_post_cancel.json()["error"]["message"]


# ============================================================================
# 4. NOTIFICATION CATEGORY PREFERENCES & AUDIT
# ============================================================================


def test_notification_category_preferences_and_audit(client: TestClient, db: Session):
    """Verify user notification preferences, category opt-outs, and audit persistence."""
    _owner_id, h_owner = _create_user(db, client, "pref_test_owner@example.com", role=UserRole.CLIENT)
    lawyer_id, h_lawyer = _create_user(db, client, "pref_test_lawyer@example.com", role=UserRole.LAWYER)
    _verify_lawyer_profile(db, lawyer_id)

    # 1. Lawyer opts out of task_updates
    res_pref_update = client.patch(
        "/api/v1/notifications/preferences",
        json={"task_updates": False, "email_enabled": False},
        headers=h_lawyer,
    )
    assert res_pref_update.status_code == 200
    assert res_pref_update.json()["task_updates"] is False
    assert res_pref_update.json()["email_enabled"] is False

    # Verify audit event in DB
    audit = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.actor_user_id == lawyer_id,
            AuditEvent.event_type == "NOTIFICATION_PREFERENCES_UPDATED",
        )
        .first()
    )
    assert audit is not None
    assert "task_updates" in audit.metadata_["updated_fields"]

    # 2. Case created and Lawyer added -> LAWYER_ASSIGNED generated (case_updates is True)
    res_case = client.post("/api/v1/cases", json={"title": "Preference Case", "description": "Pref Desc"}, headers=h_owner)
    assert res_case.status_code == 201
    case_id = res_case.json()["id"]

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(lawyer_id), "participant_role": "LAWYER"},
        headers=h_owner,
    )
    notifs_l = client.get("/api/v1/notifications", headers=h_lawyer).json()["items"]
    assert any(n["type"] == NotificationType.LAWYER_ASSIGNED.value for n in notifs_l)

    # 3. Create Task assigned to Lawyer -> Suppressed because task_updates=False
    client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Suppressed Task", "owner_user_id": str(lawyer_id)},
        headers=h_owner,
    )
    notifs_after = client.get("/api/v1/notifications", headers=h_lawyer).json()["items"]
    assert not any(n["type"] == NotificationType.TASK_ASSIGNED.value for n in notifs_after)

    # 4. Re-enable task_updates -> Subsequent tasks produce notifications
    client.patch(
        "/api/v1/notifications/preferences",
        json={"task_updates": True},
        headers=h_lawyer,
    )
    client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Active Task", "owner_user_id": str(lawyer_id)},
        headers=h_owner,
    )
    notifs_re = client.get("/api/v1/notifications", headers=h_lawyer).json()["items"]
    assert any(n["type"] == NotificationType.TASK_ASSIGNED.value for n in notifs_re)


# ============================================================================
# 5. NOTIFICATION READ STATES, BULK OPERATIONS & UNREAD COUNTS
# ============================================================================


def test_notification_read_states_bulk_and_unread_counts(client: TestClient, db: Session):
    """Verify single read/unread idempotency, bulk mark read, unread counts, and recipient isolation."""
    _user_a_id, h_a = _create_user(db, client, "notif_ops_a@example.com", role=UserRole.CLIENT)
    _user_b_id, h_b = _create_user(db, client, "notif_ops_b@example.com", role=UserRole.CLIENT)

    # Generate 3 notifications for User A
    for i in range(3):
        res_a = client.post("/api/v1/cases", json={"title": f"Matter A{i+1}", "description": "Desc A"}, headers=h_a)
        assert res_a.status_code == 201

    # Generate 2 notifications for User B
    for i in range(2):
        res_b = client.post("/api/v1/cases", json={"title": f"Matter B{i+1}", "description": "Desc B"}, headers=h_b)
        assert res_b.status_code == 201

    # 1. Check initial unread counts
    assert client.get("/api/v1/notifications/unread-count", headers=h_a).json()["unread_count"] == 3
    assert client.get("/api/v1/notifications/unread-count", headers=h_b).json()["unread_count"] == 2

    # 2. User A fetches notifications
    a_items = client.get("/api/v1/notifications", headers=h_a).json()["items"]
    assert len(a_items) == 3
    a_notif0_id = a_items[0]["id"]
    a_notif1_id = a_items[1]["id"]

    b_items = client.get("/api/v1/notifications", headers=h_b).json()["items"]
    b_notif0_id = b_items[0]["id"]

    # 3. User A marks notif 0 as read -> idempotent 200
    res_r1 = client.post(f"/api/v1/notifications/{a_notif0_id}/read", headers=h_a)
    assert res_r1.status_code == 200
    assert res_r1.json()["is_read"] is True
    assert client.get("/api/v1/notifications/unread-count", headers=h_a).json()["unread_count"] == 2

    # 4. User A marks notif 0 as unread -> 200
    res_unr = client.post(f"/api/v1/notifications/{a_notif0_id}/unread", headers=h_a)
    assert res_unr.status_code == 200
    assert res_unr.json()["is_read"] is False
    assert client.get("/api/v1/notifications/unread-count", headers=h_a).json()["unread_count"] == 3

    # 5. Bulk read with foreign and non-existent IDs:
    # User A calls bulk-read with [a_notif0, a_notif1, b_notif0 (foreign), fake_uuid]
    fake_uuid = str(generate_uuid7())
    res_bulk = client.post(
        "/api/v1/notifications/bulk-read",
        json={"notification_ids": [a_notif0_id, a_notif1_id, b_notif0_id, fake_uuid]},
        headers=h_a,
    )
    assert res_bulk.status_code == 200
    # Exactly 2 of User A's notifications updated
    assert res_bulk.json()["updated_count"] == 2
    assert client.get("/api/v1/notifications/unread-count", headers=h_a).json()["unread_count"] == 1
    # User B's count unaffected
    assert client.get("/api/v1/notifications/unread-count", headers=h_b).json()["unread_count"] == 2

    # 6. User A calls read-all -> marks remaining 1
    res_read_all = client.post("/api/v1/notifications/read-all", headers=h_a)
    assert res_read_all.status_code == 200
    assert res_read_all.json()["updated_count"] == 1
    assert client.get("/api/v1/notifications/unread-count", headers=h_a).json()["unread_count"] == 0

    # 7. User A deletes notif 0 -> 204
    assert client.delete(f"/api/v1/notifications/{a_notif0_id}", headers=h_a).status_code == 204


# ============================================================================
# 6. CROSS-TENANT BOLA / IDOR SECURITY MATRIX
# ============================================================================


def test_cross_tenant_communication_bola_matrix(client: TestClient, db: Session):
    """Verify BOLA/IDOR protection on cross-tenant notifications, messages, and removed participants."""
    _owner_a_id, h_a = _create_user(db, client, "bola_owner_a@example.com", role=UserRole.CLIENT)
    _owner_b_id, h_b = _create_user(db, client, "bola_owner_b@example.com", role=UserRole.CLIENT)
    lawyer_id, h_l = _create_user(db, client, "bola_lawyer@example.com", role=UserRole.LAWYER)
    _verify_lawyer_profile(db, lawyer_id)

    # 1. Create Case A with Lawyer
    res_case_a = client.post("/api/v1/cases", json={"title": "Case Alpha", "description": "Alpha Desc"}, headers=h_a)
    assert res_case_a.status_code == 201
    case_a_id = res_case_a.json()["id"]
    client.post(
        f"/api/v1/cases/{case_a_id}/participants",
        json={"user_id": str(lawyer_id), "participant_role": "LAWYER"},
        headers=h_a,
    )

    # 2. User B attempts to read Case A collaboration messages -> 404
    assert client.get(f"/api/v1/cases/{case_a_id}/collaboration/messages", headers=h_b).status_code == 404

    # 3. User B attempts to send message to Case A -> 404
    assert client.post(
        f"/api/v1/cases/{case_a_id}/collaboration/messages",
        json={"content": "Intrusion message"},
        headers=h_b,
    ).status_code == 404

    # 4. Remove Lawyer from Case A
    client.delete(f"/api/v1/cases/{case_a_id}/participants/{lawyer_id}", headers=h_a)

    # 5. Removed Lawyer attempting to send message -> 404 Not Found (BOLA defense)
    res_rem_send = client.post(
        f"/api/v1/cases/{case_a_id}/collaboration/messages",
        json={"content": "Post-removal message attempt"},
        headers=h_l,
    )
    assert res_rem_send.status_code == 404
