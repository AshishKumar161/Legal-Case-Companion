import uuid
from unittest.mock import MagicMock, patch

from app.models.ai import DocumentChunk
from app.models.case import Case, CaseParticipant, ParticipantRole, ParticipantStatus
from app.models.document import Document, DocumentSecurityStatus
from app.models.user import User
from app.schemas.ai import AIResearchRequest
from app.domain.ai.retrieval_service import RetrievalService, cosine_similarity


def test_cosine_similarity():
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]
    vec3 = [0.0, 1.0, 0.0]

    assert cosine_similarity(vec1, vec2) == 1.0
    assert cosine_similarity(vec1, vec3) == 0.0
    assert cosine_similarity(vec1, []) == 0.0


@patch("app.domain.ai.retrieval_service.EmbeddingService")
def test_retrieval_service_success(mock_embedding, db):
    # Setup test data
    user = User(
        id=uuid.uuid4(), email="test@test.com", password_hash="pw", role="CLIENT"
    )
    case = Case(id=uuid.uuid4(), title="Test Case", description="Test", status="OPEN")
    participant = CaseParticipant(
        case_id=case.id,
        user_id=user.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add_all([user, case, participant])

    doc = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        uploaded_by=user.id,
        filename="t.pdf",
        storage_key="t.pdf",
        mime_type="application/pdf",
        file_size=100,
        security_status=DocumentSecurityStatus.SAFE,
    )
    db.add(doc)

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        case_id=case.id,
        document_id=doc.id,
        content="relevant text",
        embedding=[1.0, 0.0, 0.0],
    )
    db.add(chunk)
    db.commit()

    # Mock embedding to return a vector similar to chunk
    mock_emb_inst = MagicMock()
    mock_emb_inst.generate_embeddings.return_value = [[1.0, 0.0, 0.0]]
    mock_embedding.return_value = mock_emb_inst

    service = RetrievalService(db)

    req = AIResearchRequest(query="relevant")
    results = service.retrieve_evidence(user, case.id, req)

    assert len(results) == 1
    assert results[0].chunk_id == chunk.id
    assert results[0].score == 1.0


@patch("app.domain.ai.retrieval_service.EmbeddingService")
def test_retrieval_service_filters_unsafe_documents(mock_embedding, db):
    # Setup test data with unsafe document
    user = User(
        id=uuid.uuid4(), email="test@test.com", password_hash="pw", role="CLIENT"
    )
    case = Case(id=uuid.uuid4(), title="Test Case", description="Test", status="OPEN")
    participant = CaseParticipant(
        case_id=case.id,
        user_id=user.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add_all([user, case, participant])

    doc = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        uploaded_by=user.id,
        filename="t.pdf",
        storage_key="t.pdf",
        mime_type="application/pdf",
        file_size=100,
        security_status=DocumentSecurityStatus.REJECTED,
    )
    db.add(doc)

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        case_id=case.id,
        document_id=doc.id,
        content="unsafe text",
        embedding=[1.0, 0.0, 0.0],
    )
    db.add(chunk)
    db.commit()

    mock_emb_inst = MagicMock()
    mock_emb_inst.generate_embeddings.return_value = [[1.0, 0.0, 0.0]]
    mock_embedding.return_value = mock_emb_inst

    service = RetrievalService(db)

    req = AIResearchRequest(query="unsafe")
    results = service.retrieve_evidence(user, case.id, req)

    # Should be empty because document is REJECTED
    assert len(results) == 0
