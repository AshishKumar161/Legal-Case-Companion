from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.models.ai import AIConversation, AIMessage, DocumentChunk
from app.models.case import CaseParticipant, ParticipantStatus
from app.models.document import (
    Document,
    DocumentCategory,
    DocumentProcessingStatus,
    DocumentSecurityStatus,
)
from app.schemas.assistant import GroundingStatus
from app.domain.ai.legal_authority_ingestion import LegalAuthorityIngestionService
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
    service = LegalAuthorityIngestionService(db)
    for stat in CURATED_STATUTES:
        service.ingest_legal_authority(stat)
    return CURATED_STATUTES


def test_copilot_authorization_and_cross_case_isolation(client: TestClient, db: Session):
    """Verifies that conversations are strictly case-scoped and enforce participant authorization."""
    _user1_id, h1 = _setup_user(client, "copilot_u1@test.com", role="CLIENT")
    user2_id, h2 = _setup_user(client, "copilot_u2@test.com", role="CLIENT")

    # User 1 creates Case 1
    res_c1 = client.post("/api/v1/cases", json={"title": "Case 1", "description": "D1"}, headers=h1)
    c1_id = res_c1.json()["id"]

    # User 2 creates Case 2
    res_c2 = client.post("/api/v1/cases", json={"title": "Case 2", "description": "D2"}, headers=h2)
    c2_id = res_c2.json()["id"]

    # 1. User 1 creates conversation in Case 1 -> 201 Created
    res_conv = client.post(f"/api/v1/cases/{c1_id}/ai/conversations", json={}, headers=h1)
    assert res_conv.status_code == 201
    conv_id = res_conv.json()["id"]
    assert res_conv.json()["title"] == "New Conversation"

    # 2. User 2 tries to access User 1's conversation -> 404 Not Found (IDOR prevention)
    res_unauth = client.get(f"/api/v1/cases/{c1_id}/ai/conversations/{conv_id}", headers=h2)
    assert res_unauth.status_code == 404

    # 3. Cross-case access attempt: accessing Case 1's conversation under Case 2 route -> 404
    res_cross = client.get(f"/api/v1/cases/{c2_id}/ai/conversations/{conv_id}", headers=h2)
    assert res_cross.status_code == 404

    # 4. Revoked participant access attempt
    # Add User 2 as participant to Case 1 then revoke
    client.post(
        f"/api/v1/cases/{c1_id}/participants",
        json={"user_id": user2_id, "participant_role": "VIEWER"},
        headers=h1,
    )
    part = (
        db.query(CaseParticipant)
        .filter(CaseParticipant.case_id == UUID(c1_id), CaseParticipant.user_id == UUID(user2_id))
        .first()
    )
    part.status = ParticipantStatus.INACTIVE
    db.commit()

    res_revoked = client.get(f"/api/v1/cases/{c1_id}/ai/conversations/{conv_id}", headers=h2)
    assert res_revoked.status_code == 404


