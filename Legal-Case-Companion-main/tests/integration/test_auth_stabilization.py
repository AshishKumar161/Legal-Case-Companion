from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.identifiers import generate_uuid7
from app.core.oauth_security import (
    generate_oauth_state,
    validate_return_url,
    verify_oauth_state,
)
from app.core.security import create_access_token, hash_password
from app.models.auth import UserExternalIdentity
from app.models.user import AccountStatus, User, UserRole
from app.services.auth_service import AuthService
from app.services.google_oauth_service import GoogleOAuthService


@pytest.fixture(scope="module")
def rsa_key_pair():
    """Generates an RSA key pair for testing Google OIDC token signatures."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


def create_mock_google_id_token(
    private_key: Any,
    sub: str = "google-sub-12345",
    email: str = "googleuser@example.com",
    email_verified: bool = True,
    name: str = "Google Test User",
    iss: str = "https://accounts.google.com",
    aud: str = "mock-google-client-id",
    exp_seconds: int = 3600,
    nonce: str | None = None,
) -> str:
    """Helper to generate signed mock Google OIDC ID tokens."""
    now = datetime.now(UTC)
    payload = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "name": name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=exp_seconds)).timestamp()),
    }
    if nonce:
        payload["nonce"] = nonce

    return jwt.encode(payload, private_key, algorithm="RS256")


# ==========================================
# 1. PASSWORD FLOW TESTS
# ==========================================


def test_password_registration_and_email_normalization(
    client: TestClient, db: Session
):
    """Verifies user registration, email normalization, and profile creation."""
    payload = {
        "email": "  TestUser_Normalized@Example.Com  ",
        "password": "StrongPassword123!",
        "role": "CLIENT",
        "full_name": "Test User Normalized",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "testuser_normalized@example.com"
    assert data["role"] == "CLIENT"

    # Duplicate registration must fail
    dup_res = client.post("/api/v1/auth/register", json=payload)
    assert dup_res.status_code == 400
    assert dup_res.json()["error"]["code"] == "EMAIL_EXISTS"


def test_password_login_and_cookie_generation(client: TestClient, db: Session):
    """Verifies login generates access token, refresh token cookie, and csrf cookie."""
    # Register user
    reg_payload = {
        "email": "login_cookie_test@example.com",
        "password": "ValidPassword123!",
        "role": "CLIENT",
        "full_name": "Cookie Test User",
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    # Login
    login_payload = {
        "email": "login_cookie_test@example.com",
        "password": "ValidPassword123!",
    }
    res = client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Check cookies
    cookies = res.cookies
    assert "refresh_token" in cookies
    assert "csrf_token" in cookies


def test_password_login_failures_and_audit(client: TestClient, db: Session):
    """Verifies wrong password and non-existent user fail and record audit events."""
    # Register user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "audit_fail_test@example.com",
            "password": "CorrectPassword123!",
            "role": "CLIENT",
            "full_name": "Audit Fail User",
        },
    )

    # Wrong password
    res = client.post(
        "/api/v1/auth/login",
        json={
            "email": "audit_fail_test@example.com",
            "password": "WrongPassword123!",
        },
    )
    assert res.status_code == 401

    # Non-existent user
    res_none = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent_999@example.com",
            "password": "SomePassword123!",
        },
    )
    assert res_none.status_code == 401


def test_suspended_account_rejection(client: TestClient, db: Session):
    """Verifies suspended accounts cannot log in."""
    user = User(
        id=generate_uuid7(),
        email="suspended_user@example.com",
        password_hash=hash_password("Password123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.SUSPENDED,
    )
    db.add(user)
    db.commit()

    res = client.post(
        "/api/v1/auth/login",
        json={
            "email": "suspended_user@example.com",
            "password": "Password123!",
        },
    )
    assert res.status_code == 401
    assert "inactive" in res.json()["error"]["message"].lower()


def test_refresh_token_rotation_and_csrf_validation(client: TestClient, db: Session):
    """Verifies refresh token rotation requires CSRF validation and issues new tokens."""
    # Register & login
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh_flow_test@example.com",
            "password": "Password123!",
            "role": "CLIENT",
            "full_name": "Refresh User",
        },
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "email": "refresh_flow_test@example.com",
            "password": "Password123!",
        },
    )
    csrf_token = login_res.cookies.get("csrf_token")
    refresh_token = login_res.cookies.get("refresh_token")

    # Refresh without CSRF header should fail
    client.cookies.set("refresh_token", refresh_token)
    client.cookies.set("csrf_token", csrf_token)
    res_no_header = client.post("/api/v1/auth/refresh")
    assert res_no_header.status_code == 401

    # Refresh with valid CSRF header succeeds
    res_valid = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_valid.status_code == 200
    new_data = res_valid.json()
    assert "access_token" in new_data
    assert new_data["access_token"] != login_res.json()["access_token"]


def test_refresh_token_reuse_family_revocation(client: TestClient, db: Session):
    """Verifies presenting a revoked refresh token revokes the entire token family (theft detection)."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "theft_detect_test@example.com",
            "password": "Password123!",
            "role": "CLIENT",
            "full_name": "Theft User",
        },
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "email": "theft_detect_test@example.com",
            "password": "Password123!",
        },
    )
    old_refresh = login_res.cookies.get("refresh_token")
    csrf_token = login_res.cookies.get("csrf_token")

    # Rotate once
    res1 = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token},
        cookies={"refresh_token": old_refresh, "csrf_token": csrf_token},
    )
    assert res1.status_code == 200
    new_refresh = res1.cookies.get("refresh_token")
    new_csrf = res1.cookies.get("csrf_token")

    # Present OLD rotated token again (Replay attack simulation)
    replay_res = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": new_csrf},
        cookies={"refresh_token": old_refresh, "csrf_token": new_csrf},
    )
    assert replay_res.status_code == 401

    # Now the NEW token must ALSO be invalidated because the family was revoked
    subsequent_res = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": new_csrf},
        cookies={"refresh_token": new_refresh, "csrf_token": new_csrf},
    )
    assert subsequent_res.status_code == 401


