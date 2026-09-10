import io
from uuid import UUID

import docx
import pypdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import get_storage_provider
from app.models.document import (
    Document,
    DocumentProcessingStatus,
    DocumentSecurityStatus,
)
from app.models.document_page import DocumentPage
from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus
from app.services.document_processor import DocumentProcessor


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "dummy-test-key"
    yield
    settings.OPENAI_API_KEY = original_key


def _setup_user(
    client: TestClient,
    email: str,
    password: str = "SecurePassword123!",
    role: str = "CLIENT",
    full_name: str = "Test User",
):
    """Register and authenticate a user."""
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


def _verify_lawyer(db: Session, lawyer_user_id: str):
    profile = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == UUID(lawyer_user_id))
        .first()
    )
    assert profile is not None
    ver = LawyerVerification(
        lawyer_profile_id=profile.id,
        enrollment_number=f"BAR/{str(lawyer_user_id)[:6]}/2020",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()
    db.refresh(profile)
    return profile


def _create_sample_pdf_bytes() -> bytes:
    """Generates a 2-page valid PDF with known text."""
    writer = pypdf.PdfWriter()
    # Page 1
    writer.add_blank_page(width=300, height=300)
    buf = io.BytesIO()
    writer.write(buf)
    # Construct a real PDF with text in content stream
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R /Resources << /Font << /F1 7 0 R >> >> >> endobj\n"
        b"4 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >> endobj\n"
        b"5 0 obj << /Length 58 >> stream\nBT /F1 12 Tf 72 712 Td (Section 1: Commercial lease between Lessor and Lessee.) Tj ET\nendstream\nendobj\n"
        b"6 0 obj << /Length 55 >> stream\nBT /F1 12 Tf 72 712 Td (Section 2: Monthly rental consideration is 75000 INR.) Tj ET\nendstream\nendobj\n"
        b"7 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"xref\n0 8\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000224 00000 n \n0000000333 00000 n \n0000000441 00000 n \n0000000546 00000 n \ntrailer << /Size 8 /Root 1 0 R >>\nstartxref\n623\n%%EOF"
    )
    return pdf_content