def test_copilot_follow_up_question_and_fresh_retrieval(client: TestClient, db: Session):
    """Verifies that follow-up questions use conversation context and perform fresh evidence retrieval."""
    user_id, headers = _setup_user(client, "copilot_followup@test.com", role="CLIENT")
    res_c = client.post("/api/v1/cases", json={"title": "Contract Case", "description": "D"}, headers=headers)
    case_id = res_c.json()["id"]

    # Seed Document 1 (Contract clauses)
    doc = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Commercial_Agreement.pdf", storage_key="k_comm", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.CONTRACT, version=1,
    )
    db.add(doc)
    db.flush()

    chunk1 = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc.id,
        content="Clause 12: Termination for Cause. Either party may terminate immediately if material breach occurs without remedy for 30 days.",
        metadata_={"page_start": 3, "page_end": 3, "document_version": 1, "source_filename": doc.filename},
    )
    chunk2 = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc.id,
        content="Clause 13: Notice Requirements. Written notice of breach must be served by registered post to the registered office address.",
        metadata_={"page_start": 4, "page_end": 4, "document_version": 1, "source_filename": doc.filename},
    )
    db.add_all([chunk1, chunk2])
    db.commit()

    # Create Conversation
    res_conv = client.post(f"/api/v1/cases/{case_id}/ai/conversations", json={}, headers=headers)
    conv_id = res_conv.json()["id"]

    # Turn 1: Initial Question
    res_msg1 = client.post(
        f"/api/v1/cases/{case_id}/ai/conversations/{conv_id}/messages",
        json={"query": "What are the rules for termination for cause under Clause 12?"},
        headers=headers,
    )
    assert res_msg1.status_code == 200
    m1_data = res_msg1.json()
    assert m1_data["role"] == "assistant"
    assert len(m1_data["citations"]) >= 1
    assert m1_data["grounding_status"] == GroundingStatus.SUPPORTED.value

    # Turn 2: Follow-up question relying on contextual query reformulation
    res_msg2 = client.post(
        f"/api/v1/cases/{case_id}/ai/conversations/{conv_id}/messages",
        json={"query": "Does that apply if written notice was served by email instead of registered post?"},
        headers=headers,
    )
    assert res_msg2.status_code == 200
    m2_data = res_msg2.json()
    assert m2_data["role"] == "assistant"
    assert len(m2_data["citations"]) >= 1

    # Verify conversation history length (2 user msgs + 2 assistant msgs = 4)
    res_msgs = client.get(f"/api/v1/cases/{case_id}/ai/conversations/{conv_id}/messages", headers=headers)
    assert len(res_msgs.json()) == 4

    # Verify auto-generated conversation title
    res_conv_check = client.get(f"/api/v1/cases/{case_id}/ai/conversations/{conv_id}", headers=headers)
    assert res_conv_check.json()["title"] != "New Conversation"
    assert len(res_conv_check.json()["title"]) > 3


def test_adversarial_memory_isolation_fresh_evidence_supremacy(client: TestClient, db: Session):
    """Verifies that previous conversation statements cannot override fresh verified evidence."""
    user_id, headers = _setup_user(client, "copilot_memory@test.com", role="CLIENT")
    res_c = client.post("/api/v1/cases", json={"title": "Dispute Case", "description": "D"}, headers=headers)
    case_id = res_c.json()["id"]

    # Seed fresh document chunk
    doc = Document(
        id=generate_uuid7(), case_id=UUID(case_id), uploaded_by=UUID(user_id),
        filename="Settlement_Demand.pdf", storage_key="k_dem", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.EVIDENCE, version=1,
    )
    db.add(doc)
    db.flush()

    chunk = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(case_id), document_id=doc.id,
        content="The Claimant explicitly demands Rs 10,00,000 compensation and has NOT waived any claims.",
        metadata_={"page_start": 1, "page_end": 1, "document_version": 1, "source_filename": doc.filename},
    )
    db.add(chunk)
    db.commit()

    # Create Conversation
    conv = AIConversation(id=generate_uuid7(), case_id=UUID(case_id), user_id=UUID(user_id), title="Waiver Discussion")
    db.add(conv)
    db.flush()

    # Inject simulated false statement into conversation history
    hallucinated_msg = AIMessage(
        id=generate_uuid7(), conversation_id=conv.id, role="assistant",
        content="Claimant agreed in previous meeting to waive all compensation demands.",
    )
    db.add(hallucinated_msg)
    db.commit()

    # Ask query about waiver
    res_msg = client.post(
        f"/api/v1/cases/{case_id}/ai/conversations/{conv.id}/messages",
        json={"query": "Did the claimant waive any compensation claims according to the settlement demand document?"},
        headers=headers,
    )
    assert res_msg.status_code == 200
    data = res_msg.json()
    assert data["grounding_status"] == GroundingStatus.SUPPORTED.value
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["source_filename"] == "Settlement_Demand.pdf"
    assert "NOT waived" in data["content"] or "10,00,000" in data["content"] or "Settlement_Demand.pdf" in data["content"]


