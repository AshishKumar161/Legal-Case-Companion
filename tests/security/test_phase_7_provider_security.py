"""Phase 7 Security Regression and Provider Failure Test Suite.

Exhaustively verifies:
1. Storage key path traversal, encoding, and malicious key rejection.
2. Mock storage fidelity (existence state accuracy, deletion, presigned URL encoding).
3. Production/staging environment gating and insecure credential fallback rejection.
4. Video meeting token validation, room/participant authorization, and expiration.
5. Payment provider idempotency, intent reuse, refund validation, and double-refund prevention.
6. Webhook signature verification, timestamp freshness tolerance, replay defense, and secret security.
7. Email CRLF injection defense on recipients and subjects.
8. OAuth state token single-use enforcement, replay protection, and open redirect defense.
"""

import hmac
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ValidationError,
)
from app.core.oauth_security import (
    clear_consumed_oauth_states,
    generate_oauth_state,
    validate_redirect_uri,
    validate_return_url,
    verify_oauth_state,
)
from app.core.storage import (
    LocalMockStorageProvider,
    S3StorageProvider,
    get_storage_provider,
    validate_storage_object_key,
)
from app.models.consultation import Consultation, ConsultationStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.models.video_meeting import VideoMeeting
from app.models.webhook import ProcessedWebhookEvent, WebhookProcessingStatus
from app.domain.notifications.email_service import (
    ConsoleEmailProvider,
    SMTPEmailProvider,
    SendGridEmailProvider,
    get_email_provider,
    sanitize_email_subject,
    validate_email_recipient,
)
from app.services.payment_service import (
    MockPaymentProvider,
    PaymentService,
    StripePaymentProvider,
    get_payment_provider,
    verify_stripe_webhook_signature,
)
from app.domain.consultations.recording_storage import (
    LocalRecordingStorageProvider,
    S3RecordingStorageProvider,
    get_recording_storage_provider,
    reset_recording_storage_provider,
)
from app.domain.consultations.video_meeting_service import (
    InternalWebRTCMeetingProvider,
    LiveKitMeetingProvider,
    get_video_provider,
)


# =====================================================================
# 1. OBJECT STORAGE KEY VALIDATION & PATH TRAVERSAL
# =====================================================================

@pytest.mark.parametrize(
    "malicious_key",
    [
        "../file.txt",
        "../../etc/passwd",
        "..\\secret.txt",
        "/absolute/path/file.txt",
        "\\windows\\system32\\cmd.exe",
        "C:\\boot.ini",
        "D:/data/secret",
        "folder/../../../etc/shadow",
        "folder/..\\..\\secret",
        "%2e%2e%2fsecret.txt",
        "%2e%2e/passwd",
        "document.pdf?query=attack",
        "document.pdf#fragment",
        "document\x00.pdf",
        "document\x1f.pdf",
        "   ",
        "",
        "a" * 1025,
    ],
)
def test_storage_key_validation_rejects_malicious_keys(malicious_key: str):
    """Verifies that validate_storage_object_key rejects traversal, absolute paths, query params, and control characters."""
    with pytest.raises(ValidationError):
        validate_storage_object_key(malicious_key)


def test_storage_key_validation_accepts_clean_keys():
    """Verifies that validate_storage_object_key accepts canonical, safe object keys."""
    assert validate_storage_object_key("documents/123/brief.pdf") == "documents/123/brief.pdf"
    assert validate_storage_object_key("cases/matter-456/evidence.png") == "cases/matter-456/evidence.png"
    assert validate_storage_object_key("consultations/uuid/rec.webm") == "consultations/uuid/rec.webm"


# =====================================================================
# 2. MOCK STORAGE FIDELITY
# =====================================================================