def _create_sample_docx_bytes() -> bytes:
    """Generates a valid DOCX file with paragraphs and a table."""
    doc = docx.Document()
    doc.add_heading("Employment Agreement", level=1)
    doc.add_paragraph("This employment contract is entered into on 1st January 2026.")
    doc.add_paragraph("Employee agrees to maintain strict confidentiality of all client data.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Designation"
    table.cell(0, 1).text = "Senior Legal Counsel"
    table.cell(1, 0).text = "Remuneration"
    table.cell(1, 1).text = "1200000 INR per annum"
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_pdf_page_level_extraction_and_provenance(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "pdf_extr_owner@test.com", role="CLIENT")

    # 1. Create Case
    res_case = client.post("/api/v1/cases", json={"title": "PDF Extraction Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    pdf_bytes = _create_sample_pdf_bytes()

    # 2. Upload PDF
    res_up = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "Lease_Contract_2026.pdf",
            "mime_type": "application/pdf",
            "file_size": len(pdf_bytes),
            "document_type": "CONTRACT",
            "description": "Commercial lease",
        },
        headers=h_owner,
    )
    assert res_up.status_code == 201
    doc_id = res_up.json()["document"]["id"]
    storage_key = res_up.json()["document"]["storage_key"]

    # Put bytes in storage
    storage = get_storage_provider()
    storage.put_object_bytes(storage_key, pdf_bytes, "application/pdf")

    # 3. Mark SAFE
    doc = db.query(Document).filter(Document.id == UUID(doc_id)).first()
    assert doc is not None
    doc.security_status = DocumentSecurityStatus.SAFE
    db.commit()

    # 4. Trigger processing via DocumentProcessor
    processor = DocumentProcessor(db)
    chunks = processor.process_document(UUID(doc_id), generate_embeddings=False)

    assert len(chunks) >= 2

    # Check Document metadata updated
    db.refresh(doc)
    assert doc.processing_status == DocumentProcessingStatus.READY
    assert doc.page_count == 2
    assert doc.word_count is not None and doc.word_count > 0
    assert doc.character_count is not None and doc.character_count > 0
    assert doc.processed_at is not None

    # Check DocumentPage records in DB
    pages = db.query(DocumentPage).filter(DocumentPage.document_id == UUID(doc_id)).order_by(DocumentPage.page_number.asc()).all()
    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert "Section 1" in pages[0].text
    assert pages[1].page_number == 2
    assert "Section 2" in pages[1].text

    # Check Chunk Provenance
    for c in chunks:
        assert c.metadata_["document_id"] == doc_id
        assert c.metadata_["case_id"] == case_id
        assert c.metadata_["source_filename"] == "Lease_Contract_2026.pdf"
        assert c.metadata_["document_version"] == 1
        assert "page_start" in c.metadata_
        assert "page_end" in c.metadata_


def test_docx_and_txt_extraction(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "docx_txt_owner@test.com", role="CLIENT")
    res_case = client.post("/api/v1/cases", json={"title": "Docx Txt Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    storage = get_storage_provider()

    # 1. Test DOCX
    docx_bytes = _create_sample_docx_bytes()
    res_docx = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "Employment_Agreement.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "file_size": len(docx_bytes),
            "document_type": "CONTRACT",
        },
        headers=h_owner,
    )
    assert res_docx.status_code == 201
    docx_id = res_docx.json()["document"]["id"]
    storage.put_object_bytes(res_docx.json()["document"]["storage_key"], docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    doc_docx = db.query(Document).filter(Document.id == UUID(docx_id)).first()
    doc_docx.security_status = DocumentSecurityStatus.SAFE
    db.commit()

    processor = DocumentProcessor(db)
    docx_chunks = processor.process_document(UUID(docx_id), generate_embeddings=False)
    assert len(docx_chunks) > 0

    db.refresh(doc_docx)
    assert doc_docx.processing_status == DocumentProcessingStatus.READY
    assert doc_docx.page_count == 1

    # 2. Test TXT
    txt_bytes = b"Clause 1: Arbitration shall take place in New Delhi.\n\nClause 2: Governing law is the Laws of India."
    res_txt = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "arbitration.txt", "mime_type": "text/plain", "file_size": len(txt_bytes)},
        headers=h_owner,
    )
    assert res_txt.status_code == 201
    txt_id = res_txt.json()["document"]["id"]
    storage.put_object_bytes(res_txt.json()["document"]["storage_key"], txt_bytes, "text/plain")

    doc_txt = db.query(Document).filter(Document.id == UUID(txt_id)).first()
    doc_txt.security_status = DocumentSecurityStatus.SAFE
    db.commit()

    txt_chunks = processor.process_document(UUID(txt_id), generate_embeddings=False)
    assert len(txt_chunks) > 0
    db.refresh(doc_txt)
    assert doc_txt.processing_status == DocumentProcessingStatus.READY
    assert doc_txt.word_count > 0


def test_unsupported_and_image_ocr_required_states(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "ocr_req_owner@test.com", role="CLIENT")
    res_case = client.post("/api/v1/cases", json={"title": "OCR Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    storage = get_storage_provider()

    # Image upload -> OCR_REQUIRED
    img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    res_img = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "evidence_photo.png", "mime_type": "image/png", "file_size": len(img_bytes)},
        headers=h_owner,
    )
    img_id = res_img.json()["document"]["id"]
    storage.put_object_bytes(res_img.json()["document"]["storage_key"], img_bytes, "image/png")

    doc_img = db.query(Document).filter(Document.id == UUID(img_id)).first()
    doc_img.security_status = DocumentSecurityStatus.SAFE
    db.commit()

    processor = DocumentProcessor(db)
    res_chunks = processor.process_document(UUID(img_id), generate_embeddings=False)
    assert len(res_chunks) == 0

    db.refresh(doc_img)
    assert doc_img.processing_status == DocumentProcessingStatus.OCR_REQUIRED
    assert "OCR pipeline" in (doc_img.processing_error or "")


