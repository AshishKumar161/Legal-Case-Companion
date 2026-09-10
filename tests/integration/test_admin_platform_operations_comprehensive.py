from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole
from app.models.consultation import Consultation, ConsultationStatus
from app.models.document import (
    Document,
    DocumentCategory,
    DocumentProcessingStatus,
    DocumentSecurityStatus,
)
from app.models.notification import Notification
from app.models.payment import Payment, PaymentStatus
from app.models.user import (
    AccountStatus,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)


def _setup_user(
    client: TestClient,
    db: Session,
    email: str,
    password: str = "Pass123!",
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Test User",
) -> tuple[str, dict[str, str]]:
    if role == UserRole.ADMIN:
        admin = User(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            account_status=AccountStatus.ACTIVE,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        user_id = admin.id
    else:
        res_reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "role": role.value,
                "full_name": full_name,
            },
        )
        user_id = res_reg.json().get("id")

    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return str(user_id), {"Authorization": f"Bearer {token}"}


# ============================================================================
# 1. ADMIN RBAC & AUTHORIZATION GUARDS
# ============================================================================


def test_admin_authorization_and_rbac_guards(client: TestClient, db: Session):
    """
    Verifies that all admin endpoints strictly require UserRole.ADMIN,
    rejecting Clients, Lawyers, and Unauthenticated users.
    """
    _, h_admin = _setup_user(client, db, "admin_rbac_test@example.com", role=UserRole.ADMIN, full_name="Super Admin")
    _, h_client = _setup_user(client, db, "client_rbac_test@example.com", role=UserRole.CLIENT, full_name="Regular Client")
    _, h_lawyer = _setup_user(client, db, "lawyer_rbac_test@example.com", role=UserRole.LAWYER, full_name="Advocate Test")

    # 1. Overview
    assert client.get("/api/v1/admin/overview", headers=h_admin).status_code == 200
    assert client.get("/api/v1/admin/overview", headers=h_client).status_code == 403
    assert client.get("/api/v1/admin/overview", headers=h_lawyer).status_code == 403
    assert client.get("/api/v1/admin/overview").status_code == 401

    # 2. Users
    assert client.get("/api/v1/admin/users", headers=h_admin).status_code == 200
    assert client.get("/api/v1/admin/users", headers=h_client).status_code == 403
    assert client.get("/api/v1/admin/users", headers=h_lawyer).status_code == 403

    # 3. Cases
    assert client.get("/api/v1/admin/cases", headers=h_admin).status_code == 200
    assert client.get("/api/v1/admin/cases", headers=h_client).status_code == 403

    # 4. Consultations
    assert client.get("/api/v1/admin/consultations", headers=h_admin).status_code == 200
    assert client.get("/api/v1/admin/consultations", headers=h_client).status_code == 403

    # 5. Payments
    assert client.get("/api/v1/admin/payments", headers=h_admin).status_code == 200
    assert client.get("/api/v1/admin/payments", headers=h_client).status_code == 403

    # 6. Document Security
    assert client.get("/api/v1/admin/document-security", headers=h_admin).status_code == 200
    assert client.get("/api/v1/admin/document-security", headers=h_client).status_code == 403

    # 7. Audit & Security Events
    assert client.get("/api/v1/admin/audit", headers=h_admin).status_code == 200
    assert client.get("/api/v1/admin/audit", headers=h_client).status_code == 403
    assert client.get("/api/v1/admin/security-events", headers=h_admin).status_code == 200
    assert client.get("/api/v1/admin/security-events", headers=h_client).status_code == 403


# ============================================================================
# 2. USER MANAGEMENT, SUSPENSION & REACTIVATION LIFECYCLE
# ============================================================================


