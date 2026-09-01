import hashlib
import hmac
import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.models.consultation import Consultation, ConsultationStatus
from app.models.document import Document, DocumentSecurityStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import ClientProfile, LawyerProfile, User, UserRole


def _setup_webhook_test_data(client: TestClient, db: Session):
    # Register a user
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "webhook_owner@test.com",
            "password": "SecurePassword123!",
            "role": "CLIENT",
            "full_name": "Webhook Owner",
        },
    )
    user_id = res_reg.json()["id"]

    # Login
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "webhook_owner@test.com", "password": "SecurePassword123!"},
    )
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Webhook Case", "description": "Webhook Case Desc"},
        headers=headers,
    )
    case_id = res_case.json()["id"]

    return user_id, case_id, headers


def test_aws_malware_webhook_unauthorized(client: TestClient, db: Session):
    doc_id = generate_uuid7()
    original_secret = settings.AWS_WEBHOOK_SECRET
    settings.AWS_WEBHOOK_SECRET = "test_webhook_secret_123"
    try:
        response = client.post(
            "/api/v1/webhooks/aws/malware",
            json={"document_id": str(doc_id), "is_safe": True},
        )
        assert response.status_code == 401

        response = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": "Bearer invalid_secret"},
            json={"document_id": str(doc_id), "is_safe": True},
        )
        assert response.status_code == 401
    finally:
        settings.AWS_WEBHOOK_SECRET = original_secret


def test_aws_malware_webhook_success_and_idempotency(client: TestClient, db: Session):
    user_id, case_id, _headers = _setup_webhook_test_data(client, db)
    doc_id = generate_uuid7()

    doc = Document(
        id=doc_id,
        case_id=case_id,
        uploaded_by=user_id,
        filename="Test Malware Scan.pdf",
        storage_key=f"documents/{doc_id}",
        mime_type="application/pdf",
        file_size=1000,
        security_status=DocumentSecurityStatus.QUARANTINED,
    )
    db.add(doc)
    db.commit()

    original_secret = settings.AWS_WEBHOOK_SECRET
    settings.AWS_WEBHOOK_SECRET = "test_webhook_secret_123"

    try:
        # First callback (SAFE)
        response = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": str(doc_id), "is_safe": True},
        )
        assert response.status_code == 200

        db.refresh(doc)
        assert doc.security_status == DocumentSecurityStatus.SAFE

        # Second identical callback (IDEMPOTENCY)
        response2 = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": str(doc_id), "is_safe": True},
        )
        assert response2.status_code == 200
        db.refresh(doc)
        assert doc.security_status == DocumentSecurityStatus.SAFE

        # Second contradictory callback (IDEMPOTENCY still holds, ignores new state)
        response3 = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": str(doc_id), "is_safe": False},
        )
        assert response3.status_code == 200
        db.refresh(doc)
        assert (
            doc.security_status == DocumentSecurityStatus.SAFE
        )  # Should not change to REJECTED

    finally:
        settings.AWS_WEBHOOK_SECRET = original_secret


def test_aws_malware_webhook_rejected(client: TestClient, db: Session):
    user_id, case_id, _headers = _setup_webhook_test_data(client, db)
    doc_id = generate_uuid7()

    doc = Document(
        id=doc_id,
        case_id=case_id,
        uploaded_by=user_id,
        filename="Virus.pdf",
        storage_key=f"documents/{doc_id}",
        mime_type="application/pdf",
        file_size=1000,
        security_status=DocumentSecurityStatus.QUARANTINED,
    )
    db.add(doc)
    db.commit()

    original_secret = settings.AWS_WEBHOOK_SECRET
    settings.AWS_WEBHOOK_SECRET = "test_webhook_secret_123"

    try:
        # Rejected callback
        response = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": str(doc_id), "is_safe": False},
        )
        assert response.status_code == 200

        db.refresh(doc)
        assert doc.security_status == DocumentSecurityStatus.REJECTED
    finally:
        settings.AWS_WEBHOOK_SECRET = original_secret


def test_aws_malware_webhook_deleted_document(client: TestClient, db: Session):
    user_id, case_id, _headers = _setup_webhook_test_data(client, db)
    doc_id = generate_uuid7()

    import datetime

    doc = Document(
        id=doc_id,
        case_id=case_id,
        uploaded_by=user_id,
        filename="Deleted.pdf",
        storage_key=f"documents/{doc_id}",
        mime_type="application/pdf",
        file_size=1000,
        security_status=DocumentSecurityStatus.QUARANTINED,
        deleted_at=datetime.datetime.now(datetime.UTC),
    )
    db.add(doc)
    db.commit()

    original_secret = settings.AWS_WEBHOOK_SECRET
    settings.AWS_WEBHOOK_SECRET = "test_webhook_secret_123"

    try:
        # Callback for deleted document
        response = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": str(doc_id), "is_safe": True},
        )
        assert response.status_code == 200

        db.refresh(doc)
        # Status should NOT have changed to SAFE because it was ignored
        assert doc.security_status == DocumentSecurityStatus.QUARANTINED
    finally:
        settings.AWS_WEBHOOK_SECRET = original_secret