def test_corrupted_and_empty_document_handling(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "corrupt_owner@test.com", role="CLIENT")
    res_case = client.post("/api/v1/cases", json={"title": "Corrupt Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    storage = get_storage_provider()

    # 1. Corrupted PDF
    corrupt_bytes = b"%PDF-1.4\n broken garbage \x00\xff\xfe\xca\xfe"
    res_c = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "corrupt.pdf", "mime_type": "application/pdf", "file_size": len(corrupt_bytes)},
        headers=h_owner,
    )
    c_id = res_c.json()["document"]["id"]
    storage.put_object_bytes(res_c.json()["document"]["storage_key"], corrupt_bytes, "application/pdf")

    doc_c = db.query(Document).filter(Document.id == UUID(c_id)).first()
    doc_c.security_status = DocumentSecurityStatus.SAFE
    db.commit()

    processor = DocumentProcessor(db)
    processor.process_document(UUID(c_id), generate_embeddings=False)
    db.refresh(doc_c)
    assert doc_c.processing_status in (DocumentProcessingStatus.CORRUPTED_FILE, DocumentProcessingStatus.EMPTY_DOCUMENT)

    # 2. Empty Text file
    empty_bytes = b"    \n   \t  \n "
    res_e = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "empty.txt", "mime_type": "text/plain", "file_size": len(empty_bytes)},
        headers=h_owner,
    )
    e_id = res_e.json()["document"]["id"]
    storage.put_object_bytes(res_e.json()["document"]["storage_key"], empty_bytes, "text/plain")

    doc_e = db.query(Document).filter(Document.id == UUID(e_id)).first()
    doc_e.security_status = DocumentSecurityStatus.SAFE
    db.commit()

    processor.process_document(UUID(e_id), generate_embeddings=False)
    db.refresh(doc_e)
    assert doc_e.processing_status == DocumentProcessingStatus.EMPTY_DOCUMENT


def test_processing_idempotency_and_retry(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "idem_owner@test.com", role="CLIENT")
    res_case = client.post("/api/v1/cases", json={"title": "Idempotency Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    storage = get_storage_provider()
    txt_bytes = b"Paragraph 1: Legal disclaimer.\n\nParagraph 2: Confidential settlement terms."
    res_txt = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "settlement.txt", "mime_type": "text/plain", "file_size": len(txt_bytes)},
        headers=h_owner,
    )
    doc_id = res_txt.json()["document"]["id"]
    storage.put_object_bytes(res_txt.json()["document"]["storage_key"], txt_bytes, "text/plain")

    doc = db.query(Document).filter(Document.id == UUID(doc_id)).first()
    doc.security_status = DocumentSecurityStatus.SAFE
    db.commit()

    processor = DocumentProcessor(db)

    # Run 1
    chunks1 = processor.process_document(UUID(doc_id), generate_embeddings=False)
    pages1 = db.query(DocumentPage).filter(DocumentPage.document_id == UUID(doc_id)).all()
    count_chunks1 = len(chunks1)
    count_pages1 = len(pages1)

    # Run 2 (Retry)
    chunks2 = processor.process_document(UUID(doc_id), generate_embeddings=False)
    pages2 = db.query(DocumentPage).filter(DocumentPage.document_id == UUID(doc_id)).all()
    count_chunks2 = len(chunks2)
    count_pages2 = len(pages2)

    assert count_chunks1 == count_chunks2
    assert count_pages1 == count_pages2 == 1


