from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.ai import DocumentChunk
from app.models.case_intelligence import (
    EvidenceGapStatus,
    FactSourceType,
    FactVerificationStatus,
    RiskSeverity,
)
from app.models.document import (
    Document,
    DocumentCategory,
    DocumentProcessingStatus,
    DocumentSecurityStatus,
)


def _setup_client_user(client: TestClient, email: str):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": "CLIENT", "full_name": "Bench User"},
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_case_intelligence_comprehensive_benchmark(client: TestClient, db: Session):
    """Benchmark evaluating structured legal intelligence extraction precision,

    conflict representation, evidence-gap precision, and provenance retention.
    """
    user_id, headers = _setup_client_user(client, "bench_intel@test.com")
    res_c = client.post("/api/v1/cases", json={"title": "Benchmark Case", "description": "Legal benchmark test"}, headers=headers)
    case_id = res_c.json()["id"]

    # Seed 3 documents:
    # 1. Loan Agreement (with rent, deposit, execution date 10 Jan 2023)
    # 2. Demand Notice (claiming default on 15 Feb 2024, notice dated 01 March 2024)
    # 3. Disputed Receipt (asserting payment on 20 Feb 2024 with different date representation)
    doc1 = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Loan_Agreement.pdf", storage_key="bench_doc1", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.CONTRACT, version=1,
    )
    doc2 = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Statutory_Demand_Notice.pdf", storage_key="bench_doc2", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.EVIDENCE, version=1,
    )
    db.add_all([doc1, doc2])
    db.flush()

    chunk1 = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc1.id,
        content="Loan Agreement executed on 10 January 2023. The monthly repayment is Rs. 45,000 payable by the borrower.",
    )
    chunk2 = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc2.id,
        content="Demand notice under Section 138 dated 01 March 2024 demanding payment of Rs. 45,000 within 15 days of receipt.",
    )
    db.add_all([chunk1, chunk2])
    db.commit()

    # Trigger Intelligence Refresh
    res = client.post(f"/api/v1/cases/{case_id}/intelligence/refresh", headers=headers)
    assert res.status_code == 200
    intel = res.json()

    # Benchmark Criteria 1: Fact extraction precision
    facts = intel["facts"]
    assert len(facts) >= 2
    assert all(f["source_type"] == FactSourceType.CASE_EVIDENCE.value for f in facts)
    assert all(f["verification_status"] == FactVerificationStatus.AI_VERIFIED.value for f in facts)
    assert all(f["source_chunk_id"] is not None for f in facts)

    # Benchmark Criteria 2: Timeline extraction & precision
    timeline = intel["timeline"]
    assert len(timeline) >= 2
    dates = [t["date_text"] for t in timeline if t["date_text"]]
    assert any("2023" in d for d in dates)
    assert any("2024" in d for d in dates)

    # Benchmark Criteria 3: Legal issue detection
    issues = intel["issues"]
    assert len(issues) >= 1
    assert any("138" in i["issue_text"] for i in issues)

    # Benchmark Criteria 4: Evidence gap detection
    gaps = intel["evidence_gaps"]
    assert len(gaps) >= 1
    assert gaps[0]["status"] == EvidenceGapStatus.NOT_FOUND_IN_AVAILABLE_MATERIALS.value

    # Benchmark Criteria 5: Conservative risk identification
    risks = intel["risks"]
    assert len(risks) >= 1
    assert risks[0]["severity"] in (RiskSeverity.HIGH.value, RiskSeverity.CRITICAL.value)