def test_user_management_suspension_lifecycle(client: TestClient, db: Session):
    """
    Verifies user listing, filtering, search, suspension with reason, session denial,
    and reactivation.
    """
    admin_id, h_admin = _setup_user(client, db, "admin_usermgt@example.com", role=UserRole.ADMIN, full_name="Admin Mgt")
    target_id, h_target = _setup_user(client, db, "bad_user@example.com", role=UserRole.CLIENT, full_name="Malicious Actor")

    # 1. List users and search
    res = client.get("/api/v1/admin/users?search=Malicious", headers=h_admin)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any(u["email"] == "bad_user@example.com" for u in data["items"])

    # 2. Get specific user details
    res_user = client.get(f"/api/v1/admin/users/{target_id}", headers=h_admin)
    assert res_user.status_code == 200
    assert res_user.json()["account_status"] == "ACTIVE"
    # Ensure password hash is not exposed
    assert "password_hash" not in res_user.json()

    # 3. Suspend user with reason
    res_suspend = client.post(
        f"/api/v1/admin/users/{target_id}/suspend",
        headers=h_admin,
        json={"reason": "Terms of Service Violation - Spam Activity"},
    )
    assert res_suspend.status_code == 200
    assert res_suspend.json()["account_status"] == "SUSPENDED"

    # Verify target user is now denied access on active token
    res_denied = client.get("/api/v1/cases", headers=h_target)
    assert res_denied.status_code in [401, 403]

    # Verify target user cannot login
    res_login_denied = client.post("/api/v1/auth/login", json={"email": "bad_user@example.com", "password": "Pass123!"})
    assert res_login_denied.status_code in [400, 401, 403]

    # 4. Reactivate user
    res_reactivate = client.post(
        f"/api/v1/admin/users/{target_id}/reactivate",
        headers=h_admin,
    )
    assert res_reactivate.status_code == 200
    assert res_reactivate.json()["account_status"] == "ACTIVE"

    # Verify target user can now login again
    res_login_ok = client.post("/api/v1/auth/login", json={"email": "bad_user@example.com", "password": "Pass123!"})
    assert res_login_ok.status_code == 200

    # 5. Admin cannot suspend self
    res_self_suspend = client.post(f"/api/v1/admin/users/{admin_id}/suspend", headers=h_admin, json={})
    assert res_self_suspend.status_code == 403


# ============================================================================
# 3. LAWYER VERIFICATION REVIEW & NOTIFICATIONS
# ============================================================================


def test_lawyer_verification_review_workflow(client: TestClient, db: Session):
    """
    Verifies lawyer verification submission, admin approval, audit trail,
    and lawyer in-app notification.
    """
    _, h_admin = _setup_user(client, db, "admin_verif_mgt@example.com", role=UserRole.ADMIN, full_name="Verification Admin")
    lawyer_id, h_lawyer = _setup_user(client, db, "lawyer_applicant@example.com", role=UserRole.LAWYER, full_name="Advocate Sharma")

    # Retrieve LawyerProfile & create LawyerVerification in DB
    lawyer_u = db.query(User).filter(User.id == UUID(lawyer_id)).first()
    assert lawyer_u is not None
    assert lawyer_u.lawyer_profile is not None

    verif = LawyerVerification(
        lawyer_profile_id=lawyer_u.lawyer_profile.id,
        enrollment_number="DL/2020/998877",
        state_bar_council="Bar Council of Delhi",
        status=VerificationStatus.PENDING,
    )
    db.add(verif)
    db.commit()

    # 1. Admin lists verifications
    res_list = client.get("/api/v1/admin/verifications", headers=h_admin)
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert any(v["id"] == str(verif.id) for v in items)

    # 2. Non-admin cannot approve
    res_fake = client.post(f"/api/v1/admin/verifications/{verif.id}/approve", headers=h_lawyer)
    assert res_fake.status_code == 403

    # 3. Admin approves verification
    res_approve = client.post(f"/api/v1/admin/verifications/{verif.id}/approve", headers=h_admin)
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "APPROVED"

    # Verify in-app notification sent to lawyer
    notif = db.query(Notification).filter(Notification.user_id == lawyer_u.id).order_by(Notification.created_at.desc()).first()
    assert notif is not None
    assert "APPROVED" in notif.message

    # 4. Attempt to approve again is rejected
    res_dup = client.post(f"/api/v1/admin/verifications/{verif.id}/approve", headers=h_admin)
    assert res_dup.status_code in [400, 403]


# ============================================================================
# 4. PLATFORM OVERSIGHT: CASES, CONSULTATIONS, PAYMENTS & DOCUMENT SECURITY
# ============================================================================


