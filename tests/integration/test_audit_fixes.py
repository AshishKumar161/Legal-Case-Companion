import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.schemas.ai import AIResearchResponse, Citation
from app.schemas.retrieval import RetrievedChunk
from app.domain.ai.ai_research_service import AIResearchService


def _create_user(
    client: TestClient, email: str, role: str = "CLIENT", full_name: str = "Test User"
):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "role": role,
            "full_name": full_name,
        },
    )
    user_id = res_reg.json().get("id")
    res_login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Password123!"}
    )
    token = res_login.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_production_secret_validation():
    """Verify that in production mode, missing or placeholder JWT keys raise an error."""
    from app.core.config import Settings

    # Setting ENVIRONMENT="production" with placeholder keys must fail
    with pytest.raises(ValueError):
        Settings(
            ENVIRONMENT="production",
            CSRF_SECRET_KEY="a" * 32,
            DATABASE_URL="postgresql://test:test@localhost/test",
            JWT_PRIVATE_KEY="<set-in-environment>",
            JWT_PUBLIC_KEY="<set-in-environment>",
        )


def test_malformed_content_length_middleware_handling(client: TestClient):
    """Ensure malformed Content-Length headers return a 400 Bad Request instead of 500 internal server error."""
    response = client.post(
        "/api/v1/auth/login",
        headers={"Content-Length": "invalid_number"},
        json={"email": "test@test.com", "password": "pass"},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_CONTENT_LENGTH"


def test_webhook_constant_time_verification(client: TestClient):
    """Ensure AWS webhook requires valid bearer secret with constant-time matching."""
    doc_id = str(generate_uuid7())
    original_secret = settings.AWS_WEBHOOK_SECRET
    settings.AWS_WEBHOOK_SECRET = "secure-webhook-token-test-123"

    try:
        # 1. Invalid secret header
        res_invalid = client.post(
            "/api/v1/webhooks/aws/malware",
            json={"document_id": doc_id, "is_safe": True},
            headers={"Authorization": "Bearer wrong-secret"},
        )
        assert res_invalid.status_code == 401
        assert "Invalid webhook signature" in res_invalid.text

        # 2. Valid secret header
        res_valid = client.post(
            "/api/v1/webhooks/aws/malware",
            json={"document_id": doc_id, "is_safe": True},
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
        )
        # Returns 404 because doc_id doesn't exist, but authorization passed (not 401)
        assert res_valid.status_code == 404
    finally:
        settings.AWS_WEBHOOK_SECRET = original_secret


def test_ai_citation_filtering_unretrieved_chunks(db: Session):
    """Ensure that any citations hallucinated by AI that do not match retrieved chunks are safely filtered out."""
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "dummy-key-for-test"

    try:
        case_id = generate_uuid7()
        real_chunk_id = generate_uuid7()
        real_doc_id = generate_uuid7()
        fake_chunk_id = generate_uuid7()
        fake_doc_id = generate_uuid7()

        retrieved_chunk = RetrievedChunk(
            chunk_id=real_chunk_id,
            document_id=real_doc_id,
            case_id=case_id,
            content="The agreed deposit is Rs. 50,000 paid by tenant.",
            source_metadata={"filename": "agreement.pdf"},
            score=0.92,
            rank=1,
        )

        class MockHallucinatingAIProvider:
            model = "mock-hallucinating"

            def generate_research_response(
                self, system_prompt: str, user_query: str, chunks: list[RetrievedChunk]
            ):
                return AIResearchResponse(
                    answer="The tenant paid deposit and additional illegal fees.",
                    citations=[
                        Citation(
                            chunk_id=real_chunk_id,
                            document_id=real_doc_id,
                            text_snippet="The agreed deposit is Rs. 50,000",
                            relevance_score=0.92,
                        ),
                        Citation(
                            chunk_id=fake_chunk_id,
                            document_id=fake_doc_id,
                            text_snippet="Fake hallucinated clause",
                            relevance_score=0.99,
                        ),
                    ],
                    warnings=[],
                )

        service = AIResearchService(db, ai_provider=MockHallucinatingAIProvider())

        class MockRetrievalService:
            def retrieve_evidence(self, user, case_id, req):
                return [retrieved_chunk]

        service.retrieval_service = MockRetrievalService()

        from app.models.user import User
        from app.schemas.ai import AIResearchRequest

        dummy_user = User(id=generate_uuid7(), email="test@ai.com")
        req = AIResearchRequest(query="What is the deposit amount?")

        response = service.generate_research(dummy_user, case_id, req)

        # Verify only the valid citation survived and warning was added
        assert len(response.citations) == 1
        assert response.citations[0].chunk_id == real_chunk_id
        assert "UNVERIFIED_CITATION_REMOVED" in response.warnings
    finally:
        settings.OPENAI_API_KEY = original_key


def test_viewer_cannot_complete_document_upload(client: TestClient, db: Session):
    """Ensure that VIEWER participants are rejected when attempting to complete document uploads."""
    _owner_id, owner_headers = _create_user(
        client, "owner_upload@test.com", "CLIENT", "Owner User"
    )
    viewer_id, viewer_headers = _create_user(
        client, "viewer_upload@test.com", "CLIENT", "Viewer User"
    )

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Doc Case", "description": "Desc"},
        headers=owner_headers,
    )
    case_id = res_case.json()["id"]

    # Add viewer to case
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": viewer_id, "participant_role": "VIEWER"},
        headers=owner_headers,
    )

    # Owner initiates upload
    res_doc = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "doc.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=owner_headers,
    )
    doc_id = res_doc.json()["document"]["id"]

    # Viewer attempts to complete upload -> Forbidden
    res_complete = client.post(
        f"/api/v1/documents/{doc_id}/complete",
        headers=viewer_headers,
    )
    assert res_complete.status_code == 403
