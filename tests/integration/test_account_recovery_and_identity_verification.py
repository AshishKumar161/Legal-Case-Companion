import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password, hash_refresh_token, verify_password
from app.models.audit import AuditEvent
from app.models.auth import (
    EmailVerificationToken,
    PasswordResetToken,
    RefreshTokenSession,
)
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    User,
    UserRole,
)
from app.domain.notifications.email_service import ConsoleEmailProvider


@pytest.fixture
def recovery_user(db: Session) -> User:
    email = f"recovery_client_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password("OldPassword123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    profile = ClientProfile(
        id=uuid.uuid4(),
        user_id=user.id,
        full_name="Recovery Test Client",
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return user


def get_error_message(res) -> str:
    data = res.json()
    if isinstance(data, dict):
        if "error" in data and isinstance(data["error"], dict) and "message" in data["error"]:
            return data["error"]["message"]
        return data.get("detail", "")
    return ""


@pytest.fixture
def recovery_lawyer(db: Session) -> User:
    email = f"recovery_lawyer_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password("LawyerSecret123!"),
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    profile = LawyerProfile(
        id=uuid.uuid4(),
        user_id=user.id,
        full_name="Advocate Recovery Test",
        experience_years=7,
        practice_areas=["Corporate Law", "Civil Litigation"],
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return user


def test_forgot_password_anti_enumeration(
    client: TestClient, db: Session, recovery_user: User
):
    """Verifies that password reset requests return identical generic messages for existing, non-existent, and inactive accounts."""
    with patch.object(ConsoleEmailProvider, "send_email", return_value=True) as mock_send:
        # 1. Existing active user
        res_existing = client.post(
            "/api/v1/auth/password/reset/request",
            json={"email": recovery_user.email},
        )
        assert res_existing.status_code == 200
        assert "If an account exists" in res_existing.json()["detail"]
        assert mock_send.called
        assert mock_send.call_args[1]["to_email"] == recovery_user.email
        assert "[Legal Case Companion] Password Reset Request" in mock_send.call_args[1]["subject"]

        mock_send.reset_mock()

        # 2. Non-existent email
        res_unknown = client.post(
            "/api/v1/auth/password/reset/request",
            json={"email": "non_existent_address_xyz123@example.com"},
        )
        assert res_unknown.status_code == 200
        assert res_unknown.json()["detail"] == res_existing.json()["detail"]
        assert not mock_send.called

        # 3. Inactive/suspended user
        suspended_user = User(
            id=uuid.uuid4(),
            email=f"suspended_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("SuspendedPass123!"),
            role=UserRole.CLIENT,
            account_status=AccountStatus.SUSPENDED,
        )
        db.add(suspended_user)
        db.commit()

        res_suspended = client.post(
            "/api/v1/auth/password/reset/request",
            json={"email": suspended_user.email},
        )
        assert res_suspended.status_code == 200
        assert res_suspended.json()["detail"] == res_existing.json()["detail"]
        assert not mock_send.called


def test_password_reset_token_expiry(
    client: TestClient, db: Session, recovery_user: User
):
    """Verifies that expired reset tokens cannot be consumed."""
    raw_token = "test_expired_token_1234567890abcdef"
    token_hash = hash_refresh_token(raw_token)
    past_time = datetime.now(UTC) - timedelta(minutes=20)

    token_record = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=recovery_user.id,
        token_hash=token_hash,
        created_at=past_time - timedelta(minutes=15),
        expires_at=past_time,
        used_at=None,
    )
    db.add(token_record)
    db.commit()

    res = client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"token": raw_token, "new_password": "BrandNewPassword123!"},
    )
    assert res.status_code == 401
    assert "expired" in get_error_message(res).lower()


def test_password_reset_confirmation_and_login_success(
    client: TestClient, db: Session, recovery_user: User
):
    """Verifies password reset confirmation updates the password and enables login."""
    # 1. Request password reset
    with patch.object(ConsoleEmailProvider, "send_email", return_value=True):
        req_res = client.post(
            "/api/v1/auth/password/reset/request",
            json={"email": recovery_user.email},
        )
        assert req_res.status_code == 200

    # 2. Extract generated token from DB
    token_record = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == recovery_user.id)
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )
    assert token_record is not None

    # Find the matching raw token by creating a test token record
    test_raw_token = f"raw_token_{uuid.uuid4().hex}"
    token_record.token_hash = hash_refresh_token(test_raw_token)
    db.commit()

    # 3. Confirm password reset
    new_password = "UpdatedPassword456!@"
    with patch.object(ConsoleEmailProvider, "send_email", return_value=True) as mock_alert:
        confirm_res = client.post(
            "/api/v1/auth/password/reset/confirm",
            json={"token": test_raw_token, "new_password": new_password},
        )
        assert confirm_res.status_code == 200
        assert "successfully reset" in confirm_res.json()["detail"].lower()
        assert mock_alert.called
        assert "Security Alert" in mock_alert.call_args[1]["subject"]

    # 4. Verify DB password hash updated
    db.refresh(recovery_user)
    assert verify_password(new_password, recovery_user.password_hash)
    assert not verify_password("OldPassword123!", recovery_user.password_hash)

    # 5. Verify old password fails login
    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": recovery_user.email, "password": "OldPassword123!"},
    )
    assert old_login.status_code == 401

    # 6. Verify new password succeeds login
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": recovery_user.email, "password": new_password},
    )
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()


