from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_session_refresh_and_family_revocation_e2e(client: TestClient, db: Session):
    """E2E Test: Validates session rotation, double-submit CSRF, and token family revocation upon replay."""
    # 1. Register & Login User
    email = "session_concurrency_e2e@example.com"
    pwd = "SessionPass123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pwd, "role": "CLIENT", "full_name": "Session User"},
    )
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert login_res.status_code == 200
    _token1 = login_res.json()["access_token"]
    csrf_token1 = login_res.cookies.get("csrf_token")
    refresh_token1 = login_res.cookies.get("refresh_token")

    # 2. First Refresh (Success)
    ref1_res = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token1},
        cookies={"refresh_token": refresh_token1, "csrf_token": csrf_token1},
    )
    assert ref1_res.status_code == 200
    _token2 = ref1_res.json()["access_token"]
    csrf_token2 = ref1_res.cookies.get("csrf_token")
    refresh_token2 = ref1_res.cookies.get("refresh_token")

    # 3. Second Refresh using new token (Success)
    ref2_res = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token2},
        cookies={"refresh_token": refresh_token2, "csrf_token": csrf_token2},
    )
    assert ref2_res.status_code == 200

    # 4. Replay of Stale refresh_token1 -> FAMILY REVOCATION
    replay_res = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token1},
        cookies={"refresh_token": refresh_token1, "csrf_token": csrf_token1},
    )
    assert replay_res.status_code == 401

    # 5. Subsequent refresh attempts on entire family now fail
    assert (
        client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": csrf_token2},
            cookies={"refresh_token": refresh_token2, "csrf_token": csrf_token2},
        ).status_code
        == 401
    )
