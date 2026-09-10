from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.oauth_security import (
    generate_oauth_state,
    validate_return_url,
)


def test_jwt_forgery_and_algorithm_confusion(client: TestClient):
    """Red Team: Validates that forged JWTs, algorithm confusion (HS256/none), and invalid keys are strictly rejected."""
    # 1. Algorithm 'none' attack
    forged_none_token = jwt.encode(
        {"sub": "attacker-user-id", "role": "ADMIN", "type": "access"},
        key="",
        algorithm="none",
    )
    res = client.get(
        "/api/v1/profiles/me",
        headers={"Authorization": f"Bearer {forged_none_token}"},
    )
    assert res.status_code == 401

    # 2. HS256 symmetric secret token attack (signed with random HMAC secret)
    fake_hs256_token = jwt.encode(
        {
            "sub": "attacker-user-id",
            "iss": "legal-case-companion",
            "aud": "legal-case-companion",
            "role": "ADMIN",
            "type": "access",
            "exp": datetime.now(UTC) + timedelta(minutes=15),
        },
        key="random-secret-key-that-is-not-ed25519",
        algorithm="HS256",
    )
    res_hs256 = client.get(
        "/api/v1/profiles/me",
        headers={"Authorization": f"Bearer {fake_hs256_token}"},
    )
    assert res_hs256.status_code == 401

    # 3. Token type confusion: token with type="refresh" passed as access token
    now = datetime.now(UTC)
    type_confused_token = jwt.encode(
        {
            "sub": "some-user-id",
            "iss": "legal-case-companion",
            "aud": "legal-case-companion",
            "role": "CLIENT",
            "type": "refresh",
            "exp": now + timedelta(minutes=15),
        },
        key=settings.JWT_PRIVATE_KEY,
        algorithm=settings.ALGORITHM,
    )
    res_confused = client.get(
        "/api/v1/profiles/me",
        headers={"Authorization": f"Bearer {type_confused_token}"},
    )
    assert res_confused.status_code == 401


def test_refresh_token_replay_and_family_invalidation(client: TestClient, db: Session):
    """Red Team: Validates that replaying an old refresh token immediately invalidates the entire token family."""
    # 1. Register & Login User
    email = "redteam_auth_replay@example.com"
    pwd = "RedTeamPass123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pwd, "role": "CLIENT", "full_name": "RedTeam User"},
    )
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert login_res.status_code == 200
    csrf_token1 = login_res.cookies.get("csrf_token")
    refresh_token1 = login_res.cookies.get("refresh_token")

    # 2. Legitimate Token Rotation (Refresh 1 -> Refresh 2)
    ref1_res = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token1},
        cookies={"refresh_token": refresh_token1, "csrf_token": csrf_token1},
    )
    assert ref1_res.status_code == 200
    csrf_token2 = ref1_res.cookies.get("csrf_token")
    refresh_token2 = ref1_res.cookies.get("refresh_token")

    # 3. Attacker replays compromised refresh_token1
    replay_res = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token1},
        cookies={"refresh_token": refresh_token1, "csrf_token": csrf_token1},
    )
    assert replay_res.status_code == 401

    # 4. Legitimate user tries to use active refresh_token2 -> MUST FAIL due to family revocation
    victim_refresh = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token2},
        cookies={"refresh_token": refresh_token2, "csrf_token": csrf_token2},
    )
    assert victim_refresh.status_code == 401


def test_password_change_global_session_revocation(client: TestClient, db: Session):
    """Red Team: Validates that changing a password invalidates all active refresh sessions."""
    email = "redteam_pw_change@example.com"
    pwd = "OldPassword123!"
    new_pwd = "NewPassword456!"

    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pwd, "role": "CLIENT", "full_name": "PW User"},
    )
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    token = login_res.json()["access_token"]
    csrf_token = login_res.cookies.get("csrf_token")
    refresh_token = login_res.cookies.get("refresh_token")

    # Change password
    change_res = client.post(
        "/api/v1/auth/password/change",
        headers={"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf_token},
        cookies={"csrf_token": csrf_token},
        json={"current_password": pwd, "new_password": new_pwd},
    )
    assert change_res.status_code == 200

    # Old refresh token is revoked
    old_ref = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token},
        cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
    )
    assert old_ref.status_code == 401


def test_oauth_open_redirect_and_state_tampering(client: TestClient):
    """Red Team: Validates open-redirect neutralization and cryptographic state tampering rejection."""
    # 1. Open redirect attacks neutralized
    malicious_urls = [
        "https://evil.com/phishing",
        "http://attacker.com",
        "//attacker.com/bypass",
        "\\\\evil.corp",
        "javascript:alert(document.cookie)",
        "data:text/html,<script>alert(1)</script>",
    ]
    for url in malicious_urls:
        assert validate_return_url(url) == "/dashboard"

    # Valid relative URLs allowed
    assert validate_return_url("/cases/01a0-1234") == "/cases/01a0-1234"
    assert validate_return_url("/lawyers") == "/lawyers"

    # 2. Tampered OAuth state token rejection
    state_token, _nonce = generate_oauth_state(purpose="login", return_url="/dashboard")
    tampered_state = state_token[:-5] + "XXXXX"
    res_callback = client.post(
        "/api/v1/auth/google/callback",
        json={"code": "valid_code_sample", "state": tampered_state, "redirect_uri": "http://localhost:3000/auth/callback"},
    )
    assert res_callback.status_code == 401
