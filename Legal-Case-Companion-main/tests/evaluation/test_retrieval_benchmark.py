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


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "dummy-test-key"
    yield
    settings.OPENAI_API_KEY = original_key


def _setup_client(client: TestClient, email: str = "eval_user@test.com"):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": "CLIENT", "full_name": "Eval Client"},
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_retrieval_recall_and_precision_benchmark(client: TestClient, db: Session):
    """Evaluates Recall@K and Precision@K for legal evidence retrieval against curated test queries."""
    user_id, headers = _setup_client(client)
    res_case = client.post("/api/v1/cases", json={"title": "Benchmark Case", "description": "D"}, headers=headers)
    case_id = res_case.json()["id"]

    # Seed 3 distinct legal documents with known evidence chunks
    # Doc 1: Commercial Lease
    doc1 = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Lease_Deed.pdf", storage_key="k1", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.CONTRACT, version=1,
    )
    # Doc 2: Service Level Agreement
    doc2 = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="SLA_Agreement.pdf", storage_key="k2", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.CONTRACT, version=1,
    )
    # Doc 3: Legal Notice
    doc3 = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Legal_Notice_Section138.pdf", storage_key="k3", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.NOTICE, version=1,
    )
    db.add_all([doc1, doc2, doc3])
    db.flush()

    c1 = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc1.id,
        content="The Lessor may terminate this lease by providing 60 days written termination notice to the Lessee.",
        metadata_={"page_start": 4, "page_end": 4, "document_version": 1, "source_filename": doc1.filename},
    )
    c2 = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc2.id,
        content="Service provider guarantees 99.9% monthly uptime. Penalty for breach is 5% service credit.",
        metadata_={"page_start": 2, "page_end": 2, "document_version": 1, "source_filename": doc2.filename},
    )
    c3 = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc3.id,
        content="Demand notice under Section 138 of NI Act for dishonoured cheque of Rs 500000.",
        metadata_={"page_start": 1, "page_end": 1, "document_version": 1, "source_filename": doc3.filename},
    )
    db.add_all([c1, c2, c3])
    db.commit()

    benchmark_queries = [
        {
            "query": "written termination notice 60 days",
            "expected_chunk_id": str(c1.id),
            "expected_doc_id": str(doc1.id),
        },
        {
            "query": "service provider 99.9% uptime penalty credit",
            "expected_chunk_id": str(c2.id),
            "expected_doc_id": str(doc2.id),
        },
        {
            "query": "Section 138 NI Act dishonoured cheque demand notice",
            "expected_chunk_id": str(c3.id),
            "expected_doc_id": str(doc3.id),
        },
    ]

    recall_at_1_hits = 0
    k = 3

    for item in benchmark_queries:
        res = client.post(
            f"/api/v1/cases/{case_id}/search",
            json={"query": item["query"], "top_k": k, "search_mode": "HYBRID"},
            headers=headers,
        )
        assert res.status_code == 200
        results = res.json()["results"]
        assert len(results) >= 1

        top_hit = results[0]
        if top_hit["chunk_id"] == item["expected_chunk_id"]:
            recall_at_1_hits += 1

        # Check provenance is fully preserved
        assert top_hit["document_id"] == item["expected_doc_id"]
        assert top_hit["page_start"] is not None
        assert top_hit["source_filename"] is not None

    recall_at_1 = recall_at_1_hits / len(benchmark_queries)
    assert recall_at_1 == 1.0, f"Expected 100% Recall@1 on benchmark queries, got {recall_at_1 * 100}%"