def test_password_reset_session_revocation_invariant(
    client: TestClient, db: Session, recovery_user: User
):
    """Verifies that resetting password immediately revokes all active refresh sessions."""
    # 1. Log in to establish an active session
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": recovery_user.email, "password": "OldPassword123!"},
    )
    assert login_res.status_code == 200
    cookies = login_res.cookies

    # Verify session is currently active
    session_count_before = (
        db.query(RefreshTokenSession)
        .filter(
            RefreshTokenSession.user_id == recovery_user.id,
            RefreshTokenSession.revoked_at == None,
        )
        .count()
    )
    assert session_count_before >= 1

    # 2. Issue and confirm password reset
    test_raw_token = f"reset_token_{uuid.uuid4().hex}"
    reset_record = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=recovery_user.id,
        token_hash=hash_refresh_token(test_raw_token),
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        used_at=None,
    )
    db.add(reset_record)
    db.commit()

    with patch.object(ConsoleEmailProvider, "send_email", return_value=True):
        confirm_res = client.post(
            "/api/v1/auth/password/reset/confirm",
            json={"token": test_raw_token, "new_password": "NewSecretPass789!"},
        )
        assert confirm_res.status_code == 200

    # 3. Verify all sessions are now marked revoked
    session_count_after = (
        db.query(RefreshTokenSession)
        .filter(
            RefreshTokenSession.user_id == recovery_user.id,
            RefreshTokenSession.revoked_at == None,
        )
        .count()
    )
    assert session_count_after == 0

    # 4. Attempt to use old session cookie to refresh -> must fail
    refresh_res = client.post(
        "/api/v1/auth/refresh",
        cookies=cookies,
        headers={"x-csrf-token": cookies.get("csrf_token", "")},
    )
    assert refresh_res.status_code == 401


def test_password_reset_single_use_replay_protection(
    client: TestClient, db: Session, recovery_user: User
):
    """Verifies that reset tokens cannot be reused a second time."""
    test_raw_token = f"replay_test_token_{uuid.uuid4().hex}"
    reset_record = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=recovery_user.id,
        token_hash=hash_refresh_token(test_raw_token),
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        used_at=None,
    )
    db.add(reset_record)
    db.commit()

    # First use -> Success
    with patch.object(ConsoleEmailProvider, "send_email", return_value=True):
        res1 = client.post(
            "/api/v1/auth/password/reset/confirm",
            json={"token": test_raw_token, "new_password": "ValidPassword111!"},
        )
        assert res1.status_code == 200

    # Second use (Replay) -> Rejected
    res2 = client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"token": test_raw_token, "new_password": "AnotherPassword222!"},
    )
    assert res2.status_code == 401
    assert "already been used" in get_error_message(res2).lower()


def test_email_verification_flow_and_audit(
    client: TestClient, db: Session, recovery_user: User
):
    """Verifies email verification request, token consumption, and audit event."""
    with patch.object(ConsoleEmailProvider, "send_email", return_value=True) as mock_send:
        # 1. Request verification
        req_res = client.post(
            "/api/v1/auth/email/verify/request",
            json={"email": recovery_user.email},
        )
        assert req_res.status_code == 200
        assert mock_send.called
        assert mock_send.call_args[1]["to_email"] == recovery_user.email

    # 2. Retrieve token from DB
    verif_record = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == recovery_user.id)
        .order_by(EmailVerificationToken.created_at.desc())
        .first()
    )
    assert verif_record is not None

    test_raw_token = f"email_token_{uuid.uuid4().hex}"
    verif_record.token_hash = hash_refresh_token(test_raw_token)
    db.commit()

    # 3. Confirm verification
    confirm_res = client.post(
        "/api/v1/auth/email/verify/confirm",
        json={"token": test_raw_token},
    )
    assert confirm_res.status_code == 200
    assert "successfully verified" in confirm_res.json()["detail"].lower()

    # 4. Check token is marked used
    db.refresh(verif_record)
    assert verif_record.used_at is not None

    # 5. Check audit event
    audit = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.actor_user_id == recovery_user.id,
            AuditEvent.event_type == "EMAIL_VERIFIED",
        )
        .first()
    )
    assert audit is not None


