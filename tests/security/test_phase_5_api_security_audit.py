from datetime import UTC, datetime
from decimal import Decimal
import io
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConfigurationError
from app.core.identifiers import generate_uuid7
from app.core.security import create_access_token, hash_password
from app.models.commercial import CommercialTransaction, TransactionStatus
from app.models.consultation import Consultation, ConsultationStatus
from app.models.operator import OperationalPermission
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.domain.payments.commercial_service import CommercialService
from app.domain.consultations.video_meeting_service import InternalWebRTCMeetingProvider, VideoMeetingService
from app.domain.consultations.video_recording_service import VideoRecordingService

VALID_PDF_BYTES = b"%PDF-1.5\n%Security test document\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


def _create_user(
    db: Session,
    prefix: str,
    role: UserRole,
) -> tuple[User, str]:
    uid = uuid.uuid4().hex[:6]
    user = User(
        email=f"{prefix}_{uid}@example.com",
        password_hash=hash_password("SecurePass123!"),
        role=role,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    if role == UserRole.CLIENT:
        profile = ClientProfile(user_id=user.id, full_name=f"Client {prefix.capitalize()}")
        db.add(profile)
    elif role == UserRole.LAWYER:
        profile = LawyerProfile(
            user_id=user.id,
            full_name=f"Advocate {prefix.capitalize()}",
            practice_areas=["Litigation"],
            court_jurisdictions=["Supreme Court"],
            languages=["English"],
            experience_years=10,
            consultation_fee=2000.0,
        )
        db.add(profile)
        db.flush()
        verif = LawyerVerification(
            lawyer_profile_id=profile.id,
            enrollment_number=f"D/{uuid.uuid4().hex[:4].upper()}/2020",
            state_bar_council="Bar Council of Delhi",
            status=VerificationStatus.APPROVED,
        )
        db.add(verif)

    db.commit()
    db.refresh(user)
    token = create_access_token(subject=str(user.id), role=user.role.value)
    return user, token


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. Test Payment Gating in Production / When Disabled (SEC-01)
# ==============================================================================

def test_pay_test_blocked_in_production_and_when_disabled(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
):
    """Verifies that /pay-test is strictly forbidden in production or when test payments are disabled."""
    client_user, client_token = _create_user(db, "pay_client", UserRole.CLIENT)
    lawyer_user, _ = _create_user(db, "pay_lawyer", UserRole.LAWYER)

    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_user.client_profile.id,
        lawyer_id=lawyer_user.lawyer_profile.id,
        scheduled_at=datetime.now(UTC),
        duration_minutes=30,
        fee_amount=1500.0,
        currency="INR",
        status=ConsultationStatus.ACCEPTED,
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)

    # Case A: ENABLE_TEST_PAYMENTS is False
    monkeypatch.setattr(settings, "ENABLE_TEST_PAYMENTS", False)
    res = client.post(
        f"/api/v1/consultations/{consultation.id}/pay-test",
        headers=_headers(client_token),
    )
    assert res.status_code == 403
    assert "disabled" in res.text.lower()

    # Case B: ENVIRONMENT is production
    monkeypatch.setattr(settings, "ENABLE_TEST_PAYMENTS", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    res = client.post(
        f"/api/v1/consultations/{consultation.id}/pay-test",
        headers=_headers(client_token),
    )
    assert res.status_code == 403
    assert "disabled" in res.text.lower()

    # Case C: In development with ENABLE_TEST_PAYMENTS = True, it succeeds
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "ENABLE_TEST_PAYMENTS", True)
    res = client.post(
        f"/api/v1/consultations/{consultation.id}/pay-test",
        headers=_headers(client_token),
    )
    assert res.status_code == 200
    assert res.json()["status"] == "PAID"


# ==============================================================================
# 2. Mock Storage Production Gating and Traversal Guards (SEC-02)
# ==============================================================================

