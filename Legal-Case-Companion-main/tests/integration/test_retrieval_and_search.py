from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.models.ai import DocumentChunk
from app.models.case import CaseParticipant, ParticipantStatus
from app.models.document import (
    Document,
    DocumentCategory,
    DocumentProcessingStatus,
    DocumentSecurityStatus,
)
from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus


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
        enrollment_number=f"BAR/{str(lawyer_user_id)[:6]}/2021",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()
    db.refresh(profile)
    return profile


def _seed_document_with_chunks(
    db: Session,
    case_id: str,
    user_id: str,
    filename: str,
    category: DocumentCategory,
    version: int,
    chunks_data: list[tuple[str, list[float] | None, int]],
    security_status: DocumentSecurityStatus = DocumentSecurityStatus.SAFE,
) -> Document:
    doc = Document(
        id=generate_uuid7(),
        case_id=UUID(case_id),
        uploaded_by=UUID(user_id),
        filename=filename,
        storage_key=f"cases/{case_id}/documents/{filename}",
        mime_type="application/pdf",
        file_size=1024,
        security_status=security_status,
        processing_status=DocumentProcessingStatus.READY,
        document_type=category,
        version=version,
    )
    db.add(doc)
    db.flush()

    for idx, (content, embedding, page_num) in enumerate(chunks_data):
        chunk = DocumentChunk(
            id=generate_uuid7(),
            case_id=UUID(case_id),
            document_id=doc.id,
            content=content,
            embedding=embedding,
            metadata_={
                "chunk_index": idx,
                "page_start": page_num,
                "page_end": page_num,
                "page_number": page_num,
                "source_filename": filename,
                "document_version": version,
                "document_id": str(doc.id),
                "case_id": str(case_id),
            },
        )
        db.add(chunk)

    db.commit()
    db.refresh(doc)
    return doc