def test_logout_revokes_session_and_clears_cookies(client: TestClient, db: Session):
    """Verifies logout revokes the session and clears cookies."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout_test@example.com",
            "password": "Password123!",
            "role": "CLIENT",
            "full_name": "Logout User",
        },
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "email": "logout_test@example.com",
            "password": "Password123!",
        },
    )
    token = login_res.json()["access_token"]
    refresh_token = login_res.cookies.get("refresh_token")
    csrf_token = login_res.cookies.get("csrf_token")

    # Logout
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
        cookies={"refresh_token": refresh_token},
    )
    assert logout_res.status_code == 200

    # Subsequent refresh must fail
    res_after = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token},
        cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
    )
    assert res_after.status_code == 401


def test_password_change_revokes_all_sessions(client: TestClient, db: Session):
    """Verifies password change revokes all active refresh token sessions."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "pwd_change_test@example.com",
            "password": "OldPassword123!",
            "role": "CLIENT",
            "full_name": "Password Change User",
        },
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "email": "pwd_change_test@example.com",
            "password": "OldPassword123!",
        },
    )
    token = login_res.json()["access_token"]
    refresh_token = login_res.cookies.get("refresh_token")
    csrf_token = login_res.cookies.get("csrf_token")

    # Change password
    change_res = client.post(
        "/api/v1/auth/password/change",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "OldPassword123!",
            "new_password": "NewStrongPassword123!",
        },
    )
    assert change_res.status_code == 200

    # Old refresh token is now revoked
    ref_res = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token},
        cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
    )
    assert ref_res.status_code == 401


# ==========================================
# 2. OAUTH STATE & SECURITY TESTS
# ==========================================


def test_oauth_state_generation_and_verification():
    """Verifies state tokens are cryptographically signed and reject tampering."""
    state, nonce = generate_oauth_state(purpose="login", return_url="/cases/123")
    payload = verify_oauth_state(state)
    assert payload["purpose"] == "login"
    assert payload["nonce"] == nonce
    assert payload["return_url"] == "/cases/123"

    # Tampered state must be rejected
    tampered_state = state[:-5] + "XXXXX"
    with pytest.raises(AuthenticationError):
        verify_oauth_state(tampered_state)


def test_open_redirect_protection():
    """Verifies open redirect prevention."""
    assert validate_return_url("/cases/123") == "/cases/123"
    assert validate_return_url("http://localhost:3000/dashboard") == "http://localhost:3000/dashboard"
    # Attacker URLs must fall back to /dashboard
    assert validate_return_url("http://evil-attacker.com/steal") == "/dashboard"
    assert validate_return_url("//evil-attacker.com") == "/dashboard"
    assert validate_return_url("javascript:alert(1)") == "/dashboard"


