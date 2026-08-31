import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


def _register_and_login(
    client: TestClient,
    email: str,
    password: str,
    role: str = "CLIENT",
    full_name: str = "Test User",
):
    """Helper to register and login a user, returning (access_token, refresh_token_cookie)."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "role": role,
        },
    )
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return res


def test_register_success(client: TestClient):
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "SecurePassword123!",
            "full_name": "Test User",
            "role": "CLIENT",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "CLIENT"
    assert "id" in data


def test_duplicate_registration_fails(client: TestClient):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "dup@example.com",
            "password": "SecurePassword123!",
            "full_name": "Test User",
            "role": "CLIENT",
        },
    )
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "dup@example.com",
            "password": "SecurePassword123!",
            "full_name": "Test User 2",
            "role": "CLIENT",
        },
    )
    assert res.status_code == 400
    assert "already exists" in res.json()["error"]["message"]


def test_login_success_and_logout(client: TestClient):
    login_res = _register_and_login(client, "login@example.com", "SecurePassword123!")
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()
    assert "refresh_token" in login_res.cookies
    # CSRF cookie should be set on login (Phase 6)
    assert "csrf_token" in login_res.cookies

    # Test refresh — requires CSRF token
    csrf_token = login_res.cookies.get("csrf_token")
    res_refresh = client.post(
        "/api/v1/auth/refresh",
        cookies={
            "refresh_token": login_res.cookies.get("refresh_token"),
            "csrf_token": csrf_token,
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_refresh.status_code == 200
    assert "access_token" in res_refresh.json()

    # Test logout
    token = login_res.json()["access_token"]
    res_logout = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
        cookies={"refresh_token": res_refresh.cookies.get("refresh_token")},
    )
    assert res_logout.status_code == 200

    # Test refresh after logout (revoked)
    new_csrf = res_refresh.cookies.get("csrf_token", csrf_token)
    res_refresh_failed = client.post(
        "/api/v1/auth/refresh",
        cookies={
            "refresh_token": res_refresh.cookies.get("refresh_token"),
            "csrf_token": new_csrf,
        },
        headers={"X-CSRF-Token": new_csrf},
    )
    assert res_refresh_failed.status_code == 401


def test_invalid_credentials(client: TestClient):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "wrong"},
    )
    assert res.status_code == 401
    assert "Invalid authentication credentials" in res.json()["error"]["message"]


def test_password_change(client: TestClient):
    login_res = _register_and_login(client, "passchange@example.com", "OldPassword123!")
    token = login_res.json()["access_token"]

    change_res = client.post(
        "/api/v1/auth/password/change",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "OldPassword123!", "new_password": "NewPassword123!"},
    )
    assert change_res.status_code == 200

    # Verify old password fails
    login_fail = client.post(
        "/api/v1/auth/login",
        json={"email": "passchange@example.com", "password": "OldPassword123!"},
    )
    assert login_fail.status_code == 401

    # Verify new password works
    login_success = client.post(
        "/api/v1/auth/login",
        json={"email": "passchange@example.com", "password": "NewPassword123!"},
    )
    assert login_success.status_code == 200


def test_refresh_token_reuse_detection(client: TestClient):
    login_res = _register_and_login(client, "reuse@example.com", "SecurePassword123!")
    refresh_token = login_res.cookies.get("refresh_token")
    csrf_token = login_res.cookies.get("csrf_token")

    # First refresh succeeds
    refresh_1 = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert refresh_1.status_code == 200

    # Reusing the old token should trigger reuse detection
    new_csrf = refresh_1.cookies.get("csrf_token", csrf_token)
    refresh_2 = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token, "csrf_token": new_csrf},
        headers={"X-CSRF-Token": new_csrf},
    )
    assert refresh_2.status_code == 401

    # The new token should ALSO be revoked now because of reuse
    new_refresh = refresh_1.cookies.get("refresh_token")
    refresh_3 = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": new_refresh, "csrf_token": new_csrf},
        headers={"X-CSRF-Token": new_csrf},
    )
    assert refresh_3.status_code == 401


def test_csrf_validation_failure_modes(client: TestClient):
    """Phase 2: Verify that /refresh rejects requests with missing or invalid CSRF or Origin."""
    login_res = _register_and_login(
        client, "csrf_fail@example.com", "SecurePassword123!"
    )
    refresh_token = login_res.cookies.get("refresh_token")
    csrf_token = login_res.cookies.get("csrf_token")

    # 1. Missing CSRF header
    res1 = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
    )
    assert res1.status_code == 401

    # 2. Mismatched CSRF token
    res2 = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
        headers={"X-CSRF-Token": "invalid-token"},
    )
    assert res2.status_code == 401

    # 3. Missing/Invalid Origin (when in production mode)
    from app.core.config import settings

    # Override environment to trigger origin check
    original_env = settings.ENVIRONMENT
    settings.ENVIRONMENT = "production"
    settings.BACKEND_CORS_ORIGINS = ["http://localhost:3000"]
    try:
        # Malicious Origin
        res3 = client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
            headers={"X-CSRF-Token": csrf_token, "Origin": "http://evil.com"},
        )
        assert res3.status_code == 401

        # Missing Origin/Referer
        res4 = client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert res4.status_code == 401

        # Valid Origin
        res5 = client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
            headers={"X-CSRF-Token": csrf_token, "Origin": "http://localhost:3000"},
        )
        assert res5.status_code == 200
    finally:
        settings.ENVIRONMENT = original_env


@pytest.mark.skipif(
    settings.DATABASE_URL.startswith("sqlite"),
    reason="SQLite does not support FOR UPDATE locks correctly",
)
def test_concurrent_refresh_rotation(client: TestClient):
    """Phase 2: Verify that concurrent refresh requests do not allow multiple valid rotations."""
    import threading

    login_res = _register_and_login(
        client, "concurrent@example.com", "SecurePassword123!"
    )
    refresh_token = login_res.cookies.get("refresh_token")
    csrf_token = login_res.cookies.get("csrf_token")

    results = []

    from app.db.database import get_db
    from tests.conftest import TestingSessionLocal

    def thread_safe_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    client.app.dependency_overrides[get_db] = thread_safe_get_db

    def attempt_refresh():
        try:
            res = client.post(
                "/api/v1/auth/refresh",
                cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
                headers={"X-CSRF-Token": csrf_token},
            )
            results.append(res.status_code)
        except Exception:  # noqa: BLE001
            # SQLite thread-sharing session errors or locking are expected here
            results.append(500)

    threads = [threading.Thread(target=attempt_refresh) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Only ONE request should succeed (200), the others should fail (401 or 500 db lock)
    successes = [code for code in results if code == 200]
    _failures = [code for code in results if code in (401, 500)]

    # Under PostgreSQL, we must have exactly 1 success and 4 failures.
    if settings.DATABASE_URL.startswith("postgresql"):
        assert (
            len(successes) == 1
        ), f"Expected exactly 1 success under PostgreSQL concurrency, got {len(successes)} (results: {results})"
    else:
        assert (
            len(successes) <= 1
        ), f"Expected at most 1 success under SQLite concurrency, got {len(successes)} (results: {results})"
