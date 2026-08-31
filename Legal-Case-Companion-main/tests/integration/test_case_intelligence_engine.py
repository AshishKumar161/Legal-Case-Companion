from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.models.ai import AIConversation, AIMessage, DocumentChunk
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


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "dummy-test-key"
    yield
    settings.OPENAI_API_KEY = original_key


def _setup_user(client: TestClient, email: str, role: str = "CLIENT"):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": role, "full_name": "Intel Test User"},
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_case_intelligence_fact_extraction_and_provenance(client: TestClient, db: Session):
    """Verifies that evidence-grounded facts and user-reported facts preserve provenance."""
    user_id, headers = _setup_user(client, "intel_fact_u@test.com", role="CLIENT")
    res_c = client.post("/api/v1/cases", json={"title": "Contract Case", "description": "D"}, headers=headers)
    case_id = res_c.json()["id"]

    # 1. Seed Safe Document & Chunks
    doc = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Commercial_Lease.pdf", storage_key="k_comm_lease", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.CONTRACT, version=1,
    )
    db.add(doc)
    db.flush()

    chunk1 = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc.id,
        content="Clause 4: The monthly rent is Rs. 80,000 payable on 5th of each month. The security deposit is Rs. 1,60,000.",
        metadata_={"page_start": 2, "page_end": 2, "document_version": 1, "source_filename": doc.filename},
    )
    db.add(chunk1)

    # 2. Seed Conversation finding (User reported)
    conv = AIConversation(id=generate_uuid7(), case_id=UUID(case_id), user_id=UUID(user_id), title="Chat")
    db.add(conv)
    db.flush()
    msg = AIMessage(
        id=generate_uuid7(), conversation_id=conv.id, role="user",
        content="I paid the maintenance charges of Rs 5000 in cash to the landlord.",
    )
    db.add(msg)
    db.commit()

    # 3. Refresh Intelligence
    res_ref = client.post(f"/api/v1/cases/{case_id}/intelligence/refresh", headers=headers)
    assert res_ref.status_code == 200
    data = res_ref.json()

    facts = data["facts"]
    assert len(facts) >= 2

    # Check verified document fact
    doc_fact = next(f for f in facts if "80,000" in f["fact_text"])
    assert doc_fact["verification_status"] == FactVerificationStatus.AI_VERIFIED.value
    assert doc_fact["source_type"] == FactSourceType.CASE_EVIDENCE.value
    assert doc_fact["source_filename"] == "Commercial_Lease.pdf"
    assert doc_fact["source_chunk_id"] == str(chunk1.id)
    assert doc_fact["document_version"] == 1

    # Check user reported conversation fact
    user_fact = next(f for f in facts if "5000" in f["fact_text"])
    assert user_fact["verification_status"] == FactVerificationStatus.USER_REPORTED.value
    assert user_fact["source_type"] == FactSourceType.USER_REPORTED.value
    assert user_fact["confidence_score"] == 0.5


def test_stale_intelligence_protection_on_version_update(client: TestClient, db: Session):
    """Verifies that facts from an older document version are superseded upon re-extraction."""
    user_id, headers = _setup_user(client, "intel_stale_u@test.com", role="CLIENT")
    res_c = client.post("/api/v1/cases", json={"title": "Version Case", "description": "D"}, headers=headers)
    case_id = res_c.json()["id"]

    # 1. Create Document v1
    doc = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Lease_Agreement.pdf", storage_key="k_lease_v1", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.CONTRACT, version=1,
    )
    db.add(doc)
    db.flush()
    chunk_v1 = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc.id,
        content="Clause 1: The monthly rent is fixed at Rs. 50,000.",
    )
    db.add(chunk_v1)
    db.commit()

    # Refresh Intelligence on v1
    client.post(f"/api/v1/cases/{case_id}/intelligence/refresh", headers=headers)
    res_facts1 = client.get(f"/api/v1/cases/{case_id}/intelligence/facts", headers=headers)
    assert any("50,000" in f["fact_text"] for f in res_facts1.json())

    # 2. Update Document to v2 with new rent
    doc.version = 2
    chunk_v1.content = "Clause 1: The monthly rent is amended to Rs. 65,000."
    db.commit()

    # Refresh Intelligence on v2
    client.post(f"/api/v1/cases/{case_id}/intelligence/refresh", headers=headers)
    res_facts2 = client.get(f"/api/v1/cases/{case_id}/intelligence/facts", headers=headers)
    facts2 = res_facts2.json()

    # Old v1 fact (50,000) should no longer be active; new v2 fact (65,000) should be active
    assert any("65,000" in f["fact_text"] for f in facts2)
    assert not any("50,000" in f["fact_text"] for f in facts2)