# ==========================================
# 3. GOOGLE OAUTH / OIDC FLOW TESTS
# ==========================================


def test_google_login_url_generation(client: TestClient):
    """Verifies GET /auth/google/login generates authorization URL with signed state."""
    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-google-client-id"), \
         patch.object(settings, "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback"):
        res = client.get("/api/v1/auth/google/login?return_url=/cases/abc")
        assert res.status_code == 200
        data = res.json()
        assert "authorization_url" in data
        assert "accounts.google.com" in data["authorization_url"]
        assert "mock-google-client-id" in data["authorization_url"]
        assert "state" in data


def test_google_direct_auth_new_user(
    client: TestClient, db: Session, rsa_key_pair: tuple[Any, Any]
):
    """Verifies Google auth creates a new User with default role CLIENT, ClientProfile, and UserExternalIdentity."""
    priv_key, pub_key = rsa_key_pair
    id_token = create_mock_google_id_token(
        priv_key,
        sub="google-sub-user-1",
        email="google_new_user@example.com",
        name="Google New User",
        aud="mock-google-client-id",
    )

    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-google-client-id"), \
         patch.object(GoogleOAuthService, "validate_id_token", lambda self, tok, expected_nonce=None: jwt.decode(tok, pub_key, algorithms=["RS256"], audience="mock-google-client-id", issuer=settings.GOOGLE_ISSUERS)):
        res = client.post(
            "/api/v1/auth/google/direct",
            json={"id_token": id_token},
        )
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert "refresh_token" in res.cookies
        assert "csrf_token" in res.cookies

        # Verify in database
        identity = (
            db.query(UserExternalIdentity)
            .filter(
                UserExternalIdentity.provider == "GOOGLE",
                UserExternalIdentity.provider_subject == "google-sub-user-1",
            )
            .first()
        )
        assert identity is not None
        assert identity.email == "google_new_user@example.com"
        assert identity.email_verified is True

        user = db.query(User).filter(User.id == identity.user_id).first()
        assert user is not None
        assert user.role == UserRole.CLIENT
        assert user.password_hash is None  # Google account has no initial password
        assert user.client_profile is not None
        assert user.client_profile.full_name == "Google New User"


def test_google_direct_auth_existing_google_identity(
    client: TestClient, db: Session, rsa_key_pair: tuple[Any, Any]
):
    """Verifies repeated Google login returns tokens for the existing user without creating duplicates."""
    priv_key, pub_key = rsa_key_pair
    id_token = create_mock_google_id_token(
        priv_key,
        sub="google-sub-user-existing",
        email="google_existing_user@example.com",
        name="Existing Google User",
        aud="mock-google-client-id",
    )

    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-google-client-id"), \
         patch.object(GoogleOAuthService, "validate_id_token", lambda self, tok, expected_nonce=None: jwt.decode(tok, pub_key, algorithms=["RS256"], audience="mock-google-client-id", issuer=settings.GOOGLE_ISSUERS)):
        # First login
        res1 = client.post("/api/v1/auth/google/direct", json={"id_token": id_token})
        assert res1.status_code == 200

        # Second login
        res2 = client.post("/api/v1/auth/google/direct", json={"id_token": id_token})
        assert res2.status_code == 200

        # Verify only one user and identity exists
        identities = (
            db.query(UserExternalIdentity)
            .filter(UserExternalIdentity.provider_subject == "google-sub-user-existing")
            .all()
        )
        assert len(identities) == 1


def test_google_auth_safe_account_linking_with_existing_password_user(
    client: TestClient, db: Session, rsa_key_pair: tuple[Any, Any]
):
    """Verifies that when a verified Google identity matches an existing email, it safely links to the existing account."""
    priv_key, pub_key = rsa_key_pair
    email = "pre_existing_client@example.com"

    # Register via password first
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "role": "CLIENT",
            "full_name": "Pre Existing Client",
        },
    )

    # Now login with Google with same verified email
    id_token = create_mock_google_id_token(
        priv_key,
        sub="google-sub-linked-123",
        email=email,
        name="Pre Existing Client",
        aud="mock-google-client-id",
    )

    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-google-client-id"), \
         patch.object(GoogleOAuthService, "validate_id_token", lambda self, tok, expected_nonce=None: jwt.decode(tok, pub_key, algorithms=["RS256"], audience="mock-google-client-id", issuer=settings.GOOGLE_ISSUERS)):
        res = client.post("/api/v1/auth/google/direct", json={"id_token": id_token})
        assert res.status_code == 200

        # Verify user now has both password_hash and external_identities
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        assert user.password_hash is not None
        assert len(user.external_identities) == 1
        assert user.external_identities[0].provider_subject == "google-sub-linked-123"