def test_version_protection_and_stale_job_guard(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "ver_guard_owner@test.com", role="CLIENT")
    res_case = client.post("/api/v1/cases", json={"title": "Version Guard Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    storage = get_storage_provider()
    txt_bytes = b"Version 1 content"
    res_txt = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "doc_v1.txt", "mime_type": "text/plain", "file_size": len(txt_bytes)},
        headers=h_owner,
    )
    doc_id = res_txt.json()["document"]["id"]
    storage.put_object_bytes(res_txt.json()["document"]["storage_key"], txt_bytes, "text/plain")

    doc = db.query(Document).filter(Document.id == UUID(doc_id)).first()
    doc.security_status = DocumentSecurityStatus.SAFE
    doc.version = 2  # Simulating that document version bumped to 2
    db.commit()

    processor = DocumentProcessor(db)
    # Stale job running for expected_version=1
    stale_result = processor.process_document(UUID(doc_id), expected_version=1, generate_embeddings=False)
    assert len(stale_result) == 0


def test_document_processing_api_endpoints_and_bola(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "api_proc_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(client, "api_proc_lawyer@test.com", role="LAWYER", full_name="Adv. Bannerjee")
    _verify_lawyer(db, lawyer_id)
    _other_id, h_other = _setup_user(client, "api_proc_other@test.com", role="CLIENT")

    # Case A
    res_case = client.post("/api/v1/cases", json={"title": "API Proc Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]
    client.post(f"/api/v1/cases/{case_id}/participants", json={"user_id": lawyer_id, "participant_role": "LAWYER"}, headers=h_owner)

    # Case B
    res_case_b = client.post("/api/v1/cases", json={"title": "Other Case", "description": "D"}, headers=h_other)
    case_b_id = res_case_b.json()["id"]

    storage = get_storage_provider()
    txt_bytes = b"Section 1: Initial claim.\n\nSection 2: Counter claim details."
    res_doc = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "claim.txt", "mime_type": "text/plain", "file_size": len(txt_bytes)},
        headers=h_owner,
    )
    doc_id = res_doc.json()["document"]["id"]
    storage.put_object_bytes(res_doc.json()["document"]["storage_key"], txt_bytes, "text/plain")

    # 1. Processing trigger before SAFE -> 422
    assert client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/process", headers=h_owner).status_code == 422

    # Mark SAFE
    doc = db.query(Document).filter(Document.id == UUID(doc_id)).first()
    doc.security_status = DocumentSecurityStatus.SAFE
    db.commit()

    # 2. Trigger processing via POST /cases/{case_id}/documents/{doc_id}/process
    res_proc = client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/process", headers=h_lawyer)
    assert res_proc.status_code == 200
    p_status = res_proc.json()
    assert p_status["processing_status"] == "READY"
    assert p_status["page_count"] == 1
    assert p_status["chunk_count"] > 0

    # 3. GET /cases/{case_id}/documents/{doc_id}/processing-status
    res_st = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/processing-status", headers=h_owner)
    assert res_st.status_code == 200
    assert res_st.json()["processing_status"] == "READY"

    # 4. GET /cases/{case_id}/documents/{doc_id}/pages
    res_pages = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/pages", headers=h_lawyer)
    assert res_pages.status_code == 200
    assert len(res_pages.json()["items"]) == 1
    assert "Section 1" in res_pages.json()["items"][0]["text"]

    # 5. GET /cases/{case_id}/documents/{doc_id}/chunks
    res_chunks = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/chunks", headers=h_lawyer)
    assert res_chunks.status_code == 200
    assert len(res_chunks.json()["items"]) > 0

    # 6. BOLA Protections: Other user querying Case A doc -> 404
    assert client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/processing-status", headers=h_other).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/pages", headers=h_other).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/chunks", headers=h_other).status_code == 404
    assert client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/process", headers=h_other).status_code == 404

    # 7. Cross-case URL protection
    assert client.get(f"/api/v1/cases/{case_b_id}/documents/{doc_id}/processing-status", headers=h_other).status_code == 404
