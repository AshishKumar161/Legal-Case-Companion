import datetime
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.models.ai import DocumentChunk
from app.models.document import (
    Document,
    DocumentCategory,
    DocumentProcessingStatus,
    DocumentSecurityStatus,
)
from app.models.legal_authority import (
    LegalAuthorityType,
    LegalJurisdiction,
    LegalSource,
    LegalSourceVersion,
)
from app.models.user import User
from app.schemas.assistant import CaseAssistantQueryRequest, GroundingStatus
from app.schemas.legal_authority import (
    LegalAuthoritySearchRequest,
)
from app.services.assistant_service import CaseAssistantService
from app.services.legal_authority_ingestion import LegalAuthorityIngestionService
from app.services.legal_authority_retrieval import LegalAuthorityRetrievalService
from app.services.llm_provider import MockLLMProvider
from tests.fixtures.curated_legal_authorities import CURATED_STATUTES


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "dummy-test-key"
    yield
    settings.OPENAI_API_KEY = original_key


def _setup_user(client: TestClient, email: str, role: str = "CLIENT"):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": role, "full_name": "Test User"},
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seed_curated_authorities(db: Session):
    """Seeds curated Indian statutes and judgments into the test database."""
    service = LegalAuthorityIngestionService(db)
    for stat in CURATED_STATUTES:
        service.ingest_legal_authority(stat)
    return CURATED_STATUTES


def test_idempotent_legal_authority_ingestion(client: TestClient, db: Session):
    """Verifies that ingesting the same canonical statute multiple times updates without creating duplicates."""
    service = LegalAuthorityIngestionService(db)
    ni_act = CURATED_STATUTES[0]

    # Ingest first time
    resp1 = service.ingest_legal_authority(ni_act)
    assert resp1.canonical_identifier == "IN-ACT-1881-26"
    assert len(resp1.provisions) == 3

    count_sources_1 = db.query(LegalSource).filter(LegalSource.canonical_identifier == "IN-ACT-1881-26").count()
    count_provisions_1 = db.query(LegalSourceVersion).filter(LegalSourceVersion.source_id == resp1.id).count()
    assert count_sources_1 == 1
    assert count_provisions_1 == 3

    # Ingest second time with updated provision title
    ni_act_updated = ni_act.model_copy(deep=True)
    ni_act_updated.provisions[0].title = "Updated Section 138 Title"
    resp2 = service.ingest_legal_authority(ni_act_updated)
    assert resp2.id == resp1.id

    count_sources_2 = db.query(LegalSource).filter(LegalSource.canonical_identifier == "IN-ACT-1881-26").count()
    count_provisions_2 = db.query(LegalSourceVersion).filter(LegalSourceVersion.source_id == resp2.id).count()
    assert count_sources_2 == 1
    assert count_provisions_2 == 3

    updated_prov = db.query(LegalSourceVersion).filter(LegalSourceVersion.canonical_provision_id == "IN-ACT-1881-26-SEC-138-ORIG").first()
    assert updated_prov.title == "Updated Section 138 Title"


def test_temporal_validity_retrieval(db: Session, seed_curated_authorities):
    """Verifies that temporal cutoff queries return the historical provision active on that date."""
    service = LegalAuthorityRetrievalService(db)

    # 1. Historical query at 2000-01-01 -> Should retrieve 1988 Original Provision (1 year imprisonment)
    req_historical = LegalAuthoritySearchRequest(
        query="punishment for cheque dishonour under section 138",
        effective_at=datetime.date(2000, 1, 1),
    )
    res_hist = service.search_legal_authorities(req_historical)
    assert res_hist.total_results >= 1
    top_hist = res_hist.results[0]
    assert top_hist.canonical_provision_id == "IN-ACT-1881-26-SEC-138-ORIG"
    assert "one year" in top_hist.content

    # 2. Current query at 2024-01-01 -> Should retrieve 2018 Amended Provision (2 years imprisonment)
    req_current = LegalAuthoritySearchRequest(
        query="punishment for cheque dishonour under section 138",
        effective_at=datetime.date(2024, 1, 1),
    )
    res_curr = service.search_legal_authorities(req_current)
    assert res_curr.total_results >= 1
    top_curr = res_curr.results[0]
    assert top_curr.canonical_provision_id == "IN-ACT-1881-26-SEC-138-V2018"
    assert "two years" in top_curr.content


def test_citation_normalization_and_exact_match(db: Session, seed_curated_authorities):
    """Verifies that searching by informal citation boosts and accurately retrieves the exact section."""
    service = LegalAuthorityRetrievalService(db)

    # Search for "Section 27 of Contract Act" (Agreement in restraint of trade)
    req = LegalAuthoritySearchRequest(query="Section 27 of Contract Act restraint of trade")
    res = service.search_legal_authorities(req)
    assert res.total_results >= 1
    top = res.results[0]
    assert top.canonical_provision_id == "IN-ACT-1872-9-SEC-27-CURR"
    assert top.section_number == "27"
    assert "restraint of trade" in top.title.lower()