def test_google_auth_unverified_email_rejection(
    client: TestClient, db: Session, rsa_key_pair: tuple[Any, Any]
):
    """Verifies that an unverified Google account (email_verified=False) is strictly rejected."""
    priv_key, pub_key = rsa_key_pair
    id_token = create_mock_google_id_token(
        priv_key,
        sub="google-unverified-sub",
        email="unverified_google@example.com",
        email_verified=False,  # UNVERIFIED
        aud="mock-google-client-id",
    )

    service = GoogleOAuthService()
    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-google-client-id"):
        with pytest.raises(Exception) as exc_info:
            service.validate_id_token(id_token, override_public_key=pub_key)
        assert "not verified" in str(exc_info.value).lower()


def test_google_auth_expired_token_rejection(
    client: TestClient, db: Session, rsa_key_pair: tuple[Any, Any]
):
    """Verifies expired Google ID tokens are rejected."""
    priv_key, pub_key = rsa_key_pair
    id_token = create_mock_google_id_token(
        priv_key,
        sub="google-expired-sub",
        email="expired_google@example.com",
        exp_seconds=-10,  # EXPIRED
        aud="mock-google-client-id",
    )

    service = GoogleOAuthService()
    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-google-client-id"):
        with pytest.raises(Exception) as exc_info:
            service.validate_id_token(id_token, override_public_key=pub_key)
        assert "expired" in str(exc_info.value).lower()


def test_google_auth_wrong_audience_rejection(
    client: TestClient, db: Session, rsa_key_pair: tuple[Any, Any]
):
    """Verifies Google ID tokens for a different client ID are rejected."""
    priv_key, pub_key = rsa_key_pair
    id_token = create_mock_google_id_token(
        priv_key,
        sub="google-wrong-aud-sub",
        email="wrong_aud@example.com",
        aud="some-other-attacker-client-id",
    )

    service = GoogleOAuthService()
    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-google-client-id"):
        with pytest.raises(Exception) as exc_info:
            service.validate_id_token(id_token, override_public_key=pub_key)
        assert "audience" in str(exc_info.value).lower()


def test_google_auth_wrong_issuer_rejection(
    client: TestClient, db: Session, rsa_key_pair: tuple[Any, Any]
):
    """Verifies tokens with non-Google issuer are rejected."""
    priv_key, pub_key = rsa_key_pair
    id_token = create_mock_google_id_token(
        priv_key,
        sub="google-wrong-iss-sub",
        email="wrong_iss@example.com",
        iss="https://evil-issuer.com",
        aud="mock-google-client-id",
    )

    service = GoogleOAuthService()
    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-google-client-id"):
        with pytest.raises(Exception) as exc_info:
            service.validate_id_token(id_token, override_public_key=pub_key)
        assert "issuer" in str(exc_info.value).lower()


def test_google_callback_with_state_and_code_exchange(
    client: TestClient, db: Session, rsa_key_pair: tuple[Any, Any]
):
    """Verifies complete GET and POST /auth/google/callback authorization code exchange flow."""
    priv_key, pub_key = rsa_key_pair
    state_token, nonce = generate_oauth_state(purpose="login", return_url="/dashboard")

    id_token = create_mock_google_id_token(
        priv_key,
        sub="google-callback-sub-1",
        email="callback_user@example.com",
        nonce=nonce,
        aud="mock-google-client-id",
    )

    mock_tokens = {"id_token": id_token, "access_token": "mock-google-access-token"}

    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-google-client-id"), \
         patch.object(settings, "GOOGLE_CLIENT_SECRET", "mock-secret"), \
         patch.object(settings, "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback"), \
         patch.object(GoogleOAuthService, "exchange_code_for_tokens", lambda self, code, redirect_uri=None: mock_tokens), \
         patch.object(GoogleOAuthService, "validate_id_token", lambda self, tok, expected_nonce=None: jwt.decode(tok, pub_key, algorithms=["RS256"], audience="mock-google-client-id", issuer=settings.GOOGLE_ISSUERS)):

        # Test POST callback
        res_post = client.post(
            "/api/v1/auth/google/callback",
            json={"code": "valid-auth-code", "state": state_token},
        )
        assert res_post.status_code == 200
        assert "access_token" in res_post.json()

        # Test GET callback
        state_token_2, nonce_2 = generate_oauth_state(purpose="login", return_url="/cases")
        id_token_2 = create_mock_google_id_token(
            priv_key,
            sub="google-callback-sub-2",
            email="callback_user_2@example.com",
            nonce=nonce_2,
            aud="mock-google-client-id",
        )
        mock_tokens_2 = {"id_token": id_token_2}
        with patch.object(GoogleOAuthService, "exchange_code_for_tokens", lambda self, code, redirect_uri=None: mock_tokens_2):
            res_get = client.get(
                f"/api/v1/auth/google/callback?code=valid-code-2&state={state_token_2}"
            )
            assert res_get.status_code == 200
            assert "access_token" in res_get.json()


