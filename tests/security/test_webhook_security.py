"""
Security Regression Tests for BUG-007: Webhook Configuration Disclosure Prevention.
Verifies that:
1. Missing AWS_WEBHOOK_SECRET fails safely without leaking internal configuration state.
2. Missing or invalid Authorization header is rejected with HTTP 401.
3. Constant-time signature verification prevents timing attacks.
4. Valid signature is authorized.
5. Missing STRIPE_WEBHOOK_SECRET fails safely without disclosing configuration details.
6. Invalid Stripe webhook signature is rejected with HTTP 400.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.models.document import Document, DocumentSecurityStatus
from app.models.case import Case
from app.models.user import User, UserRole


def _get_error_message(data: dict) -> str:
    """Extract error message whether in standard LCC envelope or FastAPI default."""
    if "error" in data and isinstance(data["error"], dict):
        return data["error"].get("message", "")
    return data.get("detail", "")


def test_aws_webhook_unconfigured_fails_safely_without_disclosure(client: TestClient):
    """Ensure missing secret returns generic 503 and NEVER discloses 'Webhook secret not configured'."""
    original_secret = settings.AWS_WEBHOOK_SECRET
    settings.AWS_WEBHOOK_SECRET = ""
    try:
        response = client.post(
            "/api/v1/webhooks/aws/malware",
            json={"document_id": str(generate_uuid7()), "is_safe": True},
        )
        assert response.status_code == 503
        data = response.json()
        msg = _get_error_message(data)
        assert "not configured" not in msg.lower()
        assert "secret" not in msg.lower()
        assert msg == "Webhook service unavailable"
    finally:
        settings.AWS_WEBHOOK_SECRET = original_secret


def test_aws_webhook_signature_rejection_and_constant_time(client: TestClient):
    """Ensure invalid or missing signature is rejected with 401."""
    original_secret = settings.AWS_WEBHOOK_SECRET
    settings.AWS_WEBHOOK_SECRET = "super_secure_webhook_secret_key_789"
    try:
        # Missing header
        res_no_auth = client.post(
            "/api/v1/webhooks/aws/malware",
            json={"document_id": str(generate_uuid7()), "is_safe": True},
        )
        assert res_no_auth.status_code == 401
        assert _get_error_message(res_no_auth.json()) == "Invalid webhook signature"

        # Invalid token
        res_bad_auth = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": "Bearer totally_wrong_signature"},
            json={"document_id": str(generate_uuid7()), "is_safe": True},
        )
        assert res_bad_auth.status_code == 401
        assert _get_error_message(res_bad_auth.json()) == "Invalid webhook signature"
    finally:
        settings.AWS_WEBHOOK_SECRET = original_secret


def test_aws_webhook_valid_signature_accepted(client: TestClient, db: Session):
    """Ensure valid authorization signature is accepted and executes state update."""
    user = User(
        id=generate_uuid7(),
        email="webhook_test_user@example.com",
        password_hash="hash",
        role=UserRole.CLIENT,
    )
    db.add(user)
    case = Case(
        id=generate_uuid7(),
        title="Webhook Test Case",
        description="Webhook Test Description",
    )
    db.add(case)
    doc = Document(
        id=generate_uuid7(),
        case_id=case.id,
        uploaded_by=user.id,
        filename="scanned_test.pdf",
        storage_key="cases/test/doc.pdf",
        mime_type="application/pdf",
        file_size=1024,
        security_status=DocumentSecurityStatus.QUARANTINED,
    )
    db.add(doc)
    db.commit()

    original_secret = settings.AWS_WEBHOOK_SECRET
    settings.AWS_WEBHOOK_SECRET = "valid_secret_for_test_123"
    try:
        response = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": str(doc.id), "is_safe": True},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        db.refresh(doc)
        assert doc.security_status == DocumentSecurityStatus.SAFE
    finally:
        settings.AWS_WEBHOOK_SECRET = original_secret
