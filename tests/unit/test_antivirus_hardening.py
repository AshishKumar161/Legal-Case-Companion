import socket
import uuid
from unittest.mock import MagicMock, patch
import pytest

from app.core.config import settings
from app.core.exceptions import AuthorizationError, ScannerUnavailableError
from app.domain.documents.document_service import DocumentService
from app.domain.evidence.scanner_service import (
    ClamAVScanner,
    DefaultMalwareScanner,
    HeuristicSignatureScanner,
    ScannerService,
)
from app.models.case import Case, CaseParticipant, ParticipantRole, ParticipantStatus
from app.models.document import (
    Document,
    DocumentCategory,
    DocumentProcessingStatus,
    DocumentSecurityStatus,
)
from app.models.user import User, UserRole


def test_heuristic_scanner_detects_eicar_and_executable_headers():
    scanner = HeuristicSignatureScanner()
    # EICAR
    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    is_safe, reason = scanner.scan_bytes(eicar, "test.pdf")
    assert not is_safe
    assert "EICAR" in reason

    # PE Executable header
    mz_bytes = b"MZ\x90\x00\x03\x00\x00\x00"
    is_safe, reason = scanner.scan_bytes(mz_bytes, "invoice.exe")
    assert not is_safe
    assert "Executable" in reason

    # Clean text
    clean_bytes = b"Legal contract agreement clause."
    is_safe, reason = scanner.scan_bytes(clean_bytes, "agreement.pdf")
    assert is_safe
    assert reason is None


def test_production_clamav_unconfigured_fails_closed(monkeypatch):
    """In production, ClamAV is strictly required; missing host must raise ScannerUnavailableError."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    scanner = ClamAVScanner(host=None)
    with pytest.raises(ScannerUnavailableError) as exc_info:
        scanner.scan_bytes(b"Normal clean document bytes", "clean.pdf")
    assert "ClamAV daemon host is not configured" in str(exc_info.value)


def test_production_heuristic_only_cannot_certify_safe(monkeypatch):
    """In production, heuristic scanner alone must not certify files as SAFE if ClamAV host is unset."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    composite = DefaultMalwareScanner()
    composite.clamav_scanner.host = None

    clean_file = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    with pytest.raises(ScannerUnavailableError) as exc_info:
        composite.scan_bytes(clean_file, "clean.pdf")
    assert "cannot independently certify files" in str(exc_info.value)


def test_clamav_socket_timeout_fails_closed(monkeypatch):
    """ClamAV socket timeout must fail closed and raise ScannerUnavailableError."""
    scanner = ClamAVScanner(host="127.0.0.1", port=3310)

    def mock_socket_timeout(*args, **kwargs):
        sock = MagicMock()
        sock.__enter__.return_value = sock
        sock.connect.side_effect = socket.timeout("Connection timed out")
        return sock

    monkeypatch.setattr(socket, "socket", mock_socket_timeout)

    with pytest.raises(ScannerUnavailableError) as exc:
        scanner.scan_bytes(b"some bytes", "file.pdf")
    assert "timed out" in str(exc.value)


