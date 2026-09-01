import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, hash_refresh_token
from app.models.auth import PasswordResetToken, RefreshTokenSession
from app.models.user import AccountStatus, ClientProfile, User, UserRole
from app.services.email_service import (
    ConsoleEmailProvider,
    SMTPEmailProvider,
    get_email_provider,
)
from app.services.user_service import UserService


def test_google_oauth_missing_configuration_error(client: TestClient):
    """Verifies that initiating Google OAuth without configured keys returns standard 401."""
    orig_client_id = settings.GOOGLE_CLIENT_ID
    settings.GOOGLE_CLIENT_ID = None
    try:
        res = client.get("/api/v1/auth/google/login")
        assert res.status_code == 401
        assert "Google OAuth is not configured" in res.json()["error"]["message"]
    finally:
        settings.GOOGLE_CLIENT_ID = orig_client_id


def test_google_oauth_configured_authorization_url(client: TestClient):
    """Verifies that Google OAuth with configured keys builds valid authorization URL with state and nonce."""
    orig_client_id = settings.GOOGLE_CLIENT_ID
    orig_redirect = settings.GOOGLE_REDIRECT_URI
    settings.GOOGLE_CLIENT_ID = "test-client-id.apps.googleusercontent.com"
    settings.GOOGLE_REDIRECT_URI = "http://localhost:3000/auth/callback"
    try:
        res = client.get("/api/v1/auth/google/login?redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fauth%2Fcallback")
        assert res.status_code == 200
        data = res.json()
        assert "authorization_url" in data
        assert "accounts.google.com" in data["authorization_url"]
        assert "test-client-id.apps.googleusercontent.com" in data["authorization_url"]
        assert "state" in data
    finally:
        settings.GOOGLE_CLIENT_ID = orig_client_id
        settings.GOOGLE_REDIRECT_URI = orig_redirect


def test_console_email_provider_extracts_links(caplog: pytest.LogCaptureFixture):
    """Verifies that ConsoleEmailProvider formats output and extracts action links in development."""
    provider = ConsoleEmailProvider()
    with caplog.at_level("INFO"):
        success = provider.send_email(
            to_email="dev_user@example.com",
            subject="Reset Your Password",
            html_body='<p>Click <a href="http://localhost:3000/reset-password?token=secret123">here</a> to reset.</p>',
        )
    assert success is True
    assert "http://localhost:3000/reset-password?token=secret123" in caplog.text
    assert "dev_user@example.com" in caplog.text


def test_smtp_email_provider_initialization_and_mock_dispatch():
    """Verifies that SMTPEmailProvider initializes with SMTP settings and dispatches via smtplib."""
    orig_host = settings.SMTP_HOST
    settings.SMTP_HOST = "smtp.example.com"
    settings.SMTP_PORT = 587
    settings.SMTP_USERNAME = "user"
    settings.SMTP_PASSWORD = "pass"
    settings.SMTP_TLS = True

    try:
        provider = SMTPEmailProvider()
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = mock_smtp_cls.return_value

            sent = provider.send_email(
                to_email="recipient@example.com",
                subject="Test Subject",
                html_body="<p>Test Body</p>",
            )
            assert sent is True
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user", "pass")
            mock_server.sendmail.assert_called_once()
    finally:
        settings.SMTP_HOST = orig_host


def test_get_email_provider_selection():
    """Verifies provider factory selects configured email backend."""
    orig = settings.EMAIL_PROVIDER
    try:
        settings.EMAIL_PROVIDER = "console"
        assert isinstance(get_email_provider(), ConsoleEmailProvider)

        settings.EMAIL_PROVIDER = "smtp"
        orig_host = settings.SMTP_HOST
        settings.SMTP_HOST = "smtp.test.com"
        assert isinstance(get_email_provider(), SMTPEmailProvider)
        settings.SMTP_HOST = orig_host
    finally:
        settings.EMAIL_PROVIDER = orig


def test_password_reset_end_to_end_and_session_invalidation(
    client: TestClient, db: Session
):
    """Verifies complete runtime password reset flow with token consumption and global session revocation."""
    email = f"reset_runtime_{uuid.uuid4().hex[:8]}@example.com"
    initial_pass = "InitialPass123!"
    new_pass = "UpdatedSecurePass456!"

    # 1. Create active test user
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(initial_pass),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    profile = ClientProfile(user_id=user.id, full_name="Reset User")
    db.add_all([user, profile])
    db.commit()

    # 2. Login to create active session
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": initial_pass})
    assert login_res.status_code == 200

    # Verify active refresh session exists
    sessions = db.query(RefreshTokenSession).filter(RefreshTokenSession.user_id == user.id, RefreshTokenSession.revoked_at.is_(None)).all()
    assert len(sessions) == 1

    # 3. Request password reset
    raw_token = f"runtime_token_{uuid.uuid4().hex}"
    reset_record = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=hash_refresh_token(raw_token),
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        used_at=None,
    )
    db.add(reset_record)
    db.commit()

    # 4. Confirm password reset
    with patch.object(ConsoleEmailProvider, "send_email", return_value=True):
        confirm_res = client.post(
            "/api/v1/auth/password/reset/confirm",
            json={"token": raw_token, "new_password": new_pass},
        )
        assert confirm_res.status_code == 200

    # 5. Verify all previous refresh sessions are revoked
    active_sessions = db.query(RefreshTokenSession).filter(RefreshTokenSession.user_id == user.id, RefreshTokenSession.revoked_at.is_(None)).all()
    assert len(active_sessions) == 0

    # 6. Verify old password is now rejected
    old_login = client.post("/api/v1/auth/login", json={"email": email, "password": initial_pass})
    assert old_login.status_code == 401

    # 7. Verify new password is accepted
    new_login = client.post("/api/v1/auth/login", json={"email": email, "password": new_pass})
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()


def test_user_service_get_user_by_email_case_and_whitespace_insensitivity(
    db: Session
):
    """Verifies that get_user_by_email normalizes emails with leading/trailing spaces and uppercase characters."""
    user = User(
        id=uuid.uuid4(),
        email="mixed.case.user@example.com",
        password_hash=hash_password("Pass123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()

    user_service = UserService(db)
    found_1 = user_service.get_user_by_email("   mixed.CASE.User@example.com   ")
    assert found_1 is not None
    assert found_1.id == user.id

    found_2 = user_service.get_user_by_email("MIXED.case.user@EXAMPLE.COM")
    assert found_2 is not None
    assert found_2.id == user.id


def test_user_registration_and_immediate_login_flow(client: TestClient):
    """Verifies that fresh registration immediately permits successful login with identical credentials."""
    email = f"fresh_reg_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"

    # 1. Register
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Fresh User",
            "role": "CLIENT",
        },
    )
    assert reg_res.status_code == 201

    # 2. Login immediately
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()