def test_jurisdiction_and_judicial_precedent_retrieval(db: Session, seed_curated_authorities):
    """Verifies that judicial decisions from the Supreme Court are categorized and retrieved."""
    service = LegalAuthorityRetrievalService(db)

    req = LegalAuthoritySearchRequest(
        query="unilateral appointment of sole arbitrator invalid",
        jurisdiction=LegalJurisdiction.SUPREME_COURT_OF_INDIA.value,
        source_type=LegalAuthorityType.JUDICIAL_DECISION,
    )
    res = service.search_legal_authorities(req)
    assert res.total_results >= 1
    top = res.results[0]
    assert top.canonical_identifier == "IN-SC-2020-20-SCC-760"
    assert top.source_type == LegalAuthorityType.JUDICIAL_DECISION
    assert "Perkins Eastman" in top.name


def test_dual_source_ai_assistant_integration(client: TestClient, db: Session, seed_curated_authorities):
    """Verifies that the AI Assistant can retrieve and synthesize both case evidence and statutory legal authorities."""
    user_id, headers = _setup_user(client, "asst_dual_user@test.com", role="CLIENT")
    res_case = client.post("/api/v1/cases", json={"title": "Cheque Bounce Case", "description": "Section 138 dispute"}, headers=headers)
    case_id = res_case.json()["id"]

    # Seed case evidence document
    doc = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Cheque_Memo.pdf", storage_key="k_memo", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.EVIDENCE, version=1,
    )
    db.add(doc)
    db.flush()

    chunk = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc.id,
        content="Return memo dated 14th May 2024 for Cheque No. 102931 drawn on HDFC Bank returned unpaid due to funds insufficient.",
        metadata_={"page_start": 1, "page_end": 1, "document_version": 1, "source_filename": doc.filename},
    )
    db.add(chunk)
    db.commit()

    # Query assistant with include_legal_authority=True
    res = client.post(
        f"/api/v1/cases/{case_id}/assistant/query",
        json={
            "question": "What is the penalty for cheque bounce under Section 138 of NI Act based on the cheque memo?",
            "include_legal_authority": True,
            "top_k": 5,
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["grounding_status"] == GroundingStatus.SUPPORTED.value

    # Check case citations
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["source_filename"] == "Cheque_Memo.pdf"

    # Check legal authority citations
    assert len(data["authority_citations"]) >= 1
    auth_cit = data["authority_citations"][0]
    assert auth_cit["canonical_identifier"] == "IN-ACT-1881-26"
    assert "138" in auth_cit["canonical_provision_id"]
    assert auth_cit["jurisdiction"] == "INDIA_CENTRAL"

    # Check claims
    assert len(data["claims"]) >= 1


def test_unverified_authority_citation_dropped(client: TestClient, db: Session, seed_curated_authorities):
    """Verifies that fabricated or unretrieved statutory authority citations are safely dropped."""
    user_id, headers = _setup_user(client, "asst_fake_auth@test.com", role="CLIENT")
    res_case = client.post("/api/v1/cases", json={"title": "Test Case", "description": "D"}, headers=headers)
    case_id = res_case.json()["id"]

    doc = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Contract.pdf", storage_key="k_c", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.CONTRACT, version=1,
    )
    db.add(doc)
    db.flush()
    chunk = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc.id,
        content="Non-compete clause duration is 12 months.",
        metadata_={"page_start": 1, "page_end": 1, "document_version": 1, "source_filename": doc.filename},
    )
    db.add(chunk)
    db.commit()

    # Mock LLM provider that attempts to return a fake authority citation
    mock_llm = MagicMock(spec=MockLLMProvider)
    mock_llm.model = "mock-gpt-4o"
    mock_llm.generate_structured_response.return_value = {
        "answer": "Answer referencing real and fake legal authority.",
        "grounding_status": "SUPPORTED",
        "citations": [
            {"chunk_id": str(chunk.id), "document_id": str(doc.id), "text_snippet": "Non-compete clause."}
        ],
        "authority_citations": [
            {
                "canonical_identifier": "IN-ACT-1872-9",
                "canonical_provision_id": "IN-ACT-1872-9-SEC-27-CURR",
                "text_snippet": "Section 27 Contract Act text.",
            },
            {
                "canonical_identifier": "IN-ACT-FAKE-999",
                "canonical_provision_id": "IN-ACT-FAKE-999-SEC-999",
                "text_snippet": "Fabricated statute provision text.",
            },
        ],
        "claims": [],
        "uncertainties": [],
        "warnings": [],
    }

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    service = CaseAssistantService(db, llm_provider=mock_llm)
    response = service.query_case_assistant(
        user=user,
        case_id=UUID(case_id),
        req=CaseAssistantQueryRequest(
            question="What is the law on non-compete restraint of trade under Section 27?",
            include_legal_authority=True,
        ),
    )

    # Only 1 authority citation should survive verification
    assert len(response.authority_citations) == 1
    assert response.authority_citations[0].canonical_provision_id == "IN-ACT-1872-9-SEC-27-CURR"
    assert "UNVERIFIED_AUTHORITY_CITATION_DROPPED" in response.warnings