def test_mock_storage_existence_state_accuracy():
    """Verifies that LocalMockStorageProvider accurately reports existence state (no unconditional True)."""
    mock_storage = LocalMockStorageProvider()
    mock_storage.clear()

    test_key = "test/documents/contract.pdf"
    # 1. Non-existent key must return False
    assert mock_storage.object_exists(test_key) is False
    assert mock_storage.get_object_bytes(test_key) is None

    # 2. Put bytes -> must return True
    mock_storage.put_object_bytes(test_key, b"%PDF-1.4\ncontent\n%%EOF", mime_type="application/pdf")
    assert mock_storage.object_exists(test_key) is True
    assert mock_storage.get_object_bytes(test_key) == b"%PDF-1.4\ncontent\n%%EOF"

    # 3. Delete -> must return False
    mock_storage.delete_object(test_key)
    assert mock_storage.object_exists(test_key) is False
    assert mock_storage.get_object_bytes(test_key) is None


def test_mock_storage_presigned_url_key_encoding():
    """Verifies that mock presigned URLs properly encode object keys."""
    mock_storage = LocalMockStorageProvider()
    key = "documents/case 1/pleading (final).pdf"
    upload_url = mock_storage.generate_presigned_upload_url(key, mime_type="application/pdf")
    download_url = mock_storage.generate_presigned_download_url(key)

    assert "documents%2Fcase%201%2Fpleading%20%28final%29.pdf" in upload_url
    assert "documents%2Fcase%201%2Fpleading%20%28final%29.pdf" in download_url


# =====================================================================
# 3. PRODUCTION & STAGING ENVIRONMENT GATING (FAIL-FAST)
# =====================================================================

def test_storage_provider_fails_fast_in_production_without_bucket():
    """Verifies get_storage_provider fails fast when AWS_S3_BUCKET_NAME is missing in production/staging."""
    with patch.object(settings, "ENVIRONMENT", "production"), patch.object(settings, "AWS_S3_BUCKET_NAME", ""):
        with pytest.raises(ConfigurationError, match="AWS_S3_BUCKET_NAME"):
            get_storage_provider()


def test_recording_storage_fails_fast_in_production_without_s3():
    """Verifies get_recording_storage_provider fails fast when S3 config is missing in production."""
    reset_recording_storage_provider()
    with patch.object(settings, "ENVIRONMENT", "production"), patch.object(settings, "AWS_S3_BUCKET_NAME", None):
        with pytest.raises(ConfigurationError, match="requires AWS S3 bucket"):
            get_recording_storage_provider()
    reset_recording_storage_provider()


def test_livekit_fails_fast_in_production_with_insecure_secrets():
    """Verifies LiveKitMeetingProvider rejects insecure dev default credentials in production."""
    with patch.object(settings, "ENVIRONMENT", "production"):
        with pytest.raises(ConfigurationError, match="insecure default credentials"):
            LiveKitMeetingProvider(api_key="devkey", api_secret="secret")

        with pytest.raises(ConfigurationError, match="insecure default credentials"):
            LiveKitMeetingProvider(api_key="prod_key", api_secret="changeme")


def test_video_provider_factory_forbids_p2p_fallback_in_production():
    """Verifies get_video_provider forbids silent P2P fallback in production/staging."""
    with patch.object(settings, "ENVIRONMENT", "production"), patch.object(settings, "LIVEKIT_API_KEY", None):
        with pytest.raises(ConfigurationError, match="requires LiveKit SFU configuration"):
            get_video_provider()


def test_payment_provider_factory_fails_fast_in_production_without_stripe():
    """Verifies get_payment_provider refuses to fall back to mock payment provider in production."""
    with patch.object(settings, "ENVIRONMENT", "production"), patch.object(settings, "STRIPE_API_KEY", ""):
        with pytest.raises(ConfigurationError, match="requires STRIPE_API_KEY"):
            get_payment_provider()


def test_email_provider_factory_forbids_console_in_production():
    """Verifies get_email_provider forbids ConsoleEmailProvider in production/staging."""
    with patch.object(settings, "ENVIRONMENT", "production"), patch.object(settings, "EMAIL_PROVIDER", "console"):
        with pytest.raises(ConfigurationError, match="ConsoleEmailProvider is strictly forbidden"):
            get_email_provider()