def test_lexical_retrieval_exact_legal_terms_and_citations(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "lex_owner@test.com", role="CLIENT")
    res_case = client.post("/api/v1/cases", json={"title": "Lexical Search Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    _seed_document_with_chunks(
        db,
        case_id,
        _owner_id,
        "cheque_dishonour_complaint.pdf",
        DocumentCategory.PLEADINGS,
        1,
        [
            ("The complainant filed this complaint under Section 138 of the Negotiable Instruments Act 1881.", None, 1),
            ("Cheque bearing No. 491022 dated 15th August 2024 for an amount of Rs. 2500000 was dishonoured due to insufficient funds.", None, 2),
            ("Legal notice was issued on 22nd August 2024 demanding payment within 15 days.", None, 3),
        ],
    )

    # 1. Search exact section reference in LEXICAL mode
    res_lex1 = client.post(
        f"/api/v1/cases/{case_id}/search",
        json={"query": "Section 138 Negotiable Instruments Act", "search_mode": "LEXICAL"},
        headers=h_owner,
    )
    assert res_lex1.status_code == 200
    data1 = res_lex1.json()
    assert data1["total_results"] >= 1
    top_result = data1["results"][0]
    assert "Section 138" in top_result["content"]
    assert top_result["lexical_score"] is not None and top_result["lexical_score"] > 0.6
    assert top_result["source_filename"] == "cheque_dishonour_complaint.pdf"
    assert top_result["page_start"] == 1

    # 2. Search exact cheque number & date
    res_lex2 = client.post(
        f"/api/v1/cases/{case_id}/search",
        json={"query": "491022 15th August 2024", "search_mode": "LEXICAL"},
        headers=h_owner,
    )
    assert res_lex2.status_code == 200
    data2 = res_lex2.json()
    assert data2["total_results"] >= 1
    assert "491022" in data2["results"][0]["content"]
    assert data2["results"][0]["page_start"] == 2


def test_semantic_and_hybrid_retrieval_ranking(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "sem_owner@test.com", role="CLIENT")
    res_case = client.post("/api/v1/cases", json={"title": "Hybrid Search Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    # In test environment, DeterministicMockEmbeddingProvider generates vectors based on word hashes
    # Let's seed chunks with semantic relevance
    _seed_document_with_chunks(
        db,
        case_id,
        _owner_id,
        "Commercial_Lease_Agreement.pdf",
        DocumentCategory.CONTRACT,
        1,
        [
            ("Lessor agrees to lease the office premises at Connaught Place to Lessee for 36 months.", None, 1),
            ("The monthly rental consideration shall be INR 150000 payable in advance by the 5th of each calendar month.", None, 2),
            ("Lessee shall furnish a refundable security deposit equal to six months of rent upon execution.", None, 3),
        ],
    )

    # Search with HYBRID mode
    res_hybrid = client.post(
        f"/api/v1/cases/{case_id}/search",
        json={"query": "monthly rental consideration payable", "search_mode": "HYBRID", "top_k": 5},
        headers=h_owner,
    )
    assert res_hybrid.status_code == 200
    data = res_hybrid.json()
    assert data["search_mode"] == "HYBRID"
    assert data["total_results"] >= 1

    top = data["results"][0]
    assert "rental consideration" in top["content"]
    assert top["score"] > 0
    assert top["document_category"] == "CONTRACT"
    assert top["document_version"] == 1


def test_category_and_document_id_filtering(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "filt_owner@test.com", role="CLIENT")
    res_case = client.post("/api/v1/cases", json={"title": "Filter Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    doc_contract = _seed_document_with_chunks(
        db, case_id, _owner_id, "contract.pdf", DocumentCategory.CONTRACT, 1,
        [("Non-disclosure agreement between parties.", None, 1)],
    )
    _seed_document_with_chunks(
        db, case_id, _owner_id, "evidence.pdf", DocumentCategory.EVIDENCE, 1,
        [("Bank statement showing wire transfer confirmation.", None, 1)],
    )

    # Filter by category = EVIDENCE
    res_cat = client.post(
        f"/api/v1/cases/{case_id}/search",
        json={"query": "agreement confirmation", "document_category": "EVIDENCE"},
        headers=h_owner,
    )
    assert res_cat.status_code == 200
    assert res_cat.json()["total_results"] == 1
    assert res_cat.json()["results"][0]["document_category"] == "EVIDENCE"

    # Filter by specific document_id
    res_doc = client.post(
        f"/api/v1/cases/{case_id}/search",
        json={"query": "agreement confirmation", "document_id": str(doc_contract.id)},
        headers=h_owner,
    )
    assert res_doc.status_code == 200
    assert res_doc.json()["total_results"] == 1
    assert res_doc.json()["results"][0]["document_id"] == str(doc_contract.id)


def test_security_authorization_and_cross_case_isolation(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "sec_search_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(client, "sec_search_lawyer@test.com", role="LAWYER", full_name="Adv. Kapoor")
    _verify_lawyer(db, lawyer_id)
    _other_id, h_other = _setup_user(client, "sec_search_other@test.com", role="CLIENT")

    # Case A
    res_case_a = client.post("/api/v1/cases", json={"title": "Case A", "description": "D"}, headers=h_owner)
    case_a_id = res_case_a.json()["id"]
    client.post(f"/api/v1/cases/{case_a_id}/participants", json={"user_id": lawyer_id, "participant_role": "LAWYER"}, headers=h_owner)

    # Case B
    res_case_b = client.post("/api/v1/cases", json={"title": "Case B", "description": "D"}, headers=h_other)
    case_b_id = res_case_b.json()["id"]

    _seed_document_with_chunks(
        db, case_a_id, _owner_id, "confidential_patent.pdf", DocumentCategory.EVIDENCE, 1,
        [("Secret proprietary algorithm formulas.", None, 1)],
    )

    # 1. Authorized owner can search Case A
    assert client.post(f"/api/v1/cases/{case_a_id}/search", json={"query": "algorithm"}, headers=h_owner).status_code == 200

    # 2. Authorized assigned lawyer can search Case A
    assert client.post(f"/api/v1/cases/{case_a_id}/search", json={"query": "algorithm"}, headers=h_lawyer).status_code == 200

    # 3. Unauthorized User B searching Case A -> 404
    assert client.post(f"/api/v1/cases/{case_a_id}/search", json={"query": "algorithm"}, headers=h_other).status_code == 404

    # 4. User B searching Case B (does not see Case A document) -> 0 results
    res_b = client.post(f"/api/v1/cases/{case_b_id}/search", json={"query": "algorithm"}, headers=h_other)
    assert res_b.status_code == 200
    assert res_b.json()["total_results"] == 0

    # 5. Revoked participant access cutoff
    participant = (
        db.query(CaseParticipant)
        .filter(CaseParticipant.case_id == UUID(case_a_id), CaseParticipant.user_id == UUID(lawyer_id))
        .first()
    )
    assert participant is not None
    participant.status = ParticipantStatus.INACTIVE
    db.commit()

    assert client.post(f"/api/v1/cases/{case_a_id}/search", json={"query": "algorithm"}, headers=h_lawyer).status_code in (403, 404)


def test_unsafe_documents_are_never_retrieved(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "unsafe_doc_owner@test.com", role="CLIENT")
    res_case = client.post("/api/v1/cases", json={"title": "Unsafe Doc Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    _seed_document_with_chunks(
        db, case_id, _owner_id, "quarantined.pdf", DocumentCategory.EVIDENCE, 1,
        [("Malicious payload attachment text.", None, 1)],
        security_status=DocumentSecurityStatus.QUARANTINED,
    )
    _seed_document_with_chunks(
        db, case_id, _owner_id, "rejected.pdf", DocumentCategory.EVIDENCE, 1,
        [("Virus infected legal document text.", None, 1)],
        security_status=DocumentSecurityStatus.REJECTED,
    )

    res = client.post(
        f"/api/v1/cases/{case_id}/search",
        json={"query": "infected payload malicious virus"},
        headers=h_owner,
    )
    assert res.status_code == 200
    assert res.json()["total_results"] == 0


def test_version_isolation_excludes_stale_versions(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "ver_iso_owner@test.com", role="CLIENT")
    res_case = client.post("/api/v1/cases", json={"title": "Version Iso Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    # Create document currently at version 2
    doc = Document(
        id=generate_uuid7(),
        case_id=UUID(case_id),
        uploaded_by=UUID(_owner_id),
        filename="settlement_terms.pdf",
        storage_key=f"cases/{case_id}/documents/settlement_terms.pdf",
        mime_type="application/pdf",
        file_size=1024,
        security_status=DocumentSecurityStatus.SAFE,
        processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.CONTRACT,
        version=2,  # Document is at v2
    )
    db.add(doc)
    db.flush()

    # Stale chunk with v1 metadata
    stale_chunk = DocumentChunk(
        id=generate_uuid7(),
        case_id=UUID(case_id),
        document_id=doc.id,
        content="Old draft: Party A pays 10000 INR settlement.",
        metadata_={"document_version": 1, "page_start": 1, "page_end": 1},
    )
    # Current chunk with v2 metadata
    current_chunk = DocumentChunk(
        id=generate_uuid7(),
        case_id=UUID(case_id),
        document_id=doc.id,
        content="Final terms: Party A pays 500000 INR settlement.",
        metadata_={"document_version": 2, "page_start": 1, "page_end": 1},
    )
    db.add(stale_chunk)
    db.add(current_chunk)
    db.commit()

    # Search for settlement
    res = client.post(
        f"/api/v1/cases/{case_id}/search",
        json={"query": "settlement", "search_mode": "LEXICAL"},
        headers=h_owner,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_results"] == 1
    assert "500000 INR" in data["results"][0]["content"]
    assert "10000 INR" not in data["results"][0]["content"]
    assert data["results"][0]["document_version"] == 2