def test_timeline_chronology_and_conflict_preservation(client: TestClient, db: Session):
    """Verifies that chronological dates are parsed and conflicts are preserved with dual provenance."""
    user_id, headers = _setup_user(client, "intel_time_u@test.com", role="CLIENT")
    res_c = client.post("/api/v1/cases", json={"title": "Timeline Case", "description": "D"}, headers=headers)
    case_id = res_c.json()["id"]

    # Doc 1: States notice issued on 12 March 2024
    doc1 = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Notice_Copy.pdf", storage_key="k_not", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.EVIDENCE, version=1,
    )
    # Doc 2: Reply states notice was dated 15 March 2024
    doc2 = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Reply_Notice.pdf", storage_key="k_rep", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.EVIDENCE, version=1,
    )
    db.add_all([doc1, doc2])
    db.flush()

    chunk1 = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc1.id,
        content="Legal Notice dated 12 March 2024 demanding payment of arrears within 15 days.",
    )
    chunk2 = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc2.id,
        content="In response to your legal notice dated 15 March 2024, our client denies all liability.",
    )
    db.add_all([chunk1, chunk2])
    db.commit()

    # Refresh Intelligence
    res_intel = client.post(f"/api/v1/cases/{case_id}/intelligence/refresh", headers=headers)
    assert res_intel.status_code == 200
    timeline = res_intel.json()["timeline"]

    assert len(timeline) >= 2
    # Verify conflict detection
    conflicting_events = [t for t in timeline if t["is_conflicting"]]
    assert len(conflicting_events) >= 1
    assert conflicting_events[0]["conflicting_source_details"] is not None
    assert len(conflicting_events[0]["conflicting_source_details"]) >= 1


def test_evidence_gaps_and_conservative_risks(client: TestClient, db: Session):
    """Verifies that missing proofs are marked NOT_FOUND_IN_AVAILABLE_MATERIALS and conservative risks created."""
    user_id, headers = _setup_user(client, "intel_gaps_u@test.com", role="CLIENT")
    res_c = client.post("/api/v1/cases", json={"title": "NI Act Case", "description": "D"}, headers=headers)
    case_id = res_c.json()["id"]

    # Doc mentioning legal notice but no postal receipt
    doc = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Cheque_Demand_Notice.pdf", storage_key="k_dem", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.EVIDENCE, version=1,
    )
    db.add(doc)
    db.flush()
    chunk = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc.id,
        content="Statutory demand notice under Section 138 issued to the drawer for dishonour of cheque.",
    )
    db.add(chunk)
    db.commit()

    # Refresh Intelligence
    res_intel = client.post(f"/api/v1/cases/{case_id}/intelligence/refresh", headers=headers)
    assert res_intel.status_code == 200
    data = res_intel.json()

    # 1. Evidence gap identified
    gaps = data["evidence_gaps"]
    assert len(gaps) >= 1
    gap = gaps[0]
    assert gap["status"] == EvidenceGapStatus.NOT_FOUND_IN_AVAILABLE_MATERIALS.value
    assert gap["severity"] == RiskSeverity.HIGH.value
    assert "postal" in gap["description"].lower() or "proof" in gap["description"].lower()

    # 2. Conservative risk identified without outcome prediction
    risks = data["risks"]
    assert len(risks) >= 1
    risk = risks[0]
    assert risk["severity"] == RiskSeverity.HIGH.value
    assert "win" not in risk["description"].lower()
    assert "probability" not in risk["description"].lower()


def test_human_review_and_lawyer_confirmation(client: TestClient, db: Session):
    """Verifies that lawyers can confirm AI-suggested intelligence to HUMAN_CONFIRMED."""
    _user_id, headers = _setup_user(client, "intel_review_u@test.com", role="LAWYER")
    res_c = client.post("/api/v1/cases", json={"title": "Review Case", "description": "D"}, headers=headers)
    case_id = res_c.json()["id"]

    # 1. Create a fact directly
    res_fact = client.post(
        f"/api/v1/cases/{case_id}/intelligence/facts",
        json={"fact_text": "Defendant acknowledged receipt of invoice in email dated 10 Jan 2024.", "category": "FINANCIAL"},
        headers=headers,
    )
    assert res_fact.status_code == 201
    fact_id = res_fact.json()["id"]

    # 2. Lawyer confirms fact
    res_update = client.patch(
        f"/api/v1/cases/{case_id}/intelligence/facts/{fact_id}",
        json={"verification_status": FactVerificationStatus.HUMAN_CONFIRMED.value},
        headers=headers,
    )
    assert res_update.status_code == 200
    assert res_update.json()["verification_status"] == FactVerificationStatus.HUMAN_CONFIRMED.value


def test_case_intelligence_cross_case_isolation_and_security(client: TestClient, db: Session):
    """Verifies that unauthorized users or participants from other cases cannot access case intelligence."""
    _u1_id, h1 = _setup_user(client, "intel_iso1@test.com", role="CLIENT")
    _u2_id, h2 = _setup_user(client, "intel_iso2@test.com", role="CLIENT")

    res_c1 = client.post("/api/v1/cases", json={"title": "Alpha Case", "description": "D"}, headers=h1)
    c1_id = res_c1.json()["id"]

    client.post("/api/v1/cases", json={"title": "Beta Case", "description": "D"}, headers=h2)

    # User 1 creates fact in Case Alpha
    client.post(
        f"/api/v1/cases/{c1_id}/intelligence/facts",
        json={"fact_text": "Confidential alpha settlement offer of Rs 25,00,000."},
        headers=h1,
    )

    # 1. User 2 tries to read Case Alpha intelligence -> 404
    res_unauth = client.get(f"/api/v1/cases/{c1_id}/intelligence", headers=h2)
    assert res_unauth.status_code == 404

    # 2. User 2 tries to refresh Case Alpha intelligence -> 404
    res_unauth_ref = client.post(f"/api/v1/cases/{c1_id}/intelligence/refresh", headers=h2)
    assert res_unauth_ref.status_code == 404

    # 3. Workspace aggregation verifies intelligence counts
    res_ws = client.get(f"/api/v1/cases/{c1_id}/workspace", headers=h1)
    assert res_ws.status_code == 200
    ws_data = res_ws.json()
    assert "intelligence_summary" in ws_data
    assert ws_data["intelligence_summary"]["facts_count"] >= 1
