"""
Regression and security test suite for BUG-003:
Direct document upload security hardening, file signature validation,
quarantine lifecycle, ClamAV malware scanning, and fail-closed defense.
"""

import io
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import ScannerUnavailableError
from app.core.storage import get_storage_provider
from app.domain.evidence.scanner_service import EICAR_SIGNATURE
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole, ParticipantStatus
from app.models.document import Document, DocumentProcessingStatus, DocumentSecurityStatus
from app.models.user import User, UserRole
from app.domain.documents.document_processor import DocumentProcessor

VALID_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Title (Test Legal Document) >>\nendobj\ntrailer\n<< >>\n%%EOF"


def _create_test_user(client: TestClient, db: Session, email: str, role: UserRole = UserRole.CLIENT) -> tuple[str, dict[str, str]]:
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": role.value, "full_name": f"User {email}"},
    )
    assert reg_res.status_code == 201, reg_res.text
    user_id = reg_res.json()["id"]

    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def _create_case(db: Session, owner_id: UUID) -> Case:
    case = Case(
        title="Direct Upload Security Test Matter",
        description="Testing direct multipart upload security hardening.",
        status=CaseStatus.OPEN,
    )
    db.add(case)
    db.flush()

    participant = CaseParticipant(
        case_id=case.id,
        user_id=owner_id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(participant)
    db.commit()
    db.refresh(case)
    return case


def test_direct_upload_valid_file_workflow(client: TestClient, db: Session):
    """Verifies that a valid PDF passes magic byte checks, malware scanning, and is marked SAFE and READY."""
    user_id, headers = _create_test_user(client, db, f"valid_doc_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(user_id))

    files = {"file": ("affidavit.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")}
    data = {"title": "Sworn Affidavit", "category": "EVIDENCE", "description": "Client sworn affidavit"}

    res = client.post(f"/api/v1/cases/{case.id}/documents", headers=headers, files=files, data=data)
    assert res.status_code == 201, res.text
    doc_data = res.json()

    assert doc_data["filename"] == "Sworn Affidavit"
    assert doc_data["security_status"] == DocumentSecurityStatus.SAFE.value
    assert doc_data["processing_status"] == DocumentProcessingStatus.READY.value

    # SAFE document can be downloaded
    dl_res = client.get(f"/api/v1/cases/{case.id}/documents/{doc_data['id']}/download", headers=headers)
    assert dl_res.status_code == 200, dl_res.text
    assert "download_url" in dl_res.json()


def test_direct_upload_invalid_file_signature(client: TestClient, db: Session):
    """Verifies that a file pretending to be PDF but having non-PDF bytes is rejected with validation error."""
    user_id, headers = _create_test_user(client, db, f"invalidsig_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(user_id))

    corrupt_bytes = b"NOT_A_REAL_PDF_JUST_RANDOM_TEXT_BYTES"
    files = {"file": ("fake.pdf", io.BytesIO(corrupt_bytes), "application/pdf")}

    res = client.post(f"/api/v1/cases/{case.id}/documents", headers=headers, files=files)
    assert res.status_code in (400, 422), res.text
    assert "signature" in res.text.lower() or "spoofing" in res.text.lower()


def test_direct_upload_spoofed_mime_type_executable_rejected(client: TestClient, db: Session):
    """Verifies that Windows PE or Linux ELF executables disguised as legal documents are strictly blocked."""
    user_id, headers = _create_test_user(client, db, f"spoofexe_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(user_id))

    # Windows PE executable header
    pe_bytes = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
    files_pe = {"file": ("trojan.pdf", io.BytesIO(pe_bytes), "application/pdf")}
    res_pe = client.post(f"/api/v1/cases/{case.id}/documents", headers=headers, files=files_pe)
    assert res_pe.status_code in (400, 422)
    assert "executable" in res_pe.text.lower()

    # Linux ELF header
    elf_bytes = b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    files_elf = {"file": ("rootkit.pdf", io.BytesIO(elf_bytes), "application/pdf")}
    res_elf = client.post(f"/api/v1/cases/{case.id}/documents", headers=headers, files=files_elf)
    assert res_elf.status_code in (400, 422)
    assert "executable" in res_elf.text.lower()


def test_direct_upload_spoofed_content_type_mismatch(client: TestClient, db: Session):
    """Verifies that mismatched Content-Type header vs extension is rejected."""
    user_id, headers = _create_test_user(client, db, f"mismatch_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(user_id))

    # Extension says .pdf, but header claims image/png
    files = {"file": ("contract.pdf", io.BytesIO(VALID_PDF_BYTES), "image/png")}
    res = client.post(f"/api/v1/cases/{case.id}/documents", headers=headers, files=files)
    assert res.status_code in (400, 422)
    assert "does not match file extension" in res.text


def test_direct_upload_prohibited_extensions_and_path_traversal(client: TestClient, db: Session):
    """Verifies that dangerous extensions (.exe, .sh, .py, double extensions) and path traversal are rejected."""
    user_id, headers = _create_test_user(client, db, f"dangerousext_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(user_id))

    # Path traversal
    res_trav = client.post(
        f"/api/v1/cases/{case.id}/documents",
        headers=headers,
        files={"file": ("../../etc/passwd.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")},
    )
    assert res_trav.status_code in (400, 422)

    # Prohibited shell script extension
    res_sh = client.post(
        f"/api/v1/cases/{case.id}/documents",
        headers=headers,
        files={"file": ("script.sh", io.BytesIO(b"#!/bin/bash\necho 1"), "application/x-sh")},
    )
    assert res_sh.status_code in (400, 422)

    # Double extension trick (.pdf.exe)
    res_double = client.post(
        f"/api/v1/cases/{case.id}/documents",
        headers=headers,
        files={"file": ("invoice.pdf.exe", io.BytesIO(VALID_PDF_BYTES), "application/pdf")},
    )
    assert res_double.status_code in (400, 422)


def test_direct_upload_oversized_file(client: TestClient, db: Session):
    """Verifies that files exceeding MAX_FILE_SIZE_BYTES (10 MB) are rejected with HTTP 413 or 422/400."""
    user_id, headers = _create_test_user(client, db, f"oversize_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(user_id))

    # 10 MB + 1 byte
    oversized_bytes = b"%PDF-" + b"0" * (10 * 1024 * 1024)
    files = {"file": ("huge.pdf", io.BytesIO(oversized_bytes), "application/pdf")}
    res = client.post(f"/api/v1/cases/{case.id}/documents", headers=headers, files=files)
    assert res.status_code in (400, 413, 422)
    assert "exceeds" in res.text.lower() or "too large" in res.text.lower()


def test_direct_upload_malicious_eicar_virus_detected(client: TestClient, db: Session):
    """Verifies that a document containing malware test payload (EICAR) is detected by ScannerService,
    causes an HTTP security rejection, and cleans up the stored file bytes."""
    user_id, headers = _create_test_user(client, db, f"eicar_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(user_id))

    # Valid PDF magic bytes concatenated with EICAR antivirus test signature
    infected_pdf = b"%PDF-1.4 " + EICAR_SIGNATURE
    files = {"file": ("infected.pdf", io.BytesIO(infected_pdf), "application/pdf")}

    res = client.post(f"/api/v1/cases/{case.id}/documents", headers=headers, files=files)
    assert res.status_code in (400, 422)
    assert "security validation failed" in res.text.lower() or "eicar" in res.text.lower()

    # Verify that the document record in database is marked REJECTED and FAILED
    rejected_doc = db.query(Document).filter(Document.case_id == case.id, Document.filename == "infected.pdf").first()
    assert rejected_doc is not None
    assert rejected_doc.security_status == DocumentSecurityStatus.REJECTED
    assert rejected_doc.processing_status == DocumentProcessingStatus.FAILED

    # Verify storage object cleanup
    storage = get_storage_provider()
    assert not storage.object_exists(rejected_doc.storage_key)


def test_direct_upload_clamav_unavailable_fails_closed(client: TestClient, db: Session):
    """Verifies fail-closed quarantine behavior when ClamAV or malware scanning service is unavailable."""
    user_id, headers = _create_test_user(client, db, f"clamav_down_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(user_id))

    files = {"file": ("unscanned.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")}

    # Simulate scanner daemon unavailability / socket timeout
    with patch("app.domain.evidence.scanner_service.ScannerService.scan_document") as mock_scan:
        mock_scan.side_effect = ScannerUnavailableError("ClamAV daemon at localhost:3310 unreachable")

        res = client.post(f"/api/v1/cases/{case.id}/documents", headers=headers, files=files)
        assert res.status_code == 201, res.text
        doc_data = res.json()

        # Document MUST NOT be SAFE or READY — it must remain locked in QUARANTINED state
        assert doc_data["security_status"] == DocumentSecurityStatus.QUARANTINED.value
        assert doc_data["processing_status"] == DocumentProcessingStatus.PENDING.value

        # Attempting to download a QUARANTINED document MUST return HTTP 403 Forbidden
        dl_res = client.get(f"/api/v1/cases/{case.id}/documents/{doc_data['id']}/download", headers=headers)
        assert dl_res.status_code == 403
        assert "not approved for download" in dl_res.text.lower()


def test_direct_upload_scanner_timeout_fails_closed(client: TestClient, db: Session):
    """Verifies that scanner timeouts fail closed into QUARANTINED status and block access."""
    user_id, headers = _create_test_user(client, db, f"timeout_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(user_id))

    files = {"file": ("timed_out.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")}

    with patch("app.domain.evidence.scanner_service.ScannerService.scan_document") as mock_scan:
        mock_scan.side_effect = ScannerUnavailableError("ClamAV socket timed out after 10.0s")

        res = client.post(f"/api/v1/cases/{case.id}/documents", headers=headers, files=files)
        assert res.status_code == 201
        doc_data = res.json()
        assert doc_data["security_status"] == DocumentSecurityStatus.QUARANTINED.value

        # Quarantined document cannot be downloaded
        dl_res = client.get(f"/api/v1/cases/{case.id}/documents/{doc_data['id']}/download", headers=headers)
        assert dl_res.status_code == 403


def test_direct_upload_unauthorized_user_blocked(client: TestClient, db: Session):
    """Verifies that users who are not participants in a case cannot upload documents to it (anti-enumeration 403/404)."""
    user_id, _ = _create_test_user(client, db, f"owner_{uuid4().hex[:6]}@example.com")
    _, attacker_headers = _create_test_user(client, db, f"attacker_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(user_id))

    files = {"file": ("unauth.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")}
    res = client.post(f"/api/v1/cases/{case.id}/documents", headers=attacker_headers, files=files)
    assert res.status_code in (403, 404)


def test_direct_upload_unauthorized_download_blocked(client: TestClient, db: Session):
    """Verifies that users who have no access to a case cannot download its SAFE documents (anti-enumeration 403/404)."""
    user_id, owner_headers = _create_test_user(client, db, f"case_owner_{uuid4().hex[:6]}@example.com")
    _, attacker_headers = _create_test_user(client, db, f"unauth_dl_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(user_id))

    # Owner uploads valid document
    files = {"file": ("secret.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")}
    upload_res = client.post(f"/api/v1/cases/{case.id}/documents", headers=owner_headers, files=files)
    doc_id = upload_res.json()["id"]

    # Attacker tries to download owner's document
    dl_res = client.get(f"/api/v1/cases/{case.id}/documents/{doc_id}/download", headers=attacker_headers)
    assert dl_res.status_code in (403, 404)


def test_direct_upload_duplicate_upload_isolation(client: TestClient, db: Session):
    """Verifies that uploading the exact same file content twice creates two isolated, distinct document records."""
    user_id, headers = _create_test_user(client, db, f"duplicate_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(user_id))

    files1 = {"file": ("contract.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")}
    res1 = client.post(f"/api/v1/cases/{case.id}/documents", headers=headers, files=files1)
    assert res1.status_code == 201
    doc1 = res1.json()

    files2 = {"file": ("contract.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")}
    res2 = client.post(f"/api/v1/cases/{case.id}/documents", headers=headers, files=files2)
    assert res2.status_code == 201
    doc2 = res2.json()

    assert doc1["id"] != doc2["id"]
    assert doc1["storage_key"] != doc2["storage_key"]


def test_quarantined_document_processing_worker_safety(db: Session):
    """Verifies that DocumentProcessor.process_document refuses to process any document that is not SAFE."""
    user = User(
        email=f"proc_safety_{uuid4().hex[:6]}@example.com",
        password_hash="fakehash",
        role=UserRole.CLIENT,
    )
    db.add(user)
    db.flush()

    case = Case(
        title="Processing Safety Matter",
        description="Testing worker safety on quarantined documents.",
        status=CaseStatus.OPEN,
    )
    db.add(case)
    db.flush()

    # Create a quarantined document
    quarantined_doc = Document(
        case_id=case.id,
        uploaded_by=user.id,
        filename="quarantined.pdf",
        storage_key=f"cases/{case.id}/documents/{uuid4()}_quarantined.pdf",
        mime_type="application/pdf",
        file_size=len(VALID_PDF_BYTES),
        security_status=DocumentSecurityStatus.QUARANTINED,
        processing_status=DocumentProcessingStatus.PENDING,
    )
    db.add(quarantined_doc)
    db.commit()
    db.refresh(quarantined_doc)

    processor = DocumentProcessor(db)
    chunks = processor.process_document(quarantined_doc.id)

    # Must abort processing and return 0 chunks
    assert chunks == []
    db.refresh(quarantined_doc)
    assert quarantined_doc.processing_status == DocumentProcessingStatus.PENDING


def test_quarantine_bounded_retry_and_exhaustion_monitoring(client: TestClient, db: Session):
    """Verifies that quarantined documents retry up to max_retries, and then fail closed with failure monitoring."""
    from app.domain.evidence.scanner_service import ScannerService, ScannerUnavailableError

    user_id, headers = _create_test_user(client, db, f"retrydoc_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(user_id))

    storage = get_storage_provider()
    key = f"cases/{case.id}/documents/{uuid4()}_test.pdf"
    storage.put_object_bytes(key, VALID_PDF_BYTES, "application/pdf")

    doc = Document(
        case_id=case.id,
        uploaded_by=UUID(user_id),
        filename="retry_test.pdf",
        storage_key=key,
        mime_type="application/pdf",
        file_size=len(VALID_PDF_BYTES),
        security_status=DocumentSecurityStatus.QUARANTINED,
        processing_status=DocumentProcessingStatus.PENDING,
    )
    db.add(doc)
    db.commit()

    class MockUnavailableScanner:
        def scan_bytes(self, file_bytes, filename):
            raise ScannerUnavailableError("ClamAV socket timeout")

    scanner_svc = ScannerService(db, scanner=MockUnavailableScanner())

    # Retries 1 and 2: scanner unavailable, attempts increment
    res1 = scanner_svc.retry_quarantined_documents(max_retries=3)
    assert res1["retry_failed"] >= 1
    db.refresh(doc)
    assert doc.security_status == DocumentSecurityStatus.QUARANTINED
    assert "attempt 1" in doc.processing_error

    res2 = scanner_svc.retry_quarantined_documents(max_retries=3)
    db.refresh(doc)
    assert "attempt 2" in doc.processing_error

    res3 = scanner_svc.retry_quarantined_documents(max_retries=3)
    db.refresh(doc)
    assert "attempt 3" in doc.processing_error

    # Attempt 4 exceeds max_retries (3): marked exhausted
    res4 = scanner_svc.retry_quarantined_documents(max_retries=3)
    db.refresh(doc)
    assert res4["exhausted"] >= 1
    assert "retry limit reached" in doc.processing_error.lower()


def test_quarantined_document_preview_pages_and_chunks_blocked(client: TestClient, db: Session):
    """Verifies that quarantined documents cannot have pages or chunks previewed/accessed."""
    from app.domain.documents.document_service import DocumentService
    from app.core.exceptions import AuthorizationError

    user_id, headers = _create_test_user(client, db, f"quar_preview_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(user_id))

    doc = Document(
        case_id=case.id,
        uploaded_by=UUID(user_id),
        filename="quarantined_preview.pdf",
        storage_key=f"cases/{case.id}/documents/{uuid4()}_preview.pdf",
        mime_type="application/pdf",
        file_size=len(VALID_PDF_BYTES),
        security_status=DocumentSecurityStatus.QUARANTINED,
        processing_status=DocumentProcessingStatus.PENDING,
    )
    db.add(doc)
    db.commit()

    doc_service = DocumentService(db)
    user = db.query(User).filter(User.id == UUID(user_id)).first()

    with pytest.raises(AuthorizationError):
        doc_service.get_document_pages(user, doc.id, case_id=case.id)

    with pytest.raises(AuthorizationError):
        doc_service.get_document_chunks(user, doc.id, case_id=case.id)


def test_confidential_document_access_restricted_from_standard_viewer(client: TestClient, db: Session):
    """Verifies that confidential documents are restricted from standard VIEWER participants."""
    from app.core.authorization import authorize_document_access
    from app.core.exceptions import AuthorizationError

    owner_id, owner_headers = _create_test_user(client, db, f"owner_{uuid4().hex[:6]}@example.com")
    viewer_id, viewer_headers = _create_test_user(client, db, f"viewer_{uuid4().hex[:6]}@example.com")
    case = _create_case(db, UUID(owner_id))

    # Add viewer to case
    viewer_part = CaseParticipant(
        case_id=case.id,
        user_id=UUID(viewer_id),
        participant_role=ParticipantRole.VIEWER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(viewer_part)

    # Confidential document
    confidential_doc = Document(
        case_id=case.id,
        uploaded_by=UUID(owner_id),
        filename="privileged_notes.pdf",
        storage_key=f"cases/{case.id}/documents/{uuid4()}_priv.pdf",
        mime_type="application/pdf",
        file_size=len(VALID_PDF_BYTES),
        security_status=DocumentSecurityStatus.SAFE,
        processing_status=DocumentProcessingStatus.READY,
        is_confidential=True,
    )
    db.add(confidential_doc)
    db.commit()

    owner_user = db.query(User).filter(User.id == UUID(owner_id)).first()
    viewer_user = db.query(User).filter(User.id == UUID(viewer_id)).first()

    # Owner can access
    assert authorize_document_access(db, owner_user, confidential_doc.id, case_id=case.id) is not None

    # Viewer is denied access
    with pytest.raises(AuthorizationError):
        authorize_document_access(db, viewer_user, confidential_doc.id, case_id=case.id)

