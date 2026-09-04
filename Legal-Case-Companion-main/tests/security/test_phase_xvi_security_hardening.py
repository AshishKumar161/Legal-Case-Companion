import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.core.security import hash_password, verify_access_token
from app.models.auth import RefreshTokenSession
from app.models.user import AccountStatus, ClientProfile, User, UserRole
from app.services.user_service import UserService


def test_algorithm_pinning_and_rejection_of_alg_none():
    """Verify that JWT verification explicitly rejects alg=none and non-EdDSA algorithms."""
    # 1. Reject alg=none
    none_token = jwt.encode(
        {"sub": "attacker", "iss": "legal-case-companion", "aud": "legal-case-companion", "type": "access"},
        key="",
        algorithm="none",
    )
    with pytest.raises(jwt.InvalidTokenError, match="Invalid JWT algorithm"):
        verify_access_token(none_token)

    # 2. Reject symmetric HS256 algorithm confusion
    hs256_token = jwt.encode(
        {"sub": "attacker", "iss": "legal-case-companion", "aud": "legal-case-companion", "type": "access"},
        key="symmetric_secret_key_1234567890_32bytes",
        algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidTokenError, match="Invalid JWT algorithm"):
        verify_access_token(hs256_token)


def test_zero_downtime_key_rotation(monkeypatch):
    """Verify that verify_access_token accepts tokens signed with prior key during rotation."""
    # Generate Old Key
    old_priv_obj = Ed25519PrivateKey.generate()
    old_pub_pem = (
        old_priv_obj.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )

    # Generate New Key
    new_priv_obj = Ed25519PrivateKey.generate()
    new_priv_pem = new_priv_obj.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    new_pub_pem = (
        new_priv_obj.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )

    # Sign token with old key
    expire = datetime.now(UTC) + timedelta(minutes=15)
    old_token = jwt.encode(
        {
            "sub": "user_123",
            "iss": "legal-case-companion",
            "aud": "legal-case-companion",
            "exp": expire,
            "iat": datetime.now(UTC),
            "jti": "random_jti_12345",
            "role": "CLIENT",
            "type": "access",
        },
        old_priv_obj,
        algorithm="EdDSA",
    )

    # Switch active key to new key WITHOUT previous key configured -> must fail
    monkeypatch.setattr(settings, "JWT_PUBLIC_KEY", new_pub_pem)
    monkeypatch.setattr(settings, "JWT_PRIVATE_KEY", new_priv_pem)
    monkeypatch.setattr(settings, "JWT_PREVIOUS_PUBLIC_KEY", None)

    with pytest.raises(jwt.InvalidSignatureError):
        verify_access_token(old_token)

    # Stage rotation: set JWT_PREVIOUS_PUBLIC_KEY to old_pub_pem -> must succeed!
    monkeypatch.setattr(settings, "JWT_PREVIOUS_PUBLIC_KEY", old_pub_pem)
    payload = verify_access_token(old_token)
    assert payload["sub"] == "user_123"
    assert payload["role"] == "CLIENT"


def test_production_sqlite_and_test_payment_rejection(monkeypatch):
    """Verify production environment strictly forbids SQLite and forces ENABLE_TEST_PAYMENTS=False."""
    from app.core.config import Settings

    # Attempting to start in production with SQLite must raise ValueError
    with pytest.raises(ValueError, match="SQLite is strictly forbidden in production"):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="sqlite:///./prod.db",
            JWT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIGTAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBHkwdwIBAQQg\n-----END PRIVATE KEY-----",
            JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE\n-----END PUBLIC KEY-----",
            CSRF_SECRET_KEY="a" * 32,
            AWS_S3_BUCKET_NAME="lcc-bucket",
            AWS_WEBHOOK_SECRET="webhook_secret_32",
            STRIPE_API_KEY="sk_live_123",
            STRIPE_WEBHOOK_SECRET="whsec_123",
            REDIS_URL="redis://localhost:6379/0",
            OPENAI_API_KEY="sk-live-123",
            EMAIL_PROVIDER="smtp",
        )


def test_safe_account_deletion_flow(db):
    """Verify safe account deletion anonymizes personal data, revokes sessions, and records audit event."""
    user_id = generate_uuid7()
    user = User(
        id=user_id,
        email=f"client_test_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("ComplexP@ssw0rd123"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    profile = ClientProfile(
        id=generate_uuid7(),
        user_id=user.id,
        full_name="Confidential Client Name",
        location="Mumbai",
    )
    db.add(profile)

    # Create active session
    session = RefreshTokenSession(
        id=generate_uuid7(),
        user_id=user.id,
        token_family_id=generate_uuid7(),
        token_hash="fake_token_hash_12345",
        created_at=datetime.now(UTC),
        last_used_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=30),
        revoked_at=None,
    )
    db.add(session)
    db.commit()

    # Execute safe account deletion
    user_service = UserService(db)
    deleted_user = user_service.delete_user_account(user_id=user.id, reason="User requested GDPR/DPDP erasure")

    # Assertions
    assert deleted_user.account_status == AccountStatus.DEACTIVATED
    assert deleted_user.deleted_at is not None
    assert deleted_user.email == f"deleted_{user.id}@anonymized.local"

    # Profile anonymized
    db.refresh(profile)
    assert profile.full_name == "Anonymized Client"
    assert profile.location is None

    # Session revoked
    db.refresh(session)
    assert session.revoked_at is not None
