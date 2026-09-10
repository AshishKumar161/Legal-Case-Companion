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
from app.schemas.assistant import GroundingStatus


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "dummy-test-key"
    yield
    settings.OPENAI_API_KEY = original_key


def _setup_client(client: TestClient, email: str = "eval_asst_user@test.com"):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": "CLIENT", "full_name": "Eval Asst Client"},
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_legal_ai_assistant_evaluation_suite(client: TestClient, db: Session):
    """Evaluates the Legal AI Assistant core across diverse legal QA test scenarios."""
    user_id, headers = _setup_client(client)
    res_case = client.post("/api/v1/cases", json={"title": "Evaluation Benchmark Case", "description": "D"}, headers=headers)
    case_id = res_case.json()["id"]

    # 1. Seed Case Documents
    doc1 = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Arbitration_Agreement.pdf", storage_key="arb_k", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.CONTRACT, version=1,
    )
    doc2 = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Employment_Contract.pdf", storage_key="emp_k", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.CONTRACT, version=1,
    )
    db.add_all([doc1, doc2])
    db.flush()

    chunk_arb = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc1.id,
        content="Clause 22: Any dispute shall be settled by sole arbitrator in New Delhi under the Arbitration and Conciliation Act 1996.",
        metadata_={"page_start": 7, "page_end": 7, "document_version": 1, "source_filename": doc1.filename, "document_category": "CONTRACT"},
    )
    chunk_emp = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc2.id,
        content="Clause 8: Non-compete restriction shall apply for a period of 12 months following termination within the territory of India.",
        metadata_={"page_start": 3, "page_end": 3, "document_version": 1, "source_filename": doc2.filename, "document_category": "CONTRACT"},
    )
    db.add_all([chunk_arb, chunk_emp])
    db.commit()

    evaluation_scenarios = [
        # Scenario A: Direct factual arbitration query
        {
            "scenario": "Direct Arbitration Query",
            "question": "What is the dispute resolution mechanism and seat of arbitration specified in the agreement?",
            "expected_grounding": GroundingStatus.SUPPORTED.value,
            "expected_doc_id": str(doc1.id),
            "expected_chunk_id": str(chunk_arb.id),
        },
        # Scenario B: Paraphrased non-compete query
        {
            "scenario": "Paraphrased Non-Compete Query",
            "question": "How long does the post-employment non-compete restriction last under the contract?",
            "expected_grounding": GroundingStatus.SUPPORTED.value,
            "expected_doc_id": str(doc2.id),
            "expected_chunk_id": str(chunk_emp.id),
        },
        # Scenario C: Insufficient evidence query
        {
            "scenario": "Insufficient Evidence Inquiry",
            "question": "What is the penalty for environmental violation under the factory license?",
            "expected_grounding": GroundingStatus.INSUFFICIENT_EVIDENCE.value,
            "expected_doc_id": None,
            "expected_chunk_id": None,
        },
    ]

    passed_scenarios = 0

    for item in evaluation_scenarios:
        res = client.post(
            f"/api/v1/cases/{case_id}/assistant/query",
            json={"question": item["question"], "top_k": 5},
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()

        assert data["grounding_status"] == item["expected_grounding"], f"Failed scenario: {item['scenario']}"

        if item["expected_doc_id"]:
            assert len(data["citations"]) >= 1
            citation = data["citations"][0]
            assert citation["document_id"] == item["expected_doc_id"]
            assert citation["chunk_id"] == item["expected_chunk_id"]
            assert citation["page_start"] is not None
            assert citation["source_filename"] is not None

        passed_scenarios += 1

    accuracy = passed_scenarios / len(evaluation_scenarios)
    assert accuracy == 1.0, f"Expected 100% scenario accuracy, got {accuracy * 100}%"