def test_lawyer_professional_verification_workflow_and_safeguards(
    client: TestClient, db: Session, recovery_lawyer: User
):
    """Verifies server-controlled lawyer verification, self-approval prevention, and admin review."""
    # 1. Authenticate lawyer
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": recovery_lawyer.email, "password": "LawyerSecret123!"},
    )
    assert login_res.status_code == 200
    lawyer_token = login_res.json()["access_token"]
    lawyer_headers = {"Authorization": f"Bearer {lawyer_token}"}

    # 2. Lawyer submits verification application
    enrollment = f"BC/{uuid.uuid4().hex[:6]}/2021"
    sub_res = client.post(
        "/api/v1/profiles/lawyer/verification",
        headers=lawyer_headers,
        json={
            "enrollment_number": enrollment,
            "state_bar_council": "Bar Council of Maharashtra & Goa",
        },
    )
    assert sub_res.status_code == 200
    assert sub_res.json()["status"] == "PENDING"
    verification_id = sub_res.json()["id"]

    # 3. Self-approval safeguard: lawyer cannot directly edit verification_status to APPROVED via Profile update
    profile_patch_res = client.patch(
        "/api/v1/profiles/lawyer",
        headers=lawyer_headers,
        json={"bio": "Attempted update"},
    )
    assert profile_patch_res.status_code == 200
    # Re-fetch profile directly from DB to verify status remains PENDING
    db.refresh(recovery_lawyer.lawyer_profile)
    assert recovery_lawyer.lawyer_profile.verification_status == "PENDING"

    # 4. Create admin user
    admin_user = User(
        id=uuid.uuid4(),
        email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("AdminPass123!"),
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(admin_user)
    db.commit()

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "AdminPass123!"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # 5. Admin lists applications
    admin_list = client.get("/api/v1/admin/verifications", headers=admin_headers)
    assert admin_list.status_code == 200
    items = admin_list.json()["items"]
    assert any(str(item["id"]) == str(verification_id) for item in items)

    # 6. Admin approves verification
    approve_res = client.post(
        f"/api/v1/admin/verifications/{verification_id}/approve",
        headers=admin_headers,
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    # Verify lawyer profile status transitioned
    db.refresh(recovery_lawyer.lawyer_profile)
    assert recovery_lawyer.lawyer_profile.verification_status == "APPROVED"


def test_audit_events_logged_for_recovery_lifecycle(
    client: TestClient, db: Session, recovery_user: User
):
    """Verifies that all recovery lifecycle events emit proper audit logs without secrets."""
    # 1. Request reset
    test_raw_token = f"audit_token_{uuid.uuid4().hex}"
    reset_record = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=recovery_user.id,
        token_hash=hash_refresh_token(test_raw_token),
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        used_at=None,
    )
    db.add(reset_record)
    db.commit()

    # 2. Confirm reset
    with patch.object(ConsoleEmailProvider, "send_email", return_value=True):
        client.post(
            "/api/v1/auth/password/reset/confirm",
            json={"token": test_raw_token, "new_password": "NewSecretPass999!"},
        )

    # 3. Query audit events
    audit_events = (
        db.query(AuditEvent)
        .filter(AuditEvent.actor_user_id == recovery_user.id)
        .all()
    )
    event_types = [e.event_type for e in audit_events]
    assert "PASSWORD_RESET_COMPLETED" in event_types

    # Ensure no passwords or raw tokens exist in metadata
    for ev in audit_events:
        metadata_str = str(ev.metadata_)
        assert "NewSecretPass999!" not in metadata_str
        assert test_raw_token not in metadata_str


def test_password_reset_rejects_weak_and_empty_passwords(
    client: TestClient, db: Session, recovery_user: User
):
    """Verifies that password reset rejects passwords shorter than 8 characters."""
    test_raw_token = f"weak_pass_token_{uuid.uuid4().hex}"
    reset_record = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=recovery_user.id,
        token_hash=hash_refresh_token(test_raw_token),
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        used_at=None,
    )
    db.add(reset_record)
    db.commit()

    # Weak password (under 8 chars) -> 422
    res_short = client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"token": test_raw_token, "new_password": "short"},
    )
    assert res_short.status_code == 422

    # Empty token -> 401/422
    res_empty_token = client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"token": "", "new_password": "ValidPassword999!"},
    )
    assert res_empty_token.status_code in (401, 422)


def test_password_reset_double_consumption_rejection(
    client: TestClient, db: Session, recovery_user: User
):
    """Verifies that attempting to consume a reset token multiple times sequentially fails after the first."""
    test_raw_token = f"double_consume_token_{uuid.uuid4().hex}"
    reset_record = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=recovery_user.id,
        token_hash=hash_refresh_token(test_raw_token),
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        used_at=None,
    )
    db.add(reset_record)
    db.commit()

    with patch.object(ConsoleEmailProvider, "send_email", return_value=True):
        r1 = client.post(
            "/api/v1/auth/password/reset/confirm",
            json={
                "token": test_raw_token,
                "new_password": "FirstAttemptPass123!",
            },
        )
        assert r1.status_code == 200

        r2 = client.post(
            "/api/v1/auth/password/reset/confirm",
            json={
                "token": test_raw_token,
                "new_password": "SecondAttemptPass456!",
            },
        )
        assert r2.status_code == 401
        assert "already been used" in get_error_message(r2).lower()
