import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.ai import DocumentChunk
from app.models.document import (
    Document,
    DocumentCategory,
    DocumentProcessingStatus,
    DocumentSecurityStatus,
)


def _setup_perf_user(client: TestClient, email: str = "perf_retrieval@example.com") -> tuple[str, dict[str, str]]:
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "PerfPassword123!", "role": "CLIENT", "full_name": "Perf User"},
    )
    user_id = reg_res.json()["id"]
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "PerfPassword123!"})
    token = login_res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_evidence_search_and_legal_authority_search_latency(client: TestClient, db: Session):
    """Measures hybrid evidence search and legal authority retrieval query performance."""
    user_id, headers = _setup_perf_user(client, "perf_search_latency@example.com")

    # Create Case
    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": "Search Latency Case", "description": "Testing search retrieval speeds."},
    )
    case_id = case_res.json()["id"]
    case_uuid = uuid.UUID(case_id)
    user_uuid = uuid.UUID(user_id)

    # Seed Document and Chunks
    doc = Document(
        id=generate_uuid7(),
        case_id=case_uuid,
        uploaded_by=user_uuid,
        filename="Commercial_Lease_Agreement.pdf",
        storage_key="cases/lease.pdf",
        mime_type="application/pdf",
        file_size=2048,
        security_status=DocumentSecurityStatus.SAFE,
        processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.CONTRACT,
        version=1,
    )
    db.add(doc)
    db.flush()

    chunks = [
        DocumentChunk(
            id=generate_uuid7(),
            case_id=case_uuid,
            document_id=doc.id,
            content=f"Clause {i}: The tenant agrees to maintain monthly rental payments under Section 106 of the Transfer of Property Act 1882.",
            metadata_={"page_start": i + 1, "page_end": i + 1},
        )
        for i in range(15)
    ]
    db.add_all(chunks)
    db.commit()

    # 1. Benchmark Case Evidence Search Latency
    t0 = time.perf_counter()
    search_res = client.post(
        f"/api/v1/cases/{case_id}/search",
        headers=headers,
        json={"query": "Section 106 Transfer of Property Act", "top_k": 5},
    )
    search_lat_ms = (time.perf_counter() - t0) * 1000.0
    assert search_res.status_code == 200
    assert search_lat_ms < 300.0  # Search must complete in < 300ms

    # 2. Benchmark Legal Authority Citation Search Latency
    t0 = time.perf_counter()
    auth_res = client.post(
        "/api/v1/legal-authorities/search",
        headers=headers,
        json={"query": "Section 138 Negotiable Instruments Act", "limit": 5},
    )
    auth_lat_ms = (time.perf_counter() - t0) * 1000.0
    assert auth_res.status_code == 200
    assert auth_lat_ms < 250.0  # Legal authority query must complete in < 250ms
