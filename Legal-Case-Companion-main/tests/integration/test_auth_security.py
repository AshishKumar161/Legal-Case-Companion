from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.user import AccountStatus, User, UserRole


def _register_and_login(client: TestClient, email: str, password: str = "SecurePass123!", role: str = "CLIENT"):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "role": role, "full_name": "Auth Test User"},
    )
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return res


def test_jwt_validation_matrix_and_algorithm_confusion(client: TestClient, db: Session):
    # 1. Setup user
    user = User(
        email="jwt_matrix@test.com",
        password_hash=hash_password("SecurePass123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 2. Valid token succeeds
    valid_token = create_access_token(str(user.id), user.role.value)
    res_valid = client.get("/api/v1/cases", headers={"Authorization": f"Bearer {valid_token}"})
    assert res_valid.status_code == 200

    # 3. Expired token is rejected (401)
    private_key = serialization.load_pem_private_key(settings.JWT_PRIVATE_KEY.encode(), password=None)
    expired_payload = {
        "sub": str(user.id),
        "iss": "legal-case-companion",
        "aud": "legal-case-companion",
        "exp": datetime.now(UTC) - timedelta(minutes=10),
        "iat": datetime.now(UTC) - timedelta(minutes=20),
        "role": user.role.value,
        "type": "access",
    }
    expired_token = jwt.encode(expired_payload, private_key, algorithm=settings.ALGORITHM)
    res_exp = client.get("/api/v1/cases", headers={"Authorization": f"Bearer {expired_token}"})
    assert res_exp.status_code == 401
    assert "expired" in res_exp.json()["error"]["message"].lower()

    # 4. Token with wrong token type (e.g. 'refresh') is rejected (401)
    wrong_type_payload = {
        "sub": str(user.id),
        "iss": "legal-case-companion",
        "aud": "legal-case-companion",
        "exp": datetime.now(UTC) + timedelta(minutes=10),
        "iat": datetime.now(UTC),
        "role": user.role.value,
        "type": "refresh",
    }
    wrong_type_token = jwt.encode(wrong_type_payload, private_key, algorithm=settings.ALGORITHM)
    res_wrong_type = client.get("/api/v1/cases", headers={"Authorization": f"Bearer {wrong_type_token}"})
    assert res_wrong_type.status_code == 401

    # 5. Algorithm confusion attack: Token signed with HS256 using public key as secret is rejected (401)
    hs256_payload = {
        "sub": str(user.id),
        "iss": "legal-case-companion",
        "aud": "legal-case-companion",
        "exp": datetime.now(UTC) + timedelta(minutes=10),
        "iat": datetime.now(UTC),
        "role": user.role.value,
        "type": "access",
    }
    hs256_token = jwt.encode(hs256_payload, "symmetric_secret_key_1234567890_32bytes", algorithm="HS256")
    res_hs256 = client.get("/api/v1/cases", headers={"Authorization": f"Bearer {hs256_token}"})
    assert res_hs256.status_code == 401

    # 6. Untrusted Ed25519 key signature is rejected (401)
    other_key = Ed25519PrivateKey.generate()
    other_token = jwt.encode(hs256_payload, other_key, algorithm=settings.ALGORITHM)
    res_untrusted = client.get("/api/v1/cases", headers={"Authorization": f"Bearer {other_token}"})
    assert res_untrusted.status_code == 401

    # 7. Token missing subject claim is rejected (401)
    no_sub_payload = {
        "iss": "legal-case-companion",
        "aud": "legal-case-companion",
        "exp": datetime.now(UTC) + timedelta(minutes=10),
        "iat": datetime.now(UTC),
        "role": user.role.value,
        "type": "access",
    }
    no_sub_token = jwt.encode(no_sub_payload, private_key, algorithm=settings.ALGORITHM)
    res_no_sub = client.get("/api/v1/cases", headers={"Authorization": f"Bearer {no_sub_token}"})
    assert res_no_sub.status_code == 401


def test_refresh_token_rotation_and_family_revocation(client: TestClient):
    login_res = _register_and_login(client, "family_test@test.com", "SecurePass123!")
    refresh_token_a = login_res.cookies.get("refresh_token")
    csrf_token_1 = login_res.cookies.get("csrf_token")

    # 1. First rotation (Token A -> Token B)
    res_rot1 = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token_a, "csrf_token": csrf_token_1},
        headers={"X-CSRF-Token": csrf_token_1},
    )
    assert res_rot1.status_code == 200
    refresh_token_b = res_rot1.cookies.get("refresh_token")
    csrf_token_2 = res_rot1.cookies.get("csrf_token")
    assert refresh_token_b != refresh_token_a

    # 2. Token Reuse Attack: Attempt to use Token A again
    res_reuse = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token_a, "csrf_token": csrf_token_2},
        headers={"X-CSRF-Token": csrf_token_2},
    )
    assert res_reuse.status_code == 401

    # 3. Family Revocation: Token B must ALSO be revoked now because Token A reuse compromised the family
    res_rot2 = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token_b, "csrf_token": csrf_token_2},
        headers={"X-CSRF-Token": csrf_token_2},
    )
    assert res_rot2.status_code == 401