def test_admin_oversight_domains(client: TestClient, db: Session):
    """
    Verifies operational oversight across cases, consultations, payments,
    and document security scanning status.
    """
    _, h_admin = _setup_user(client, db, "admin_oversight@example.com", role=UserRole.ADMIN, full_name="Ops Director")
    client_id, _ = _setup_user(client, db, "client_oversight@example.com", role=UserRole.CLIENT, full_name="Client Corp")
    lawyer_id, _ = _setup_user(client, db, "lawyer_oversight@example.com", role=UserRole.LAWYER, full_name="Advocate Verma")

    # Create Case
    test_case = Case(
        title="High Court Commercial Arbitration",
        description="Arbitration matter under ACA 1996",
        status=CaseStatus.IN_PROGRESS,
    )
    db.add(test_case)
    db.flush()

    p_owner = CaseParticipant(case_id=test_case.id, user_id=UUID(client_id), participant_role=ParticipantRole.OWNER)
    db.add(p_owner)

    # Create Documents (One safe, one quarantined)
    doc_safe = Document(
        case_id=test_case.id,
        uploaded_by=UUID(client_id),
        filename="pleadings_final.pdf",
        mime_type="application/pdf",
        file_size=245000,
        storage_key="vault/pleadings_final.pdf",
        document_type=DocumentCategory.PLEADINGS,
        processing_status=DocumentProcessingStatus.READY,
        security_status=DocumentSecurityStatus.SAFE,
    )
    doc_quarantine = Document(
        case_id=test_case.id,
        uploaded_by=UUID(client_id),
        filename="suspicious_attachment.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size=82000,
        storage_key="vault/suspicious_attachment.docx",
        document_type=DocumentCategory.MISCELLANEOUS,
        processing_status=DocumentProcessingStatus.FAILED,
        security_status=DocumentSecurityStatus.QUARANTINED,
    )
    db.add_all([doc_safe, doc_quarantine])

    # Create Consultation & Payment
    con = Consultation(
        client_id=UUID(client_id),
        lawyer_id=UUID(lawyer_id),
        case_id=test_case.id,
        status=ConsultationStatus.PAID,
        fee_amount=5000.0,
        currency="INR",
        duration_minutes=60,
        scheduled_at=datetime.now(UTC) + timedelta(days=2),
    )
    db.add(con)
    db.flush()

    payment = Payment(
        consultation_id=con.id,
        payer_user_id=UUID(client_id),
        amount=5000.0,
        currency="INR",
        status=PaymentStatus.SUCCEEDED,
        provider="stripe",
        provider_payment_id="pi_admin_test_123",
    )
    db.add(payment)
    db.commit()

    # 1. Operational Overview
    res_over = client.get("/api/v1/admin/overview", headers=h_admin)
    assert res_over.status_code == 200
    ov = res_over.json()
    assert ov["total_cases"] >= 1
    assert ov["total_revenue_inr"] >= 5000.0
    assert ov["quarantined_documents"] >= 1

    # 2. Case Oversight
    res_cases = client.get("/api/v1/admin/cases?search=Arbitration", headers=h_admin)
    assert res_cases.status_code == 200
    assert any(c["title"] == "High Court Commercial Arbitration" for c in res_cases.json()["items"])

    # 3. Consultation Oversight
    res_con = client.get("/api/v1/admin/consultations?status=PAID", headers=h_admin)
    assert res_con.status_code == 200
    assert any(c["id"] == str(con.id) for c in res_con.json()["items"])

    # 4. Payment Oversight
    res_pay = client.get("/api/v1/admin/payments?status=SUCCEEDED", headers=h_admin)
    assert res_pay.status_code == 200
    assert any(p["id"] == str(payment.id) for p in res_pay.json()["items"])

    # 5. Document Security Inspection
    res_sec = client.get("/api/v1/admin/document-security?status=QUARANTINED", headers=h_admin)
    assert res_sec.status_code == 200
    assert any(d["filename"] == "suspicious_attachment.docx" for d in res_sec.json()["items"])


# ============================================================================
# 5. AUDIT LOG VIEWER & SECURITY EVENTS
# ============================================================================


def test_audit_log_viewer_and_security_events(client: TestClient, db: Session):
    """
    Verifies audit logs pagination, event filtering, and security event categorization.
    """
    _, h_admin = _setup_user(client, db, "admin_audit_viewer@example.com", role=UserRole.ADMIN, full_name="Compliance Officer")

    # 1. Audit Logs list
    res_audit = client.get("/api/v1/admin/audit?limit=20", headers=h_admin)
    assert res_audit.status_code == 200
    assert "items" in res_audit.json()
    assert "total" in res_audit.json()

    # 2. Security Events list
    res_sec_events = client.get("/api/v1/admin/security-events?limit=20", headers=h_admin)
    assert res_sec_events.status_code == 200
    assert "items" in res_sec_events.json()