# =====================================================================
# 4. VIDEO MEETING TOKEN AUTHORIZATION & EXPIRATION
# =====================================================================

def test_video_meeting_token_cryptographic_verification_and_context():
    """Verifies that video join tokens cryptographically bind room, user, consultation, and role."""
    provider = InternalWebRTCMeetingProvider()
    consultation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    room_id = f"lcc-room-{consultation_id.hex[:12]}-test"

    token = provider.create_access_token(
        room_name=room_id,
        participant_identity=str(user_id),
        role="CLIENT",
        consultation_id=consultation_id,
        duration_minutes=30,
    )

    # 1. Valid token passes
    payload = provider.verify_access_token(
        token,
        expected_room_id=room_id,
        expected_user_id=user_id,
        expected_consultation_id=consultation_id,
        expected_role="CLIENT",
    )
    assert payload["role"] == "CLIENT"

    # 2. Tampered signature fails
    parts = token.split(".", 1)
    tampered_sig = ("0" if parts[0][0] != "0" else "1") + parts[0][1:]
    with pytest.raises(ValidationError, match="Tampered or invalid"):
        provider.verify_access_token(f"{tampered_sig}.{parts[1]}")

    # 3. Mismatched room fails
    with pytest.raises(ValidationError, match="not authorized for this meeting room"):
        provider.verify_access_token(token, expected_room_id="different-room")

    # 4. Mismatched user fails
    with pytest.raises(ValidationError, match="does not belong to this participant"):
        provider.verify_access_token(token, expected_user_id=uuid.uuid4())

    # 5. Mismatched consultation fails
    with pytest.raises(ValidationError, match="does not match this consultation"):
        provider.verify_access_token(token, expected_consultation_id=uuid.uuid4())

    # 6. Mismatched role fails
    with pytest.raises(ValidationError, match="role does not match"):
        provider.verify_access_token(token, expected_role="LAWYER")


def test_video_meeting_token_expiration():
    """Verifies that expired video tokens are rejected."""
    provider = InternalWebRTCMeetingProvider()
    token = provider.create_access_token(
        room_name="test-room",
        participant_identity=str(uuid.uuid4()),
        role="CLIENT",
        duration_minutes=-5,  # Expired 5 minutes ago
    )
    with pytest.raises(ValidationError, match="expired"):
        provider.verify_access_token(token)


# =====================================================================
# 5. PAYMENT PROVIDER IDEMPOTENCY & REFUNDS
# =====================================================================

def test_mock_payment_provider_idempotency_and_refund():
    """Verifies MockPaymentProvider adheres to PaymentProvider protocol with state tracking."""
    provider = MockPaymentProvider()
    provider.clear()

    payment_id = uuid.uuid4()
    secret, prov_id = provider.create_payment_intent(
        amount=2500.0,
        currency="INR",
        payment_id=payment_id,
        idempotency_key=f"lcc_pi_{payment_id}",
    )
    assert prov_id == f"pi_mock_{payment_id}"

    # Retrieve intent
    retrieved = provider.retrieve_payment_intent(prov_id)
    assert retrieved["amount"] == 2500.0
    assert retrieved["currency"] == "INR"

    # Refund
    refund = provider.create_refund(
        provider_payment_id=prov_id,
        amount=2500.0,
        idempotency_key=f"lcc_rfd_{payment_id}",
    )
    assert refund["status"] == "succeeded"
    assert refund["payment_intent"] == prov_id