def test_scan_document_retry_bounding_and_exhaustion(db, monkeypatch):
    """Verifies that transient failures keep file QUARANTINED, and exceeding retries fails closed to REJECTED."""
    user = User(
        id=uuid.uuid4(),
        email=f"scanner_test_{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.LAWYER,
    )
    db.add(user)
    db.flush()

    case = Case(
        id=uuid.uuid4(),
        title="Quarantine Retry Case",
        description="Testing retry bounding.",
    )
    db.add(case)
    db.flush()

    doc = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        uploaded_by=user.id,
        filename="test_contract.pdf",
        storage_key=f"keys/{uuid.uuid4()}",
        mime_type="application/pdf",
        file_size=1024,
        document_type=DocumentCategory.CONTRACT,
        version=1,
        security_status=DocumentSecurityStatus.QUARANTINED,
        processing_status=DocumentProcessingStatus.READY,
    )
    db.add(doc)
    db.commit()

    failing_scanner = MagicMock()
    failing_scanner.scan_bytes.side_effect = ScannerUnavailableError("Connection refused by daemon")

    service = ScannerService(db, scanner=failing_scanner)
    service.storage.get_object_bytes = lambda key: b"%PDF-1.4\nLegal Text\n%%EOF"

    monkeypatch.setattr(settings, "MALWARE_SCAN_MAX_RETRIES", 3)

    # Attempt 1: Fails, stays QUARANTINED, attempt 1 recorded
    with pytest.raises(ScannerUnavailableError):
        service.scan_document(doc.id)
    db.refresh(doc)
    assert doc.security_status == DocumentSecurityStatus.QUARANTINED
    assert "attempt 1/3" in doc.processing_error

    # Attempt 2: Fails, stays QUARANTINED, attempt 2 recorded
    with pytest.raises(ScannerUnavailableError):
        service.scan_document(doc.id)
    db.refresh(doc)
    assert doc.security_status == DocumentSecurityStatus.QUARANTINED
    assert "attempt 2/3" in doc.processing_error

    # Attempt 3: Fails, stays QUARANTINED, attempt 3 recorded
    with pytest.raises(ScannerUnavailableError):
        service.scan_document(doc.id)
    db.refresh(doc)
    assert doc.security_status == DocumentSecurityStatus.QUARANTINED
    assert "attempt 3/3" in doc.processing_error

    # Retry exhaustion: retry_quarantined_documents marks retry limit reached and keeps file quarantined
    res = service.retry_quarantined_documents(max_retries=3)
    assert res["exhausted"] >= 1
    db.refresh(doc)
    assert doc.security_status == DocumentSecurityStatus.QUARANTINED
    assert "retry limit reached" in doc.processing_error.lower()


def test_rejected_and_quarantined_documents_inaccessible(db):
    """Verifies that non-SAFE documents cannot generate presigned download URLs."""
    user = User(
        id=uuid.uuid4(),
        email=f"access_tester_{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.LAWYER,
    )
    db.add(user)
    db.flush()

    case = Case(
        id=uuid.uuid4(),
        title="Inaccessible Doc Case",
        description="Testing security access control.",
    )
    db.add(case)
    db.flush()

    part = CaseParticipant(
        id=uuid.uuid4(),
        case_id=case.id,
        user_id=user.id,
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(part)

    rejected_doc = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        uploaded_by=user.id,
        filename="malware.pdf",
        storage_key=f"keys/{uuid.uuid4()}",
        mime_type="application/pdf",
        file_size=1024,
        document_type=DocumentCategory.CONTRACT,
        version=1,
        security_status=DocumentSecurityStatus.REJECTED,
        processing_status=DocumentProcessingStatus.READY,
    )
    db.add(rejected_doc)
    db.commit()

    doc_service = DocumentService(db)
    with pytest.raises(AuthorizationError) as exc:
        doc_service.generate_download_url(user, rejected_doc.id, case_id=case.id)
    assert "not approved for download" in str(exc.value)

    # Document preview pages must also be blocked
    with pytest.raises(AuthorizationError) as exc_prev:
        doc_service.get_document_pages(user, rejected_doc.id, case_id=case.id)
    assert "cannot be previewed while in quarantine" in str(exc_prev.value)