def test_cross_case_evidence_leakage_prevented(client: TestClient, db: Session):
    """Verifies that an inquiry in Case A cannot retrieve or cite documents from Case B."""
    _user1_id, h1 = _setup_user(client, "copilot_iso1@test.com", role="CLIENT")
    user2_id, h2 = _setup_user(client, "copilot_iso2@test.com", role="CLIENT")

    res_c1 = client.post("/api/v1/cases", json={"title": "Case Alpha", "description": "D"}, headers=h1)
    c1_id = res_c1.json()["id"]

    res_c2 = client.post("/api/v1/cases", json={"title": "Case Beta", "description": "D"}, headers=h2)
    c2_id = res_c2.json()["id"]

    # Seed confidential trade secret in Case Beta
    doc_beta = Document(
        id=generate_uuid7(), case_id=UUID(c2_id), uploaded_by=UUID(user2_id),
        filename="Secret_Formula_Beta.pdf", storage_key="k_sec", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.EVIDENCE, version=1,
    )
    db.add(doc_beta)
    db.flush()
    chunk_beta = DocumentChunk(
        id=generate_uuid7(), case_id=UUID(c2_id), document_id=doc_beta.id,
        content="Secret proprietary formula code is BETA-XYZ-998811.",
        metadata_={"page_start": 1, "page_end": 1, "document_version": 1, "source_filename": doc_beta.filename},
    )
    db.add(chunk_beta)
    db.commit()

    # User 1 creates conversation in Case Alpha and attempts to query Secret Formula
    res_conv = client.post(f"/api/v1/cases/{c1_id}/ai/conversations", json={}, headers=h1)
    conv_id = res_conv.json()["id"]

    res_msg = client.post(
        f"/api/v1/cases/{c1_id}/ai/conversations/{conv_id}/messages",
        json={"query": "What is the secret proprietary formula code BETA-XYZ?"},
        headers=h1,
    )
    assert res_msg.status_code == 200
    data = res_msg.json()
    # Case Alpha has no such evidence -> must be INSUFFICIENT_EVIDENCE and 0 citations
    assert data["grounding_status"] == GroundingStatus.INSUFFICIENT_EVIDENCE.value
    assert len(data["citations"]) == 0
    assert "BETA-XYZ-998811" not in data["content"]


def test_copilot_conversation_lifecycle_management(client: TestClient, db: Session):
    """Verifies conversation update (PATCH) and soft-deletion (DELETE)."""
    _user_id, headers = _setup_user(client, "copilot_mgmt@test.com", role="CLIENT")
    res_c = client.post("/api/v1/cases", json={"title": "Mgmt Case", "description": "D"}, headers=headers)
    case_id = res_c.json()["id"]

    # 1. Create conversation
    res_conv = client.post(
        f"/api/v1/cases/{case_id}/ai/conversations",
        json={"title": "Initial Title"},
        headers=headers,
    )
    conv_id = res_conv.json()["id"]

    # 2. Update conversation title and status
    res_patch = client.patch(
        f"/api/v1/cases/{case_id}/ai/conversations/{conv_id}",
        json={"title": "Updated Arbitration Discussion", "status": "ARCHIVED"},
        headers=headers,
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["title"] == "Updated Arbitration Discussion"
    assert res_patch.json()["status"] == "ARCHIVED"

    # 3. Soft-delete conversation
    res_del = client.delete(f"/api/v1/cases/{case_id}/ai/conversations/{conv_id}", headers=headers)
    assert res_del.status_code == 204

    # 4. Verify conversation is no longer returned in list or get
    res_get = client.get(f"/api/v1/cases/{case_id}/ai/conversations/{conv_id}", headers=headers)
    assert res_get.status_code == 404

    res_list = client.get(f"/api/v1/cases/{case_id}/ai/conversations", headers=headers)
    assert not any(c["id"] == conv_id for c in res_list.json())