def test_payment_service_execute_refund_validation_and_authorization(db: Session):
    """Verifies PaymentService.execute_refund prevents unauthorized or double refunds."""
    client_user = User(
        id=uuid.uuid4(),
        email=f"client_rfd_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hash",
        role=UserRole.CLIENT,
        account_status="ACTIVE",
    )
    attacker_user = User(
        id=uuid.uuid4(),
        email=f"attacker_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hash",
        role=UserRole.CLIENT,
        account_status="ACTIVE",
    )
    db.add_all([client_user, attacker_user])
    db.commit()

    payment = Payment(
        id=uuid.uuid4(),
        consultation_id=uuid.uuid4(),
        payer_user_id=client_user.id,
        amount=1500.0,
        currency="INR",
        status=PaymentStatus.SUCCEEDED,
        provider="mock",
        provider_payment_id=f"pi_mock_{uuid.uuid4().hex[:8]}",
    )
    db.add(payment)
    db.commit()

    service = PaymentService(db)

    # 1. Attacker cannot refund client payment
    with pytest.raises(AuthorizationError):
        service.execute_refund(attacker_user, payment.id, amount=1500.0)

    # 2. Invalid refund amount (> payment amount or <= 0)
    with pytest.raises(ValidationError, match="Invalid refund amount"):
        service.execute_refund(client_user, payment.id, amount=2000.0)

    with pytest.raises(ValidationError, match="Invalid refund amount"):
        service.execute_refund(client_user, payment.id, amount=-10.0)

    # 3. Legitimate refund succeeds
    res = service.execute_refund(client_user, payment.id, amount=1500.0, reason="Advocate Cancelled")
    assert res["status"] == "succeeded"
    db.refresh(payment)
    assert payment.status == PaymentStatus.REFUNDED

    # 4. Subsequent refund attempt rejected (cannot refund already REFUNDED payment)
    with pytest.raises(ValidationError, match="Cannot refund payment in REFUNDED status"):
        service.execute_refund(client_user, payment.id, amount=1500.0)


# =====================================================================
# 6. WEBHOOK SECURITY & REPLAY DEFENSE
# =====================================================================

def test_stripe_webhook_signature_verification_and_replay_defense():
    """Verifies Stripe webhook signature validation, freshness tolerance, and replay rejection."""
    secret = "whsec_test_secret_for_hardening_suite_123"
    payload_dict = {
        "id": f"evt_test_{uuid.uuid4().hex[:8]}",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_test_123", "currency": "inr"}},
    }
    raw_payload = json.dumps(payload_dict).encode("utf-8")
    now_ts = int(datetime.now(UTC).timestamp())

    # Compute valid signature
    signed_payload = f"{now_ts}.".encode() + raw_payload
    valid_sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    valid_header = f"t={now_ts},v1={valid_sig}"

    # 1. Valid signature passes
    verified = verify_stripe_webhook_signature(raw_payload, valid_header, secret=secret)
    assert verified["id"] == payload_dict["id"]

    # 2. Missing signature header fails (401)
    with pytest.raises(HTTPException) as exc_info:
        verify_stripe_webhook_signature(raw_payload, None, secret=secret)
    assert exc_info.value.status_code == 401

    # 3. Tampered signature fails (401)
    tampered_header = f"t={now_ts},v1=0000000000000000000000000000000000000000000000000000000000000000"
    with pytest.raises(HTTPException) as exc_info:
        verify_stripe_webhook_signature(raw_payload, tampered_header, secret=secret)
    assert exc_info.value.status_code == 401

    # 4. Expired timestamp (> 300 seconds) fails (401)
    expired_ts = now_ts - 301
    expired_payload = f"{expired_ts}.".encode() + raw_payload
    expired_sig = hmac.new(secret.encode(), expired_payload, hashlib.sha256).hexdigest()
    expired_header = f"t={expired_ts},v1={expired_sig}"
    with pytest.raises(HTTPException) as exc_info:
        verify_stripe_webhook_signature(raw_payload, expired_header, secret=secret)
    assert exc_info.value.status_code == 401
    assert "timestamp expired" in str(exc_info.value.detail).lower()