def test_logout_and_session_revocation(client: TestClient):
    login_res = _register_and_login(client, "logout_test@test.com", "SecurePass123!")
    access_token = login_res.json()["access_token"]
    refresh_token = login_res.cookies.get("refresh_token")
    csrf_token = login_res.cookies.get("csrf_token")

    # 1. Logout
    res_logout = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
    )
    assert res_logout.status_code == 200

    # 2. Refresh after logout is rejected (401)
    res_refresh = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_refresh.status_code == 401


def test_account_suspension_immediate_access_and_refresh_denial(client: TestClient, db: Session):
    login_res = _register_and_login(client, "suspended_auth@test.com", "SecurePass123!")
    access_token = login_res.json()["access_token"]
    refresh_token = login_res.cookies.get("refresh_token")
    csrf_token = login_res.cookies.get("csrf_token")

    # Access token works initially
    assert client.get("/api/v1/cases", headers={"Authorization": f"Bearer {access_token}"}).status_code == 200

    # Admin suspends user directly in DB
    user = db.query(User).filter(User.email == "suspended_auth@test.com").first()
    assert user is not None
    user.account_status = AccountStatus.SUSPENDED
    db.commit()

    # 1. Existing access token immediately rejected on protected routes (401)
    res_protected = client.get("/api/v1/cases", headers={"Authorization": f"Bearer {access_token}"})
    assert res_protected.status_code == 401
    assert "inactive" in res_protected.json()["error"]["message"].lower()

    # 2. Refresh token immediately rejected (401)
    res_refresh = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_refresh.status_code == 401
    assert "inactive" in res_refresh.json()["error"]["message"].lower()


def test_password_change_invalidates_all_active_refresh_sessions(client: TestClient):
    login_res = _register_and_login(client, "pwd_session_inv@test.com", "OldPassword123!")
    access_token = login_res.json()["access_token"]
    refresh_token = login_res.cookies.get("refresh_token")
    csrf_token = login_res.cookies.get("csrf_token")

    # 1. Change password
    res_change = client.post(
        "/api/v1/auth/password/change",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"current_password": "OldPassword123!", "new_password": "NewPassword123!"},
    )
    assert res_change.status_code == 200

    # 2. Previous refresh token is now revoked (session invalidated)
    res_refresh = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_refresh.status_code == 401

    # 3. Old password fails login
    assert client.post("/api/v1/auth/login", json={"email": "pwd_session_inv@test.com", "password": "OldPassword123!"}).status_code == 401

    # 4. New password succeeds login
    res_new_login = client.post("/api/v1/auth/login", json={"email": "pwd_session_inv@test.com", "password": "NewPassword123!"})
    assert res_new_login.status_code == 200


def test_registration_integrity_and_email_normalization(client: TestClient):
    # 1. Normal registration with mixed-case email
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "CaseNorm@Test.com",
            "password": "SecurePassword123!",
            "role": "CLIENT",
            "full_name": "Case User",
        },
    )
    assert res_reg.status_code == 201
    assert res_reg.json()["email"] == "casenorm@test.com"

    # 2. Duplicate registration with different case fails (400)
    res_dup = client.post(
        "/api/v1/auth/register",
        json={
            "email": "casenorm@test.com",
            "password": "SecurePassword123!",
            "role": "CLIENT",
            "full_name": "Case User Duplicate",
        },
    )
    assert res_dup.status_code == 400

    # 3. Login with mixed-case email succeeds
    res_login = client.post(
        "/api/v1/auth/login",
        json={"email": "CASENORM@TEST.COM", "password": "SecurePassword123!"},
    )
    assert res_login.status_code == 200
