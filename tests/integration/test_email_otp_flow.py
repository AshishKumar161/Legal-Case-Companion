import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_refresh_token
from app.models.auth import EmailVerificationToken
from app.models.user import User
from app.domain.notifications.email_service import ConsoleEmailProvider


def get_error_message(res) -> str:
    data = res.json()
    if isinstance(data, dict):
        if "error" in data and isinstance(data["error"], dict) and "message" in data["error"]:
            return data["error"]["message"]
        return data.get("detail", "")
    return ""


def test_registration_and_email_otp_verification_flow(client: TestClient, db: Session):
    """Verifies that registration dispatches an email OTP, and /api/v1/auth/email/verify/otp
    validates the code, sets authentication cookies, and returns an access token.
    """
    unique_id = uuid.uuid4().hex[:8]
    test_email = f"otp_user_{unique_id}@example.com"
    test_password = "SecurePassword123!@"
    test_name = "OTP Test User"

    # 1. Register new user
    with patch.object(ConsoleEmailProvider, "send_email", return_value=True) as mock_email:
        reg_res = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": test_name,
                "email": test_email,
                "password": test_password,
                "role": "CLIENT",
            },
        )
        assert reg_res.status_code == 201
        assert reg_res.json()["email"] == test_email
        assert mock_email.called
        assert test_email in mock_email.call_args[1]["to_email"]

    # 2. Extract generated OTP record from database
    user = db.query(User).filter(User.email == test_email).first()
    assert user is not None

    otp_record = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == user.id)
        .order_by(EmailVerificationToken.created_at.desc())
        .first()
    )
    assert otp_record is not None
    assert otp_record.used_at is None

    # Set a known test OTP code
    known_otp = "739201"
    otp_record.token_hash = hash_refresh_token(known_otp)
    db.commit()

    # 3. Test Invalid OTP rejection (returns 401)
    bad_res = client.post(
        "/api/v1/auth/email/verify/otp",
        json={"email": test_email, "otp": "000000"},
    )
    assert bad_res.status_code == 401
    assert "invalid" in get_error_message(bad_res).lower()

    # 4. Test Successful OTP verification & auto-login
    success_res = client.post(
        "/api/v1/auth/email/verify/otp",
        json={"email": test_email, "otp": known_otp},
    )
    assert success_res.status_code == 200
    data = success_res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert success_res.cookies.get("refresh_token") is not None
    assert success_res.cookies.get("csrf_token") is not None

    # 5. Verify database record marked used
    db.refresh(otp_record)
    assert otp_record.used_at is not None

    # 6. Verify access token works to query profile
    profile_res = client.get(
        "/api/v1/profiles/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert profile_res.status_code == 200
    assert profile_res.json()["full_name"] == test_name

    # 7. Test Replay attack (consumed OTP cannot be reused)
    replay_res = client.post(
        "/api/v1/auth/email/verify/otp",
        json={"email": test_email, "otp": known_otp},
    )
    assert replay_res.status_code == 401
    assert "already been used" in get_error_message(replay_res).lower()


def test_expired_email_otp_rejection(client: TestClient, db: Session):
    """Verifies that expired OTP codes are rejected with 401."""
    unique_id = uuid.uuid4().hex[:8]
    test_email = f"expired_otp_{unique_id}@example.com"
    test_password = "SecurePassword123!@"

    # Register user
    with patch.object(ConsoleEmailProvider, "send_email", return_value=True):
        client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Expired User",
                "email": test_email,
                "password": test_password,
                "role": "CLIENT",
            },
        )

    user = db.query(User).filter(User.email == test_email).first()
    assert user is not None

    # Create expired OTP
    expired_otp = "445566"
    now = datetime.now(UTC)
    expired_record = EmailVerificationToken(
        id=uuid.uuid4(),
        user_id=user.id,
        email=test_email,
        token_hash=hash_refresh_token(expired_otp),
        created_at=now - timedelta(minutes=30),
        expires_at=now - timedelta(minutes=15),
        used_at=None,
    )
    db.add(expired_record)
    db.commit()

    res = client.post(
        "/api/v1/auth/email/verify/otp",
        json={"email": test_email, "otp": expired_otp},
    )
    assert res.status_code == 401
    assert "expired" in get_error_message(res).lower()