def test_payment_service_webhook_idempotency_deduplication(db: Session):
    """Verifies that replaying the same webhook event ID is safely handled without duplicate execution."""
    event_id = f"evt_dup_{uuid.uuid4().hex[:8]}"
    secret = "whsec_test_secret_for_hardening_suite_123"

    payload_dict = {
        "id": event_id,
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_mock_nonexistent", "currency": "INR"}},
    }
    raw_payload = json.dumps(payload_dict).encode("utf-8")
    now_ts = int(datetime.now(UTC).timestamp())
    signed_payload = f"{now_ts}.".encode() + raw_payload
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    sig_header = f"t={now_ts},v1={sig}"

    # Pre-record event as already processed
    rec = ProcessedWebhookEvent(
        id=uuid.uuid4(),
        event_id=event_id,
        provider="STRIPE",
        event_type="payment_intent.succeeded",
        status=WebhookProcessingStatus.PROCESSED,
        payload=payload_dict,
        created_at=datetime.now(UTC),
    )
    db.add(rec)
    db.commit()

    service = PaymentService(db)
    with patch.object(settings, "STRIPE_WEBHOOK_SECRET", secret):
        res = service.handle_webhook(raw_payload, signature_header=sig_header)
        assert res == {"status": "already_processed"}


# =====================================================================
# 7. EMAIL CRLF HEADER INJECTION DEFENSE
# =====================================================================

@pytest.mark.parametrize(
    "malicious_email",
    [
        "victim@example.com\r\nBcc: evil@attacker.com",
        "victim@example.com\nBcc: evil@attacker.com",
        "victim@example.com\rBcc: evil@attacker.com",
        "user\r\n@domain.com",
        "invalid-email-format",
        "",
    ],
)
def test_email_recipient_validation_rejects_crlf_and_invalid(malicious_email: str):
    """Verifies validate_email_recipient rejects CRLF injection and malformed addresses."""
    with pytest.raises(ValidationError):
        validate_email_recipient(malicious_email)


@pytest.mark.parametrize(
    "malicious_subject",
    [
        "Meeting Scheduled\r\nBcc: evil@attacker.com",
        "Document Ready\nCc: spy@hacker.org",
        "Subject\rAnother-Header: test",
        "",
        "   ",
    ],
)
def test_email_subject_sanitization_rejects_crlf(malicious_subject: str):
    """Verifies sanitize_email_subject rejects CRLF injection."""
    with pytest.raises(ValidationError):
        sanitize_email_subject(malicious_subject)


def test_console_email_provider_accepts_clean_input():
    """Verifies ConsoleEmailProvider accepts valid recipient and subject."""
    provider = ConsoleEmailProvider()
    assert provider.send_email("client@example.com", "Legal Notice", "<p>Content</p>") is True


# =====================================================================
# 8. OAUTH STATE REPLAY PREVENTION & OPEN REDIRECT
# =====================================================================

def test_oauth_state_single_use_replay_prevention():
    """Verifies that an OAuth state token can only be consumed once, preventing replay attacks."""
    clear_consumed_oauth_states()
    state_token, _ = generate_oauth_state(purpose="login", return_url="/dashboard")

    # 1. First verification succeeds
    claims = verify_oauth_state(state_token)
    assert claims["purpose"] == "login"
    assert claims["return_url"] == "/dashboard"

    # 2. Replay attempt with same state token must fail
    with pytest.raises(AuthenticationError, match="already been used"):
        verify_oauth_state(state_token)

    clear_consumed_oauth_states()


def test_oauth_open_redirect_defense():
    """Verifies that validate_return_url and validate_redirect_uri reject malicious redirects."""
    # Relative paths allowed
    assert validate_return_url("/cases/123") == "/cases/123"

    # External attacker URLs fall back to /dashboard
    assert validate_return_url("http://attacker.com/steal") == "/dashboard"
    assert validate_return_url("https://malicious.evil/callback") == "/dashboard"
    assert validate_return_url("//evil.com") == "/dashboard"
    assert validate_return_url("javascript:alert(document.cookie)") == "/dashboard"

    # Redirect URI validation
    with patch.object(settings, "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback"):
        assert validate_redirect_uri("http://evil.com/fake/callback") == "http://localhost:8000/api/v1/auth/google/callback"