def test_google_link_and_unlink_flow(
    client: TestClient, db: Session, rsa_key_pair: tuple[Any, Any]
):
    """Verifies explicit linking and unlinking of Google identity by an authenticated user."""
    priv_key, pub_key = rsa_key_pair

    # Register user with password
    email = "link_user@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPassword123!",
            "role": "CLIENT",
            "full_name": "Link User",
        },
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    id_token = create_mock_google_id_token(
        priv_key,
        sub="google-sub-explicit-link",
        email="google_link_alt@example.com",
        aud="mock-google-client-id",
    )

    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-google-client-id"), \
         patch.object(GoogleOAuthService, "validate_id_token", lambda self, tok, expected_nonce=None: jwt.decode(tok, pub_key, algorithms=["RS256"], audience="mock-google-client-id", issuer=settings.GOOGLE_ISSUERS)):

        # Link account
        link_res = client.post(
            "/api/v1/auth/google/link",
            headers=headers,
            json={"id_token": id_token},
        )
        assert link_res.status_code == 200
        data = link_res.json()
        assert data["provider"] == "GOOGLE"
        assert data["email"] == "google_link_alt@example.com"

        # Check identities list
        id_list_res = client.get("/api/v1/auth/identities", headers=headers)
        assert id_list_res.status_code == 200
        assert len(id_list_res.json()) == 1

        # Unlink account
        unlink_res = client.post("/api/v1/auth/google/unlink", headers=headers)
        assert unlink_res.status_code == 200

        # Check identities list is now empty
        id_list_after = client.get("/api/v1/auth/identities", headers=headers)
        assert len(id_list_after.json()) == 0


def test_google_unlink_prevents_account_lockout(
    client: TestClient, db: Session, rsa_key_pair: tuple[Any, Any]
):
    """Verifies that a user created via Google (with no password) cannot unlink their only login method."""
    priv_key, pub_key = rsa_key_pair
    id_token = create_mock_google_id_token(
        priv_key,
        sub="google-only-sub-lockout-test",
        email="google_only_lockout@example.com",
        aud="mock-google-client-id",
    )

    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-google-client-id"), \
         patch.object(GoogleOAuthService, "validate_id_token", lambda self, tok, expected_nonce=None: jwt.decode(tok, pub_key, algorithms=["RS256"], audience="mock-google-client-id", issuer=settings.GOOGLE_ISSUERS)):

        # Login via Google
        res = client.post("/api/v1/auth/google/direct", json={"id_token": id_token})
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Attempt to unlink without setting a password first -> must fail with 409 Conflict
        unlink_res = client.post("/api/v1/auth/google/unlink", headers=headers)
        assert unlink_res.status_code == 409
        assert "password" in unlink_res.json()["error"]["message"].lower()


def test_account_enumeration_defense(client: TestClient):
    """Verifies that wrong password and non-existent email return identical 401 error structure to prevent account enumeration."""
    # 1. Non-existent email
    res1 = client.post(
        "/api/v1/auth/login",
        json={"email": "non_existent_account_12345@example.com", "password": "AnyPassword123!"},
    )
    # 2. Existing email with wrong password
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "existing_enumeration_test@example.com",
            "password": "CorrectPassword123!",
            "role": "CLIENT",
            "full_name": "Enumeration Test User",
        },
    )
    res2 = client.post(
        "/api/v1/auth/login",
        json={"email": "existing_enumeration_test@example.com", "password": "WrongPassword123!"},
    )

    assert res1.status_code == 401
    assert res2.status_code == 401
    assert res1.json()["error"]["code"] == "UNAUTHENTICATED"
    assert res2.json()["error"]["code"] == "UNAUTHENTICATED"
    assert res1.json()["error"]["message"] == res2.json()["error"]["message"]


