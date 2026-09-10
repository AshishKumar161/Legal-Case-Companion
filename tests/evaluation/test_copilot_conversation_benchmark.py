from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.ai import AIMessage, DocumentChunk
from app.models.document import (
    Document,
    DocumentCategory,
    DocumentProcessingStatus,
    DocumentSecurityStatus,
)
from app.models.user import User
from app.schemas.ai import AIMessageRequest
from app.schemas.assistant import GroundingStatus
from app.domain.ai.ai_conversation_service import AIConversationService
from app.domain.ai.legal_authority_ingestion import LegalAuthorityIngestionService
from tests.fixtures.curated_legal_authorities import CURATED_STATUTES


def test_copilot_conversation_benchmark_suite(client: TestClient, db: Session):
    """Benchmark evaluation measuring multi-turn contextual coherence, cross-case isolation,

    memory supremacy controls, and uncertainty reporting.
    """
    # 1. Ingest curated legal authorities
    service_ingest = LegalAuthorityIngestionService(db)
    for stat in CURATED_STATUTES:
        service_ingest.ingest_legal_authority(stat)

    # 2. Setup user and two distinct cases
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"email": "copilot_bench@test.com", "password": "SecurePassword123!", "role": "CLIENT", "full_name": "Bench User"},
    )
    user_id = res_reg.json().get("id")
    user = db.query(User).filter(User.id == UUID(user_id)).first()

    # Case A: Lease Dispute
    res_ca = client.post("/api/v1/cases", json={"title": "Lease Dispute Alpha", "description": "D"}, headers={"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': 'copilot_bench@test.com', 'password': 'SecurePassword123!'}).json()['access_token']}"})
    case_a_id = UUID(res_ca.json()["id"])

    # Case B: Intellectual Property
    res_cb = client.post("/api/v1/cases", json={"title": "IP Case Beta", "description": "D"}, headers={"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': 'copilot_bench@test.com', 'password': 'SecurePassword123!'}).json()['access_token']}"})
    case_b_id = UUID(res_cb.json()["id"])

    # Seed Evidence in Case A
    doc_a = Document(
        id=generate_uuid7(), case_id=case_a_id, uploaded_by=user.id,
        filename="Lease_Deed.pdf", storage_key="k_lease", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.CONTRACT, version=1,
    )
    db.add(doc_a)
    db.flush()
    chunk_a = DocumentChunk(
        id=generate_uuid7(), case_id=case_a_id, document_id=doc_a.id,
        content="Monthly rent is fixed at Rs 75,000 payable on or before 5th of each English calendar month. Security deposit is Rs 1,50,000.",
        metadata_={"page_start": 2, "page_end": 2, "document_version": 1, "source_filename": doc_a.filename},
    )
    db.add(chunk_a)

    # Seed Evidence in Case B
    doc_b = Document(
        id=generate_uuid7(), case_id=case_b_id, uploaded_by=user.id,
        filename="Patent_Filing.pdf", storage_key="k_pat", mime_type="application/pdf", file_size=100,
        security_status=DocumentSecurityStatus.SAFE, processing_status=DocumentProcessingStatus.READY,
        document_type=DocumentCategory.EVIDENCE, version=1,
    )
    db.add(doc_b)
    db.flush()
    chunk_b = DocumentChunk(
        id=generate_uuid7(), case_id=case_b_id, document_id=doc_b.id,
        content="Patent application No. 202411009988 for biometric encryption apparatus filed on 10th March 2024.",
        metadata_={"page_start": 1, "page_end": 1, "document_version": 1, "source_filename": doc_b.filename},
    )
    db.add(chunk_b)
    db.commit()

    service = AIConversationService(db)

    # --- Scenario 1: Multi-turn Coherent Inquiry in Case A ---
    conv_a = service.create_conversation(user, case_a_id, "Lease Inquiry")
    m1 = service.send_message(user, case_a_id, conv_a.id, AIMessageRequest(query="What is the monthly rent amount specified in the lease deed?"))
    assert m1.grounding_status == GroundingStatus.SUPPORTED.value
    assert len(m1.citations) >= 1
    assert "75,000" in m1.content

    # Turn 2: Follow-up question using relative reference
    m2 = service.send_message(user, case_a_id, conv_a.id, AIMessageRequest(query="And what is the security deposit for that?"))
    assert m2.grounding_status == GroundingStatus.SUPPORTED.value
    assert len(m2.citations) >= 1
    assert "1,50,000" in m2.content

    # --- Scenario 2: Cross-Case Boundary Protection ---
    # Asking in Case A about the biometric encryption patent from Case B
    m_cross = service.send_message(user, case_a_id, conv_a.id, AIMessageRequest(query="What is the patent application number for the biometric encryption apparatus?"))
    assert m_cross.grounding_status == GroundingStatus.INSUFFICIENT_EVIDENCE.value
    assert len(m_cross.citations) == 0
    assert "202411009988" not in m_cross.content

    # --- Scenario 3: Memory Supremacy over Simulated False Memory ---
    # Create conversation in Case A with simulated false memory
    conv_mem = service.create_conversation(user, case_a_id, "Memory Test")
    hallucinated_msg = AIMessage(
        id=generate_uuid7(), conversation_id=conv_mem.id, role="assistant",
        content="The rent was previously reduced to Rs 20,000 by oral agreement.",
    )
    db.add(hallucinated_msg)
    db.commit()

    m_mem = service.send_message(user, case_a_id, conv_mem.id, AIMessageRequest(query="What is the monthly rent specified in the lease agreement?"))
    assert m_mem.grounding_status == GroundingStatus.SUPPORTED.value
    assert len(m_mem.citations) >= 1
    assert m_mem.citations[0]["source_filename"] == "Lease_Deed.pdf"
    assert "75,000" in m_mem.content
    assert "20,000" not in m_mem.content

    print("\n[COPILOT BENCHMARK] All 3 benchmark scenarios passed with 100% precision & safety!")
