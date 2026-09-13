import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AuthorizationError,
    ScannerUnavailableError,
    ValidationError,
)
from app.core.file_validation import (
    validate_file_magic_bytes,
    validate_filename_security,
)
from app.core.identifiers import generate_uuid7
from app.core.logging import SensitiveDataScrubberFilter
from app.core.security import create_access_token, hash_password
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole, ParticipantStatus
from app.models.court_case import CourtCase, UserFollowedCase
from app.models.document import Document, DocumentSecurityStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import AccountStatus, ClientProfile, User, UserRole
from app.domain.payments.payment_service import PaymentService
from app.domain.evidence.scanner_service import HeuristicSignatureScanner, ScannerService


def _create_client_user(db: Session, prefix: str) -> tuple[User, str]:
    uid = uuid.uuid4().hex[:6]
    user = User(
        id=generate_uuid7(),
        email=f"{prefix}_{uid}@example.com",
        password_hash=hash_password("SecurePassword123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    profile = ClientProfile(id=generate_uuid7(), user_id=user.id, full_name=f"User {prefix}")
    db.add(profile)
    db.commit()
    db.refresh(user)

    token = create_access_token(str(user.id), role=user.role.value)
    return user, token


def _create_court_case(db: Session) -> CourtCase:
    cnr_suffix = uuid.uuid4().hex[:8].upper()
    court_case = CourtCase(
        id=generate_uuid7(),
        cnr=f"DLHC{cnr_suffix}",
        case_number=f"W.P.(C) {uuid.uuid4().int % 9000 + 1000}/2024",
        case_type="Writ Petition (Civil)",
        court_name="High Court of Delhi",
        petitioner="Alpha Corp",
        respondent="Union of India",
        technical_status="Pending Hearing",
        human_status="Listed for preliminary hearing",
        source_provenance="OFFICIAL COURT DATA",
        sync_status="SYNCED",
    )
    db.add(court_case)
    db.commit()
    db.refresh(court_case)
    return court_case


# -----------------------------------------------------------------------------
# 1. BOLA / IDOR RESTRICTION ON COURT CASE LINKING
# -----------------------------------------------------------------------------


def test_court_case_link_matter_idor_protection(client: TestClient, db: Session):
    """Validates that User B cannot link a court case to User A's private matter (IDOR/BOLA)."""
    user_a, token_a = _create_client_user(db, "victim_a")
    user_b, token_b = _create_client_user(db, "attacker_b")

    # User A creates a matter
    matter_a = Case(
        id=generate_uuid7(),
        title="Victim A Private Case",
        description="Confidential dispute",
        status=CaseStatus.OPEN,
    )
    db.add(matter_a)
    db.flush()

    participant_a = CaseParticipant(
        id=generate_uuid7(),
        case_id=matter_a.id,
        user_id=user_a.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(participant_a)
    db.commit()

    court_case = _create_court_case(db)

    # ATTACK: Attacker B attempts to link CourtCase to Victim A's matter
    headers_b = {"Authorization": f"Bearer {token_b}"}
    res_attack = client.post(
        f"/api/v1/court-cases/{court_case.cnr}/link-matter",
        headers=headers_b,
        json={"case_id": str(matter_a.id)},
    )
    assert res_attack.status_code in [403, 404], f"Expected 403 Forbidden, got {res_attack.status_code}"

    # LEGITIMATE: Owner User A links CourtCase to Matter A
    headers_a = {"Authorization": f"Bearer {token_a}"}
    res_legit = client.post(
        f"/api/v1/court-cases/{court_case.cnr}/link-matter",
        headers=headers_a,
        json={"case_id": str(matter_a.id)},
    )
    assert res_legit.status_code == 200
    data = res_legit.json()
    assert data["case_id"] == str(matter_a.id)
    assert data["court_case_id"] == str(court_case.id)


# -----------------------------------------------------------------------------
# 2. USER SUBSCRIPTION ISOLATION ON COURT FOLLOW / UNFOLLOW
# -----------------------------------------------------------------------------


def test_user_followed_court_case_isolation(client: TestClient, db: Session):
    """Validates that User A following a court case does not leak follow state to User B."""
    user_a, token_a = _create_client_user(db, "follower_a")
    user_b, token_b = _create_client_user(db, "observer_b")
    court_case = _create_court_case(db)

    # User A follows
    res_follow = client.post(
        f"/api/v1/court-cases/{court_case.cnr}/follow",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_follow.status_code == 200
    assert res_follow.json()["is_followed"] is True

    # User B queries the case -> is_followed must be False
    res_detail_b = client.get(
        f"/api/v1/court-cases/{court_case.cnr}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_detail_b.status_code == 200
    assert res_detail_b.json()["is_followed"] is False

    # User B unfollows -> does not remove User A's follow record
    res_unfollow_b = client.delete(
        f"/api/v1/court-cases/{court_case.cnr}/follow",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_unfollow_b.status_code == 200
    assert res_unfollow_b.json()["is_followed"] is False

    # Verify User A is still following
    follow_record = (
        db.query(UserFollowedCase)
        .filter(
            UserFollowedCase.user_id == user_a.id,
            UserFollowedCase.court_case_id == court_case.id,
        )
        .first()
    )
    assert follow_record is not None


# -----------------------------------------------------------------------------
# 3. DOCUMENT SECURITY: MAGIC BYTES, PATH TRAVERSAL & MALICIOUS EXTENSIONS
# -----------------------------------------------------------------------------


def test_document_filename_and_magic_byte_security():
    """Validates filename traversal rejection, dangerous extensions, and magic byte enforcement."""
    # 1. Path traversal attempts
    with pytest.raises(ValidationError, match="path traversal"):
        validate_filename_security("../../etc/passwd.pdf")
    with pytest.raises(ValidationError, match="path traversal"):
        validate_filename_security("C:\\Windows\\System32\\cmd.exe")

    # 2. Executable / dangerous extensions
    with pytest.raises(ValidationError, match="prohibited for security"):
        validate_filename_security("malware.exe")
    with pytest.raises(ValidationError, match="prohibited for security"):
        validate_filename_security("script.sh")
    with pytest.raises(ValidationError, match="prohibited for security"):
        validate_filename_security("document.exe.pdf")

    # 3. Magic byte mismatch (Windows executable masquerading as PDF)
    fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00PE-Executable disguised as PDF"
    with pytest.raises(ValidationError, match=r"(?i)executable.*header"):
        validate_file_magic_bytes(fake_pdf, "application/pdf")

    # 4. Valid PDF magic bytes pass
    valid_pdf = b"%PDF-1.7\n%Legal document body\n%%EOF"
    validate_file_magic_bytes(valid_pdf, "application/pdf")


# -----------------------------------------------------------------------------
# 4. MALWARE SCANNER FAIL-CLOSED & HEURISTIC DETECTION
# -----------------------------------------------------------------------------


def test_malware_scanner_eicar_and_embedded_macros():
    """Validates heuristic detection of EICAR test signatures and embedded active scripts."""
    scanner = HeuristicSignatureScanner()

    # 1. EICAR test string
    eicar_content = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    is_safe, reason = scanner.scan_bytes(eicar_content, "eicar.com")
    assert is_safe is False
    assert "EICAR" in reason

    # 2. PDF with embedded JavaScript macro execution
    malicious_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Action /S /JavaScript /JS (app.alert('pwned');) >>\nendobj"
    is_safe_pdf, reason_pdf = scanner.scan_bytes(malicious_pdf, "brief.pdf")
    assert is_safe_pdf is False
    assert "JavaScript" in reason_pdf

    # 3. Clean PDF
    clean_pdf = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj"
    is_safe_clean, _ = scanner.scan_bytes(clean_pdf, "clean_evidence.pdf")
    assert is_safe_clean is True


class FailingScanner:
    """Mock scanner that simulates daemon timeout or network failure."""

    def scan_bytes(self, file_bytes: bytes, filename: str) -> tuple[bool, str | None]:
        raise ScannerUnavailableError("ClamAV socket timed out after 10.0s")


def test_scanner_fail_closed_quarantine(db: Session):
    """Validates that scanner failure leaves documents in QUARANTINED state rather than SAFE."""
    user, _ = _create_client_user(db, "quarantine_user")

    # Create dummy storage provider and save dummy file
    from app.core.storage import get_storage_provider
    storage = get_storage_provider()
    storage_key = f"test_docs/{uuid.uuid4().hex}.pdf"
    storage.put_object_bytes(storage_key, b"%PDF-1.7\nClean test content\n%%EOF", "application/pdf")

    case = Case(id=generate_uuid7(), title="Test Case", description="Desc", status=CaseStatus.OPEN)
    db.add(case)
    db.flush()

    doc = Document(
        id=generate_uuid7(),
        case_id=case.id,
        filename="affidavit.pdf",
        storage_key=storage_key,
        file_size=128,
        mime_type="application/pdf",
        uploaded_by=user.id,
        security_status=DocumentSecurityStatus.QUARANTINED,
    )
    db.add(doc)
    db.commit()

    failing_service = ScannerService(db, scanner=FailingScanner())
    with pytest.raises(ScannerUnavailableError):
        failing_service.scan_document(doc.id)

    db.refresh(doc)
    assert doc.security_status == DocumentSecurityStatus.QUARANTINED
    assert "unavailable" in (doc.processing_error or "").lower()


# -----------------------------------------------------------------------------
# 5. STRIPE WEBHOOK IDEMPOTENCY
# -----------------------------------------------------------------------------


def test_stripe_webhook_idempotency(db: Session):
    """Validates that duplicate Stripe webhook deliveries return already_processed without duplicate side effects."""
    user, _ = _create_client_user(db, "payer_user")
    client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()

    # Setup consultation and payment
    from app.models.consultation import Consultation, ConsultationStatus
    from app.models.user import LawyerProfile

    lawyer_user, _ = _create_client_user(db, "advocate_payment")
    lawyer_user.role = UserRole.LAWYER
    profile = LawyerProfile(
        id=generate_uuid7(),
        user_id=lawyer_user.id,
        full_name="Advocate Payment Test",
        consultation_fee=1500.0,
    )
    db.add(profile)
    db.flush()

    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_profile.id,
        lawyer_id=profile.id,
        scheduled_at=datetime.now(UTC) + timedelta(days=2),
        duration_minutes=30,
        fee_amount=1500.0,
        currency="INR",
        status=ConsultationStatus.ACCEPTED,
    )
    db.add(consultation)
    db.flush()

    payment = Payment(
        id=generate_uuid7(),
        consultation_id=consultation.id,
        payer_user_id=user.id,
        amount=1500.0,
        currency="INR",
        status=PaymentStatus.CREATED,
        provider="stripe",
        provider_payment_id=f"pi_test_{uuid.uuid4().hex[:12]}",
    )
    db.add(payment)
    db.commit()

    payment_service = PaymentService(db)

    # First webhook execution
    payload_dict = {
        "id": f"evt_test_{uuid.uuid4().hex[:8]}",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": payment.provider_payment_id}},
    }

    # Bypass HMAC signature verification by invoking internal handler directly with mock payload
    import json
    raw_payload = json.dumps(payload_dict).encode("utf-8")

    # Monkeypatch verify_stripe_webhook_signature
    import app.domain.payments.payment_service as ps_mod
    orig_verify = ps_mod.verify_stripe_webhook_signature
    ps_mod.verify_stripe_webhook_signature = lambda raw_payload, signature_header, secret: payload_dict
    try:
        res1 = payment_service.handle_webhook(raw_payload, signature_header="sig_test")
        assert res1["status"] == "success"

        db.refresh(payment)
        db.refresh(consultation)
        assert payment.status == PaymentStatus.SUCCEEDED
        assert consultation.status == ConsultationStatus.PAID

        # Second webhook execution (replay / duplicate webhook)
        res2 = payment_service.handle_webhook(raw_payload, signature_header="sig_test")
        assert res2["status"] == "already_processed"
    finally:
        ps_mod.verify_stripe_webhook_signature = orig_verify


# -----------------------------------------------------------------------------
# 6. SENSITIVE DATA SCRUBBER (LOG INTEGRITY)
# -----------------------------------------------------------------------------


def test_sensitive_data_scrubber_filter():
    """Validates that log messages scrub credentials, tokens, PAN, Aadhaar, Cards, and CNRs."""
    scrubber = SensitiveDataScrubberFilter()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg=(
            "User login with password: MySecretPass123! and Bearer eyJhbGciOi.token.sig. "
            "Client PAN ABCDE1234F and Aadhaar 1234 5678 9012 presented card 4111 1111 1111 1111 "
            "for court tracking CNR DLHC010044102023."
        ),
        args=(),
        exc_info=None,
    )

    scrubber.filter(record)
    msg = record.msg

    # Verify redactions
    assert "MySecretPass123!" not in msg
    assert "***REDACTED***" in msg
    assert "ABCDE1234F" not in msg
    assert "***REDACTED-PAN***" in msg
    assert "1234 5678 9012" not in msg
    assert "***REDACTED-AADHAAR***" in msg
    assert "4111 1111 1111 1111" not in msg
    assert "***REDACTED-CARD***" in msg
    assert "DLHC010044102023" not in msg
    assert "***REDACTED-CNR***" in msg