def test_oauth_privilege_escalation_defense(
    client: TestClient, db: Session, rsa_key_pair: tuple[Any, Any]
):
    """Verifies that an OAuth login or callback NEVER creates an ADMIN or verified LAWYER account."""
    priv_key, pub_key = rsa_key_pair
    id_token = create_mock_google_id_token(
        priv_key,
        sub="google-privilege-test-sub",
        email="privilege_test@example.com",
        aud="mock-google-client-id",
    )

    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-google-client-id"), \
         patch.object(GoogleOAuthService, "validate_id_token", lambda self, tok, expected_nonce=None: jwt.decode(tok, pub_key, algorithms=["RS256"], audience="mock-google-client-id", issuer=settings.GOOGLE_ISSUERS)):

        res = client.post("/api/v1/auth/google/direct", json={"id_token": id_token})
        assert res.status_code == 200

        user = db.query(User).filter(User.email == "privilege_test@example.com").first()
        assert user is not None
        assert user.role == UserRole.CLIENT
        assert user.role != UserRole.ADMIN
        assert user.role != UserRole.LAWYER


def test_concurrent_google_identity_uniqueness(db: Session):
    """Verifies database uniqueness constraint prevents duplicate (provider, provider_subject) entries."""
    user1 = User(
        id=generate_uuid7(),
        email="concurrent_user_1@example.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    user2 = User(
        id=generate_uuid7(),
        email="concurrent_user_2@example.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add_all([user1, user2])
    db.commit()

    id1 = UserExternalIdentity(
        id=generate_uuid7(),
        user_id=user1.id,
        provider="GOOGLE",
        provider_subject="concurrent-sub-12345",
        email="concurrent_user_1@example.com",
        email_verified=True,
    )
    db.add(id1)
    db.commit()

    id2 = UserExternalIdentity(
        id=generate_uuid7(),
        user_id=user2.id,
        provider="GOOGLE",
        provider_subject="concurrent-sub-12345",  # SAME PROVIDER AND SUBJECT
        email="concurrent_user_2@example.com",
        email_verified=True,
    )
    db.add(id2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_auth_service_get_user_identities_isolation_and_layering(client: TestClient, db: Session):
    """
    Verifies that AuthService.get_user_identities correctly encapsulates identity retrieval
    and isolates identities strictly to the authenticated user.
    """
    user_a = User(
        id=generate_uuid7(),
        email="identity_user_a@example.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    user_b = User(
        id=generate_uuid7(),
        email="identity_user_b@example.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add_all([user_a, user_b])
    db.commit()

    id_a = UserExternalIdentity(
        id=generate_uuid7(),
        user_id=user_a.id,
        provider="GOOGLE",
        provider_subject="google-sub-user-a",
        email="identity_user_a@example.com",
        email_verified=True,
    )
    id_b = UserExternalIdentity(
        id=generate_uuid7(),
        user_id=user_b.id,
        provider="GOOGLE",
        provider_subject="google-sub-user-b",
        email="identity_user_b@example.com",
        email_verified=True,
    )
    db.add_all([id_a, id_b])
    db.commit()

    auth_service = AuthService(db)

    # 1. Direct service method isolation
    identities_a = auth_service.get_user_identities(user_a.id)
    identities_b = auth_service.get_user_identities(user_b.id)

    assert len(identities_a) == 1
    assert identities_a[0].provider_subject == "google-sub-user-a"
    assert identities_a[0].user_id == user_a.id

    assert len(identities_b) == 1
    assert identities_b[0].provider_subject == "google-sub-user-b"
    assert identities_b[0].user_id == user_b.id

    # 2. HTTP endpoint invocation for User A
    token_a = create_access_token(str(user_a.id), user_a.role.value)
    res_a = client.get("/api/v1/auth/identities", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200
    items_a = res_a.json()
    assert len(items_a) == 1
    assert items_a[0]["email"] == "identity_user_a@example.com"
    assert items_a[0]["provider"] == "GOOGLE"

    # 3. HTTP endpoint invocation for User B
    token_b = create_access_token(str(user_b.id), user_b.role.value)
    res_b = client.get("/api/v1/auth/identities", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 200
    items_b = res_b.json()
    assert len(items_b) == 1
    assert items_b[0]["email"] == "identity_user_b@example.com"
    assert items_b[0]["provider"] == "GOOGLE"