def test_aws_malware_webhook_invalid_transition(client: TestClient, db: Session):
    user_id, case_id, _headers = _setup_webhook_test_data(client, db)
    doc_id = generate_uuid7()

    doc = Document(
        id=doc_id,
        case_id=case_id,
        uploaded_by=user_id,
        filename="Pending.pdf",
        storage_key=f"documents/{doc_id}",
        mime_type="application/pdf",
        file_size=1000,
        security_status=DocumentSecurityStatus.PENDING,  # Invalid prior state for webhook
    )
    db.add(doc)
    db.commit()

    original_secret = settings.AWS_WEBHOOK_SECRET
    settings.AWS_WEBHOOK_SECRET = "test_webhook_secret_123"

    try:
        # Callback for PENDING document
        response = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": str(doc_id), "is_safe": True},
        )
        # Our endpoint lets unhandled exceptions bubble up to 500, which is correct for
        # invalid webhook triggers so that the queue can dead-letter it if needed.
        # UPDATE: Now raises ValidationError -> 422
        assert response.status_code == 422

        db.refresh(doc)
        assert doc.security_status == DocumentSecurityStatus.PENDING
    finally:
        settings.AWS_WEBHOOK_SECRET = original_secret


def test_aws_malware_webhook_malformed(client: TestClient):
    original_secret = settings.AWS_WEBHOOK_SECRET
    settings.AWS_WEBHOOK_SECRET = "test_webhook_secret_123"
    try:
        response = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": "not-a-uuid", "is_safe": True},
        )
        assert response.status_code == 422
    finally:
        settings.AWS_WEBHOOK_SECRET = original_secret


def test_aws_malware_webhook_unknown(client: TestClient):
    original_secret = settings.AWS_WEBHOOK_SECRET
    settings.AWS_WEBHOOK_SECRET = "test_webhook_secret_123"
    try:
        response = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": str(generate_uuid7()), "is_safe": True},
        )
        assert response.status_code == 404
    finally:
        settings.AWS_WEBHOOK_SECRET = original_secret


# --- Stripe Webhook Tests ---


def _make_stripe_sig(
    payload: dict, secret: str = "whsec_test_secret_123", timestamp: int | None = None
) -> tuple[str, bytes]:
    raw_body = json.dumps(payload).encode("utf-8")
    if timestamp is None:
        timestamp = int(datetime.now(UTC).timestamp())
    signed_payload = f"{timestamp}.".encode() + raw_body
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}", raw_body


def test_stripe_webhook_invalid_signature(client: TestClient):
    payload = {
        "id": "evt_test",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_test"}},
    }
    # 1. Missing signature header
    response = client.post("/api/v1/webhooks/stripe", json=payload)
    assert response.status_code == 401

    # 2. Forged signature
    sig_header, raw_body = _make_stripe_sig(payload, secret="wrong_secret")
    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": sig_header, "Content-Type": "application/json"},
        content=raw_body,
    )
    assert response.status_code == 401

    # 3. Expired timestamp (> 300s in past)
    old_time = int(datetime.now(UTC).timestamp()) - 400
    sig_header_old, raw_body_old = _make_stripe_sig(payload, timestamp=old_time)
    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={
            "Stripe-Signature": sig_header_old,
            "Content-Type": "application/json",
        },
        content=raw_body_old,
    )
    assert response.status_code == 401

    # 4. Tampered payload
    valid_sig, raw_body = _make_stripe_sig(payload)
    tampered_body = json.dumps({**payload, "tampered": True}).encode("utf-8")
    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": valid_sig, "Content-Type": "application/json"},
        content=tampered_body,
    )
    assert response.status_code == 401


def test_stripe_webhook_success(client: TestClient, db: Session):
    payment_id = generate_uuid7()
    provider_id = f"pi_mock_{payment_id}"

    client_user = User(
        id=generate_uuid7(),
        email="webhook_client@test.com",
        phone="8888888888",
        password_hash=hash_password("pass"),
        role=UserRole.CLIENT,
    )
    lawyer_user = User(
        id=generate_uuid7(),
        email="webhook_lawyer@test.com",
        phone="8888888889",
        password_hash=hash_password("pass"),
        role=UserRole.LAWYER,
    )
    db.add_all([client_user, lawyer_user])
    db.commit()

    client_profile = ClientProfile(
        id=generate_uuid7(), user_id=client_user.id, full_name="WH Client"
    )
    lawyer_profile = LawyerProfile(
        id=generate_uuid7(),
        user_id=lawyer_user.id,
        full_name="WH Lawyer",
        consultation_fee=1000.0,
    )
    db.add(client_profile)
    db.add(lawyer_profile)
    db.commit()

    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_profile.id,
        lawyer_id=lawyer_profile.id,
        status=ConsultationStatus.REQUESTED,
        scheduled_at=datetime.now(UTC),
        duration_minutes=30,
        fee_amount=1000.0,
        currency="INR",
    )
    db.add(consultation)
    db.commit()

    payment = Payment(
        id=payment_id,
        consultation_id=consultation.id,
        payer_user_id=client_user.id,
        amount=1000.0,
        currency="INR",
        status=PaymentStatus.CREATED,
        provider="stripe",
        provider_payment_id=provider_id,
    )
    db.add(payment)
    db.commit()

    payload = {
        "id": "evt_test_success_999",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": provider_id}},
    }

    sig_header, raw_body = _make_stripe_sig(payload)

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": sig_header, "Content-Type": "application/json"},
        content=raw_body,
    )
    assert response.status_code == 200

    db.refresh(payment)
    db.refresh(consultation)
    assert payment.status == PaymentStatus.SUCCEEDED
    assert consultation.status == ConsultationStatus.PAID

    # Idempotent replay of same event
    response2 = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": sig_header, "Content-Type": "application/json"},
        content=raw_body,
    )
    assert response2.status_code == 200
    assert response2.json()["status"] == "already_processed"


def test_duplicate_payments_webhook_route_removed(client: TestClient):
    """
    Verifies that the duplicate registration /api/v1/payments/webhooks/stripe has been
    completely removed and returns 404.
    """
    payload = {
        "id": "evt_test",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_test"}},
    }
    response = client.post("/api/v1/payments/webhooks/stripe", json=payload)
    assert response.status_code == 404