def test_mock_storage_blocked_in_production_and_staging(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    """Verifies that /mock-storage routes return 404 in production and staging."""
    for env in ("production", "staging"):
        monkeypatch.setattr(settings, "ENVIRONMENT", env)
        # Upload attempt
        res_up = client.put("/mock-storage/upload?key=test.pdf", content=b"content")
        assert res_up.status_code == 404, f"Upload did not 404 in {env}"

        # Download attempt
        res_down = client.get("/mock-storage/download?key=test.pdf")
        assert res_down.status_code == 404, f"Download did not 404 in {env}"


def test_mock_storage_rejects_path_traversal_keys(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    """Verifies that /mock-storage routes reject path traversal patterns with 400 Bad Request."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    # Traversal with ..
    res_traversal = client.get("/mock-storage/download?key=../../etc/passwd")
    assert res_traversal.status_code == 400
    assert "Invalid storage key" in res_traversal.text

    # Traversal with leading slash
    res_abs = client.get("/mock-storage/download?key=/root/secret")
    assert res_abs.status_code == 400

    # Upload with ..
    res_up = client.put("/mock-storage/upload?key=../../../etc/cron.d/job", content=b"evil")
    assert res_up.status_code == 400


# ==============================================================================
# 3. Commercial Tax Invoice Receipt IDOR Prevention (SEC-03)
# ==============================================================================

def test_commercial_receipt_idor_prevention(client: TestClient, db: Session):
    """Verifies that unauthorized users cannot access another party's commercial invoice receipt."""
    payer_user, payer_token = _create_user(db, "payer_client", UserRole.CLIENT)
    payee_user, payee_token = _create_user(db, "payee_lawyer", UserRole.LAWYER)
    unauth_user, unauth_token = _create_user(db, "unauth_client", UserRole.CLIENT)
    admin_user, admin_token = _create_user(db, "admin_user", UserRole.ADMIN)

    # Create transaction
    txn_id = f"TXN-SEC-{uuid.uuid4().hex[:8].upper()}"
    txn = CommercialTransaction(
        transaction_id=txn_id,
        consultation_id=uuid.uuid4(),
        payer_user_id=payer_user.id,
        payee_user_id=payee_user.id,
        gross_amount=Decimal("2000.00"),
        platform_fee=Decimal("200.00"),
        tax_amount=Decimal("36.00"),
        net_advocate_amount=Decimal("1764.00"),
        currency="INR",
        status=TransactionStatus.CAPTURED,
        invoice_number=f"INV-SEC-{uuid.uuid4().hex[:6].upper()}",
    )
    db.add(txn)
    db.commit()

    # 1. Unauthorized third party should be blocked with 403 Forbidden
    res_unauth = client.get(
        f"/api/v1/commercial/invoices/{txn_id}/receipt",
        headers=_headers(unauth_token),
    )
    assert res_unauth.status_code == 403
    assert "Not authorized" in res_unauth.text

    # 2. Payer (client) has legitimate access
    res_payer = client.get(
        f"/api/v1/commercial/invoices/{txn_id}/receipt",
        headers=_headers(payer_token),
    )
    assert res_payer.status_code == 200
    data = res_payer.json()
    assert data["gross_amount"] == 2000.0
    assert data["currency"] == "INR"

    # 3. Payee (advocate) has legitimate access
    res_payee = client.get(
        f"/api/v1/commercial/invoices/{txn_id}/receipt",
        headers=_headers(payee_token),
    )
    assert res_payee.status_code == 200

    # 4. Administrator has legitimate access
    res_admin = client.get(
        f"/api/v1/commercial/invoices/{txn_id}/receipt",
        headers=_headers(admin_token),
    )
    assert res_admin.status_code == 200


# ==============================================================================
# 4. Compliance Scorecard Authorization & Operator Scoping (SEC-04)
# ==============================================================================

def test_compliance_scorecard_requires_operator_auth(client: TestClient, db: Session):
    """Verifies that /compliance/scorecard rejects unauthenticated and non-operator users."""
    # 1. Unauthenticated request -> 401
    res_anon = client.get("/api/v1/compliance/scorecard")
    assert res_anon.status_code == 401

    # 2. Authenticated non-operator client -> 403
    client_user, client_token = _create_user(db, "non_op_client", UserRole.CLIENT)
    res_client = client.get("/api/v1/compliance/scorecard", headers=_headers(client_token))
    assert res_client.status_code == 403

    # 3. Authenticated admin -> 200
    admin_user, admin_token = _create_user(db, "comp_admin", UserRole.ADMIN)
    res_admin = client.get("/api/v1/compliance/scorecard", headers=_headers(admin_token))
    assert res_admin.status_code == 200
    assert "technical_readiness_pct" in res_admin.json()


# ==============================================================================
# 5. Administrative Verification Decision RBAC Route Guarding (SEC-05)
# ==============================================================================

def test_verification_admin_endpoints_require_admin_role(client: TestClient, db: Session):
    """Verifies that administrative verification endpoints reject non-admin users at the route layer."""
    client_user, client_token = _create_user(db, "verif_client", UserRole.CLIENT)
    lawyer_user, lawyer_token = _create_user(db, "verif_lawyer", UserRole.LAWYER)

    dummy_verif_id = uuid.uuid4()

    # Client calling admin queue -> 403
    res_q = client.get("/api/v1/verification/admin/queue", headers=_headers(client_token))
    assert res_q.status_code == 403

    # Lawyer calling admin queue -> 403
    res_lq = client.get("/api/v1/verification/admin/queue", headers=_headers(lawyer_token))
    assert res_lq.status_code == 403

    # Client calling start-review canonical endpoint -> 403
    res_sr = client.post(
        f"/api/v1/verification/admin/{dummy_verif_id}/start-review",
        json={},
        headers=_headers(client_token),
    )
    assert res_sr.status_code == 403

    # Lawyer calling start-review legacy alias endpoint -> 403
    res_alias = client.post(
        f"/api/v1/verification/{dummy_verif_id}/start-review",
        json={},
        headers=_headers(lawyer_token),
    )
    assert res_alias.status_code == 403


# ==============================================================================
# 6. Video Signing Secret Fallback Gating in Staging & Production (SEC-06)
# ==============================================================================

def test_video_secret_fallback_rejected_in_staging(monkeypatch: pytest.MonkeyPatch):
    """Verifies that missing signing secrets raise ConfigurationError in staging as well as production."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(settings, "CSRF_SECRET_KEY", "mock-secret-for-dev")
    monkeypatch.setattr(settings, "JWT_PRIVATE_KEY", "")

    with pytest.raises(ConfigurationError, match="Missing production cryptographic secret"):
        InternalWebRTCMeetingProvider._get_signing_secret()

    with pytest.raises(ConfigurationError, match="Missing production cryptographic secret"):
        VideoRecordingService._get_signing_secret()


# ==============================================================================
# 7. Consultation Document Upload Filename Sanitization (SEC-08)
# ==============================================================================

def test_consultation_document_upload_sanitization(client: TestClient, db: Session):
    """Verifies that consultation document uploads reject path traversal and dangerous extensions."""
    client_user, client_token = _create_user(db, "upload_client", UserRole.CLIENT)
    lawyer_user, _ = _create_user(db, "upload_lawyer", UserRole.LAWYER)

    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_user.client_profile.id,
        lawyer_id=lawyer_user.lawyer_profile.id,
        scheduled_at=datetime.now(UTC),
        duration_minutes=30,
        fee_amount=1500.0,
        currency="INR",
        status=ConsultationStatus.ACCEPTED,
    )
    db.add(consultation)
    db.commit()

    # Attempt upload with path traversal filename
    files = {"file": ("../../evil.sh", io.BytesIO(VALID_PDF_BYTES), "application/pdf")}
    res_traversal = client.post(
        f"/api/v1/consultations/{consultation.id}/documents",
        files=files,
        headers=_headers(client_token),
    )
    assert res_traversal.status_code in (400, 422)

    # Attempt upload with executable extension
    files_exe = {"file": ("payload.exe", io.BytesIO(VALID_PDF_BYTES), "application/pdf")}
    res_exe = client.post(
        f"/api/v1/consultations/{consultation.id}/documents",
        files=files_exe,
        headers=_headers(client_token),
    )
    assert res_exe.status_code in (400, 422)


# ==============================================================================
# 8. Calendar Events Authentication Guard (SEC-09)
# ==============================================================================

def test_calendar_events_requires_authentication(client: TestClient, db: Session):
    """Verifies that /api/v1/calendar/events strictly requires authentication."""
    # Anonymous -> 401
    res_anon = client.get("/api/v1/calendar/events")
    assert res_anon.status_code == 401

    # Authenticated client -> 200
    user, token = _create_user(db, "cal_test_user", UserRole.CLIENT)
    res_authed = client.get("/api/v1/calendar/events", headers=_headers(token))
    assert res_authed.status_code == 200
    assert "events" in res_authed.json()