def test_quarantined_evidence_version_cannot_be_previewed_or_downloaded(db):
    """Verifies that EvidenceService get_view_url and get_download_url reject unverified/quarantined versions."""
    from app.core.exceptions import ValidationError
    from app.domain.evidence.evidence_service import EvidenceService
    from app.models.evidence import Evidence, EvidenceVersion, EvidenceScanStatus

    user = User(
        id=uuid.uuid4(),
        email=f"preview_sec_{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.LAWYER,
    )
    db.add(user)
    db.flush()

    case = Case(
        id=uuid.uuid4(),
        title="Quarantine Evidence Case",
        description="Testing evidence preview boundary.",
    )
    db.add(case)
    db.flush()

    part = CaseParticipant(
        id=uuid.uuid4(),
        case_id=case.id,
        user_id=user.id,
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(part)

    evidence = Evidence(
        id=uuid.uuid4(),
        case_id=case.id,
        created_by_user_id=user.id,
        title="Quarantined Exhibit",
        original_filename="suspicious_contract.pdf",
    )
    db.add(evidence)
    db.flush()

    ver = EvidenceVersion(
        id=uuid.uuid4(),
        evidence_id=evidence.id,
        version_number=1,
        uploaded_by_user_id=user.id,
        storage_key=f"evidence/{uuid.uuid4()}",
        original_filename="suspicious_contract.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        scan_status=EvidenceScanStatus.PENDING,
    )
    db.add(ver)
    db.flush()
    evidence.current_version_id = ver.id
    db.commit()

    service = EvidenceService(db)

    # 1. get_view_url MUST reject quarantined evidence
    with pytest.raises(ValidationError) as exc_view:
        service.get_view_url(user, case.id, evidence.id, ver.id)
    assert "Cannot preview unverified or quarantined evidence" in str(exc_view.value)

    # 2. get_download_url MUST reject quarantined evidence
    with pytest.raises(ValidationError) as exc_dl:
        service.get_download_url(user, case.id, evidence.id, ver.id)
    assert "Cannot download unverified or quarantined evidence" in str(exc_dl.value)


def test_authorized_manual_quarantine_reprocessing(db):
    """Verifies that an administrator can manually reprocess an exhausted quarantined document."""
    admin_user = User(
        id=uuid.uuid4(),
        email=f"admin_{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.ADMIN,
    )
    unauthorized_user = User(
        id=uuid.uuid4(),
        email=f"client_{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.CLIENT,
    )
    db.add_all([admin_user, unauthorized_user])
    db.flush()

    case = Case(
        id=uuid.uuid4(),
        title="Quarantine Reprocess Case",
        description="Manual reprocessing test",
    )
    db.add(case)
    db.flush()

    doc = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        uploaded_by=admin_user.id,
        filename="exhausted_contract.pdf",
        storage_key=f"keys/{uuid.uuid4()}",
        mime_type="application/pdf",
        file_size=1024,
        document_type=DocumentCategory.CONTRACT,
        version=1,
        security_status=DocumentSecurityStatus.QUARANTINED,
        processing_status=DocumentProcessingStatus.READY,
        processing_error="Quarantine scan retry limit reached (3/3). Document quarantined indefinitely.",
    )
    db.add(doc)
    db.commit()

    clean_scanner = MagicMock()
    clean_scanner.scan_bytes.return_value = (True, None)

    service = ScannerService(db, scanner=clean_scanner)
    service.storage.get_object_bytes = lambda key: b"%PDF-1.4\nClean Legal Text\n%%EOF"

    # 1. Non-admin user rejected with AuthorizationError
    with pytest.raises(AuthorizationError) as auth_err:
        service.reprocess_quarantined_document(doc.id, unauthorized_user, force=True)
    assert "Only administrators" in str(auth_err.value)

    # 2. Admin successfully reprocesses
    reprocessed = service.reprocess_quarantined_document(doc.id, admin_user, force=True)
    assert reprocessed.security_status == DocumentSecurityStatus.SAFE
    assert reprocessed.processing_error is None


def test_manual_quarantine_reprocessing_maintains_fail_closed(db):
    """Verifies fail-closed behavior: if scanner is unavailable, document remains QUARANTINED."""
    admin_user = User(
        id=uuid.uuid4(),
        email=f"admin_fail_{uuid.uuid4().hex[:8]}@example.com",
        role=UserRole.ADMIN,
    )
    db.add(admin_user)
    db.flush()

    case = Case(id=uuid.uuid4(), title="Fail Closed Case", description="Fail closed test")
    db.add(case)
    db.flush()

    doc = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        uploaded_by=admin_user.id,
        filename="fail_closed.pdf",
        storage_key=f"keys/{uuid.uuid4()}",
        mime_type="application/pdf",
        file_size=1024,
        document_type=DocumentCategory.CONTRACT,
        version=1,
        security_status=DocumentSecurityStatus.QUARANTINED,
        processing_status=DocumentProcessingStatus.READY,
        processing_error="Quarantine scan retry limit reached",
    )
    db.add(doc)
    db.commit()

    failing_scanner = MagicMock()
    failing_scanner.scan_bytes.side_effect = ScannerUnavailableError("ClamAV daemon offline")

    service = ScannerService(db, scanner=failing_scanner)
    service.storage.get_object_bytes = lambda key: b"%PDF-1.4\nTest\n%%EOF"

    with pytest.raises(ScannerUnavailableError):
        service.reprocess_quarantined_document(doc.id, admin_user, force=True)

    db.refresh(doc)
    # Must remain QUARANTINED (fail-closed)
    assert doc.security_status == DocumentSecurityStatus.QUARANTINED


