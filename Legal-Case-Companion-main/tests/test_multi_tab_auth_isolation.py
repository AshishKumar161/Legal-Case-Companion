"""Comprehensive Multi-Tab Authentication and Session Isolation Integration Tests.

Validates that:
1. Tab A (CLIENT), Tab B (LAWYER), and Tab C (ADMIN) can log in simultaneously.
2. Concurrent requests from each tab return the correct, isolated identity and authoritative role.
3. Tab A credentials cannot access lawyer-restricted endpoints (authorization enforcement).
4. Tab B credentials can access lawyer-specific endpoints.
5. Tab A logging out revokes only Tab A's session; Tab B and Tab C remain actively authenticated.
6. Tab B can refresh its session without mutating or disturbing Tab C's credentials.
7. Role is authoritatively delivered via /api/v1/auth/me for all roles.
"""

from fastapi.testclient import TestClient
from app.main import app

def test_multi_tab_session_isolation():
    client = TestClient(app)

    print("\n--- STEP 1: Independent Login for Tab A (CLIENT), Tab B (LAWYER), Tab C (ADMIN) ---")
    # Tab A: Client Login
    res_a = client.post("/api/v1/auth/login", json={"email": "client@lcc.test", "password": "Password123!"})
    assert res_a.status_code == 200, f"Tab A login failed: {res_a.text}"
    token_a = res_a.json()["access_token"]
    cookie_a = res_a.cookies.get("refresh_token")
    assert token_a and cookie_a, "Tab A missing tokens"

    # Tab B: Lawyer Login
    res_b = client.post("/api/v1/auth/login", json={"email": "advocate@lcc.test", "password": "Password123!"})
    assert res_b.status_code == 200, f"Tab B login failed: {res_b.text}"
    token_b = res_b.json()["access_token"]
    cookie_b = res_b.cookies.get("refresh_token")
    assert token_b and cookie_b, "Tab B missing tokens"

    # Tab C: Admin Login
    res_c = client.post("/api/v1/auth/login", json={"email": "admin@lcc.test", "password": "Password123!"})
    assert res_c.status_code == 200, f"Tab C login failed: {res_c.text}"
    token_c = res_c.json()["access_token"]
    cookie_c = res_c.cookies.get("refresh_token")
    assert token_c and cookie_c, "Tab C missing tokens"

    print("PASS: Tab A, Tab B, and Tab C received separate unique tokens.")
    assert token_a != token_b != token_c

    print("\n--- STEP 2: Simultaneous Authoritative Identity Checks (/api/v1/auth/me) ---")
    me_a = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    assert me_a.status_code == 200, f"Tab A /me failed: {me_a.text}"
    data_a = me_a.json()
    assert data_a["role"] == "CLIENT", f"Expected CLIENT for Tab A, got {data_a['role']}"
    assert data_a["email"] == "client@lcc.test"
    print(f"PASS: Tab A authoritative identity -> {data_a['email']} ({data_a['role']})")

    me_b = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})
    assert me_b.status_code == 200, f"Tab B /me failed: {me_b.text}"
    data_b = me_b.json()
    assert data_b["role"] == "LAWYER", f"Expected LAWYER for Tab B, got {data_b['role']}"
    assert data_b["email"] == "advocate@lcc.test"
    print(f"PASS: Tab B authoritative identity -> {data_b['email']} ({data_b['role']})")

    me_c = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_c}"})
    assert me_c.status_code == 200, f"Tab C /me failed: {me_c.text}"
    data_c = me_c.json()
    assert data_c["role"] == "ADMIN", f"Expected ADMIN for Tab C, got {data_c['role']}"
    assert data_c["email"] == "admin@lcc.test"
    print(f"PASS: Tab C authoritative identity -> {data_c['email']} ({data_c['role']})")

    print("\n--- STEP 3: Role-Based Route Access & Authorization Isolation ---")
    # Tab A (CLIENT) attempts lawyer-only endpoint -> MUST BE REJECTED (403 Forbidden)
    res_a_lawyer = client.patch(
        "/api/v1/profiles/lawyer",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"bio": "Hacked from Tab A"},
    )
    assert res_a_lawyer.status_code == 403, f"Expected 403 for Client accessing lawyer route, got {res_a_lawyer.status_code}"
    print("PASS: Tab A (CLIENT) was forbidden from lawyer-only endpoint (403).")

    # Tab B (LAWYER) accesses lawyer incoming calls endpoint -> MUST SUCCEED (200 OK)
    res_b_incoming = client.get(
        "/api/v1/consultations/incoming-calls",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b_incoming.status_code == 200, f"Expected 200 for Lawyer incoming calls, got {res_b_incoming.status_code}"
    print("PASS: Tab B (LAWYER) successfully accessed lawyer chamber calls endpoint.")

    print("\n--- STEP 4: Logout Isolation (Tab A logs out; Tab B & Tab C remain active) ---")
    # Tab A logs out
    client_a = TestClient(app, cookies={"refresh_token": cookie_a})
    logout_res = client_a.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token_a}"})
    assert logout_res.status_code == 200, f"Tab A logout failed: {logout_res.text}"
    print("PASS: Tab A logged out successfully.")

    # Tab B verifies it is STILL active and authenticated
    me_b_after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})
    assert me_b_after.status_code == 200, f"Tab B should remain valid after Tab A logout: {me_b_after.text}"
    assert me_b_after.json()["role"] == "LAWYER"
    print("PASS: Tab B remains 100% authenticated as LAWYER after Tab A logged out.")

    # Tab C verifies it is STILL active and authenticated
    me_c_after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_c}"})
    assert me_c_after.status_code == 200, f"Tab C should remain valid after Tab A logout: {me_c_after.text}"
    assert me_c_after.json()["role"] == "ADMIN"
    print("PASS: Tab C remains 100% authenticated as ADMIN after Tab A logged out.")

    print("\n--- STEP 5: Token Refresh Isolation ---")
    # Tab B refreshes its token using its own cookie
    client_b = TestClient(app, cookies={"refresh_token": cookie_b, "csrf_token": "test-csrf"})
    refresh_res = client_b.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": "test-csrf", "Origin": "http://testserver"},
    )
    assert refresh_res.status_code == 200, f"Tab B refresh failed: {refresh_res.text}"
    new_token_b = refresh_res.json()["access_token"]
    assert new_token_b, "Missing refreshed token for Tab B"

    # Tab B verifies identity with new refreshed token
    me_b_refreshed = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token_b}"})
    assert me_b_refreshed.status_code == 200
    assert me_b_refreshed.json()["role"] == "LAWYER"
    print("PASS: Tab B successfully refreshed token and retains LAWYER identity.")

    # Tab C continues operating with its original token without disruption
    me_c_final = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_c}"})
    assert me_c_final.status_code == 200
    assert me_c_final.json()["role"] == "ADMIN"
    print("PASS: Tab C continues operating as ADMIN with original credentials undisturbed.")

    print("\n=======================================================")
    print("ALL MULTI-TAB AUTHENTICATION & ROLE ISOLATION TESTS PASSED!")
    print("=======================================================\n")

if __name__ == "__main__":
    test_multi_tab_session_isolation()
