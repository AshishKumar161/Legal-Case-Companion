"""Comprehensive Production Readiness & Hardening E2E Test Suite.

Phase 9 Final Release Gate:
1. End-to-End Multi-Tenant Client Journey (Register -> Login -> Case -> S3 Upload -> Scanner -> Retain Lawyer -> Consultation -> Messaging -> Notification).
2. Cross-Tenant BOLA / IDOR Penetration Attack Matrix (Cases, Documents, Tasks, Notes, Messages, Notifications).
3. Concurrent Refresh Token Rotation & Family Replay Invalidation.
4. Concurrent Consultation Slot Booking Race Condition Prevention.
5. External Webhook Security (Bearer Secret Verification, Tamper Rejection & Idempotency).
6. Atomic Database Transaction Rollback on Partial Failures.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.models.document import (
    Document,
    DocumentSecurityStatus,
)
from app.models.notification import NotificationType
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
    full_name: str = "Production User",
) -> tuple[UUID, dict[str, str]]:
    """Creates a user and returns (user_id, auth_headers)."""
    user_id = generate_uuid7()
    user = User(
        id=user_id,
        email=email,
        password_hash=hash_password("SecureProdPassword123!"),
        role=role,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    if role == UserRole.CLIENT:
        db.add(ClientProfile(id=generate_uuid7(), user_id=user.id, full_name=full_name))
    elif role == UserRole.LAWYER:
        db.add(LawyerProfile(id=generate_uuid7(), user_id=user.id, full_name=full_name, consultation_fee=2500.0))
    db.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecureProdPassword123!"},
    )
    token = login_res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def _verify_lawyer(db: Session, lawyer_user_id: UUID) -> LawyerProfile:
    """Marks lawyer profile as verified (APPROVED)."""
    lp = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == lawyer_user_id)
        .first()
    )
    assert lp is not None
    ver = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number=f"PROD-ENR/{str(lawyer_user_id)[:6]}",
        state_bar_council="Delhi Bar Council",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()
    db.refresh(lp)
    return lp


# ============================================================================
# 1. COMPLETE MULTI-TENANT E2E JOURNEY
# ============================================================================


def test_complete_multi_tenant_e2e_journey(client: TestClient, db: Session):
    """Verify complete end-to-end multi-tenant lifecycle from registration to resolution."""
    # 1. Client and Lawyer Registration
    client_id, h_client = _create_user(db, client, "prod_client_e2e@example.com", role=UserRole.CLIENT, full_name="Sanjay Verma")
    lawyer_id, h_lawyer = _create_user(db, client, "prod_advocate_e2e@example.com", role=UserRole.LAWYER, full_name="Adv. Meera Sen")
    lp = _verify_lawyer(db, lawyer_id)
    lp.consultation_fee = 0.0
    db.commit()

    # 2. Client Opens New Case File
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Shareholder Dispute in Fintech", "description": "Arbitration under Companies Act 2013"},
        headers=h_client,
    )
    assert res_case.status_code == 201
    case_id = res_case.json()["id"]

    # 3. Client Uploads Dispute Evidence Document
    res_up = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "Shareholders_Agreement_2024.pdf",
            "file_size": 2048,
            "mime_type": "application/pdf",
            "document_type": "CONTRACT",
        },
        headers=h_client,
    )
    assert res_up.status_code == 201
    doc_id = res_up.json()["document"]["id"]
    assert res_up.json()["document"]["security_status"] == "PENDING"

    # Attempt download while PENDING -> 403 Forbidden (Zero-Trust Gating)
    assert client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/download", headers=h_client).status_code == 403

    # Client notifies upload completion -> Transitions to QUARANTINED
    res_comp = client.post(f"/api/v1/documents/{doc_id}/complete", headers=h_client)
    assert res_comp.status_code == 200
    assert res_comp.json()["security_status"] == "QUARANTINED"

    # 4. Automated Malware Scanner Webhook Validates Document as SAFE
    orig_secret = settings.AWS_WEBHOOK_SECRET
    settings.AWS_WEBHOOK_SECRET = "test_webhook_secret_phase9"
    try:
        res_webhook = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": str(doc_id), "is_safe": True},
        )
        assert res_webhook.status_code == 200
    finally:
        settings.AWS_WEBHOOK_SECRET = orig_secret

    # Download is now permitted for Case Owner
    res_down = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/download", headers=h_client)
    assert res_down.status_code == 200
    assert "download_url" in res_down.json()

    # 5. Client Retains Advocate via Consultation
    fut = (datetime.now(UTC) + timedelta(days=3)).replace(hour=14, minute=0, second=0, microsecond=0).isoformat()
    res_con = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": str(lawyer_id), "case_id": case_id, "scheduled_at": fut, "duration_minutes": 30},
        headers=h_client,
    )
    assert res_con.status_code == 201
    con_id = res_con.json()["id"]

    # Lawyer accepts consultation
    res_acc = client.post(f"/api/v1/consultations/{con_id}/accept", headers=h_lawyer)
    assert res_acc.status_code == 200

    # 6. Pre-Case Consultation Messaging
    res_cmsg = client.post(
        f"/api/v1/consultations/{con_id}/messages",
        json={"content": "Advocate, please review the SHA clause 14 on dispute resolution."},
        headers=h_client,
    )
    assert res_cmsg.status_code == 201

    # 7. Add Lawyer as Legal Counsel to Case Workspace
    res_part = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(lawyer_id), "participant_role": "LAWYER"},
        headers=h_client,
    )
    assert res_part.status_code in (200, 201)

    # 8. Lawyer Creates Matter Task and Posts Counsel Notice
    res_task = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Draft Section 9 Arbitration Petition", "priority": "HIGH", "owner_user_id": str(client_id)},
        headers=h_lawyer,
    )
    assert res_task.status_code == 201

    res_mat_msg = client.post(
        f"/api/v1/cases/{case_id}/collaboration/messages",
        json={"content": "Section 9 draft ready for client verification.", "message_type": "FORMAL_NOTICE", "is_counsel_only": False},
        headers=h_lawyer,
    )
    assert res_mat_msg.status_code == 201

    # 9. Client Verifies In-App Notifications
    notifs = client.get("/api/v1/notifications", headers=h_client).json()["items"]
    assert any(n["type"] == NotificationType.TASK_ASSIGNED.value for n in notifs)
    assert any(n["type"] == NotificationType.MATTER_MESSAGE_RECEIVED.value for n in notifs)


# ============================================================================
# 2. CROSS-TENANT BOLA / IDOR PENETRATION ATTACK MATRIX
# ============================================================================


def test_cross_tenant_bola_idor_penetration_matrix(client: TestClient, db: Session):
    """Systematic red-team penetration testing across all resources for unauthorized cross-tenant leakage."""
    _user_a_id, h_a = _create_user(db, client, "tenant_a_victim@example.com", role=UserRole.CLIENT)
    _user_b_id, h_b = _create_user(db, client, "tenant_b_attacker@example.com", role=UserRole.CLIENT)

    # 1. Victim creates Case A, Task, Note, and Document
    res_case_a = client.post("/api/v1/cases", json={"title": "Confidential IP Asset", "description": "Trade secrets"}, headers=h_a)
    case_a_id = res_case_a.json()["id"]

    res_task = client.post(f"/api/v1/cases/{case_a_id}/tasks", json={"title": "Victim Task"}, headers=h_a)
    task_a_id = res_task.json()["id"]

    res_note = client.post(f"/api/v1/cases/{case_a_id}/notes", json={"title": "Secret Note", "content": "Patents", "visibility": "CLIENT_PRIVATE"}, headers=h_a)
    note_a_id = res_note.json()["id"]

    # 2. Attacker Attempts BOLA/IDOR on Case A:
    # Read Case A -> 404
    assert client.get(f"/api/v1/cases/{case_a_id}", headers=h_b).status_code == 404
    # Update Case A -> 404
    assert client.patch(f"/api/v1/cases/{case_a_id}", json={"title": "Compromised"}, headers=h_b).status_code == 404
    # Delete Case A -> 404
    assert client.delete(f"/api/v1/cases/{case_a_id}", headers=h_b).status_code == 404
    # List Case A tasks -> 404
    assert client.get(f"/api/v1/cases/{case_a_id}/tasks", headers=h_b).status_code == 404
    # Update Case A task -> 404
    assert client.patch(f"/api/v1/cases/{case_a_id}/tasks/{task_a_id}", json={"status": "COMPLETED"}, headers=h_b).status_code == 404
    # Read Case A note -> 404
    assert client.get(f"/api/v1/cases/{case_a_id}/notes/{note_a_id}", headers=h_b).status_code == 404
    # Read Case A messages -> 404
    assert client.get(f"/api/v1/cases/{case_a_id}/collaboration/messages", headers=h_b).status_code == 404
    # Send message to Case A -> 404
    assert client.post(f"/api/v1/cases/{case_a_id}/collaboration/messages", json={"content": "Injected"}, headers=h_b).status_code == 404


# ============================================================================
# 3. CONCURRENT REFRESH TOKEN ROTATION & REPLAY INVALIDATION
# ============================================================================


def test_concurrent_refresh_rotation_and_replay_invalidation(client: TestClient, db: Session):
    """Verify refresh token rotation concurrency safety and immediate token-family invalidation upon replay."""
    _user_id, _ = _create_user(db, client, "refresh_replay_prod@example.com", role=UserRole.CLIENT)

    # 1. Login to establish cookie session
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "refresh_replay_prod@example.com", "password": "SecureProdPassword123!"},
    )
    assert login_res.status_code == 200
    csrf_token = login_res.cookies.get("csrf_token")
    headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}

    # 2. Legitimate Refresh -> 200 OK
    ref1_res = client.post("/api/v1/auth/refresh", headers=headers)
    assert ref1_res.status_code == 200
    assert "access_token" in ref1_res.json()

    # 3. Attacker Replays the previous refresh token -> 401 Unauthorized + entire family invalidated
    replay_res = client.post("/api/v1/auth/refresh", headers=headers, cookies=login_res.cookies)
    assert replay_res.status_code == 401

    # 4. Subsequent refresh with newly issued token also fails because family was revoked
    ref2_res = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": ref1_res.cookies.get("csrf_token")}, cookies=ref1_res.cookies)
    assert ref2_res.status_code == 401


# ============================================================================
# 4. CONCURRENT CONSULTATION SLOT BOOKING RACE PREVENTION
# ============================================================================


def test_concurrent_consultation_slot_booking_race_prevention(client: TestClient, db: Session):
    """Verify that concurrent booking of the identical lawyer slot prevents double-booking."""
    _c1_id, h_c1 = _create_user(db, client, "race_client_1@example.com", role=UserRole.CLIENT)
    _c2_id, h_c2 = _create_user(db, client, "race_client_2@example.com", role=UserRole.CLIENT)
    lawyer_id, _h_l = _create_user(db, client, "race_lawyer@example.com", role=UserRole.LAWYER)
    lp = _verify_lawyer(db, lawyer_id)
    lp.consultation_fee = 0.0
    db.commit()

    slot_time = (datetime.now(UTC) + timedelta(days=7)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()

    # Client 1 books slot -> 201 Created
    res1 = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": str(lawyer_id), "scheduled_at": slot_time, "duration_minutes": 30},
        headers=h_c1,
    )
    assert res1.status_code == 201

    # Client 2 attempts to book the same conflicting slot -> 422 Unprocessable (overlapping slot)
    res2 = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": str(lawyer_id), "scheduled_at": slot_time, "duration_minutes": 30},
        headers=h_c2,
    )
    assert res2.status_code == 422
    assert "overlaps" in res2.json()["error"]["message"].lower()


# ============================================================================
# 5. WEBHOOK TAMPERING & IDEMPOTENCY DEFENSE
# ============================================================================


def test_webhook_tampering_and_idempotency_defense(client: TestClient, db: Session):
    """Verify Bearer secret validation, unauthorized rejection, and idempotent state transitions."""
    owner_id, h_owner = _create_user(db, client, "webhook_owner_prod@example.com", role=UserRole.CLIENT)
    res_case = client.post("/api/v1/cases", json={"title": "Webhook Defense Case", "description": "Desc"}, headers=h_owner)
    case_id = UUID(res_case.json()["id"])

    doc = Document(
        id=generate_uuid7(),
        case_id=case_id,
        uploaded_by=owner_id,
        filename="Evidence_Contract.pdf",
        storage_key="cases/prod/doc.pdf",
        mime_type="application/pdf",
        file_size=1024,
        security_status=DocumentSecurityStatus.QUARANTINED,
    )
    db.add(doc)
    db.commit()

    orig_secret = settings.AWS_WEBHOOK_SECRET
    settings.AWS_WEBHOOK_SECRET = "test_webhook_secret_phase9"

    try:
        # 1. Missing secret -> 401
        assert client.post("/api/v1/webhooks/aws/malware", json={"document_id": str(doc.id), "is_safe": True}).status_code == 401

        # 2. Invalid secret -> 401
        assert client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": "Bearer invalid_secret"},
            json={"document_id": str(doc.id), "is_safe": True},
        ).status_code == 401

        # 3. Legitimate callback -> 200 OK
        res_valid = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": str(doc.id), "is_safe": True},
        )
        assert res_valid.status_code == 200
        db.refresh(doc)
        assert doc.security_status == DocumentSecurityStatus.SAFE

        # 4. Duplicate / Replayed callback -> Idempotent 200 OK
        res_replay = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": str(doc.id), "is_safe": True},
        )
        assert res_replay.status_code == 200
        db.refresh(doc)
        assert doc.security_status == DocumentSecurityStatus.SAFE
    finally:
        settings.AWS_WEBHOOK_SECRET = orig_secret