def test_operational_alerts_for_clamav_and_quarantine_backlog(db, monkeypatch):
    """Verifies that AlertService fires alerts when ClamAV is unavailable or quarantined docs accumulate."""
    from app.domain.notifications.alert_service import AlertService

    # 1. ClamAV unavailable alert test
    monkeypatch.setattr(settings, "CLAMAV_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "CLAMAV_PORT", 9999)  # closed port

    alert_svc = AlertService(db)
    alerts = alert_svc.evaluate_alerts()
    clamav_alert = next((a for a in alerts if a["alert_id"] == "ALERT-CLAMAV-UNAVAILABLE"), None)
    assert clamav_alert is not None
    assert clamav_alert["status"] == "FIRING"

    # 2. Quarantined documents accumulation alert test
    # Seed 10 quarantined documents
    case = Case(id=uuid.uuid4(), title="Alert Case", description="Alert test")
    user = User(id=uuid.uuid4(), email=f"user_{uuid.uuid4().hex[:6]}@test.com", role=UserRole.LAWYER)
    db.add_all([case, user])
    db.flush()

    docs = []
    for i in range(10):
        docs.append(
            Document(
                id=uuid.uuid4(),
                case_id=case.id,
                uploaded_by=user.id,
                filename=f"quarantined_{i}.pdf",
                storage_key=f"keys/{uuid.uuid4()}",
                mime_type="application/pdf",
                file_size=1024,
                document_type=DocumentCategory.CONTRACT,
                version=1,
                security_status=DocumentSecurityStatus.QUARANTINED,
                processing_status=DocumentProcessingStatus.READY,
            )
        )
    db.bulk_save_objects(docs)
    db.commit()

    alerts_after_seed = alert_svc.evaluate_alerts()
    quarantine_alert = next((a for a in alerts_after_seed if a["alert_id"] == "ALERT-QUARANTINE-ACCUMULATION"), None)
    assert quarantine_alert is not None
    assert quarantine_alert["status"] == "FIRING"
    assert quarantine_alert["current_value"] >= 10


def test_kyc_document_storage_key_object_authorization(db):
    """Verifies that a user cannot submit a KYC document storage key belonging to another user."""
    from app.api.v1.kyc import ClientKYCSubmitRequest, submit_client_kyc
    from fastapi import Request

    victim_user = User(
        id=uuid.uuid4(),
        email=f"victim_{uuid.uuid4().hex[:6]}@test.com",
        role=UserRole.CLIENT,
    )
    attacker_user = User(
        id=uuid.uuid4(),
        email=f"attacker_{uuid.uuid4().hex[:6]}@test.com",
        role=UserRole.CLIENT,
    )
    db.add_all([victim_user, attacker_user])
    db.commit()

    # Attacker tries to submit victim's storage key
    stolen_key = f"kyc/{victim_user.id}/confidential_passport.pdf"
    req_payload = ClientKYCSubmitRequest(
        full_name="Attacker Name",
        phone="9876543210",
        id_type="AADHAAR",
        id_number="123456789012",
        address="123 MG Road",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
        kyc_document_storage_key=stolen_key,
        kyc_document_filename="passport.pdf",
        dpdp_consent=True,
    )

    mock_request = MagicMock(spec=Request)
    with pytest.raises(AuthorizationError) as exc_info:
        submit_client_kyc(
            request=mock_request,
            payload=req_payload,
            current_user=attacker_user,
            db=db,
        )
    assert "does not belong to the authenticated user" in str(exc_info.value)


