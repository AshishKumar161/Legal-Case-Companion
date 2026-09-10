from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, email: str, role: str = "CLIENT", full_name: str = "Test User"):
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": full_name,
            "role": role,
        },
    )
    assert reg_res.status_code == 201, reg_res.text
    user_id = reg_res.json()["id"]

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_client_profile_read_and_update(client: TestClient):
    _user_id, headers = _register_and_login(client, "client_settings@test.com", "CLIENT", "Client User")

    # 1. Read Profile
    get_res = client.get("/api/v1/profiles/me", headers=headers)
    assert get_res.status_code == 200, get_res.text
    data = get_res.json()
    assert data["full_name"] == "Client User"
    assert data["email"] == "client_settings@test.com"
    assert data["phone"] is None
    assert data["location"] is None

    # 2. Update Profile with phone and location
    patch_res = client.patch(
        "/api/v1/profiles/client",
        headers=headers,
        json={
            "full_name": "Updated Client Name",
            "location": "New Delhi, India",
            "phone": "+919876543210",
        },
    )
    assert patch_res.status_code == 200, patch_res.text
    updated = patch_res.json()
    assert updated["full_name"] == "Updated Client Name"
    assert updated["location"] == "New Delhi, India"
    assert updated["phone"] == "+919876543210"

    # 3. Read again to verify persistence
    get_res2 = client.get("/api/v1/profiles/me", headers=headers)
    assert get_res2.status_code == 200
    assert get_res2.json()["full_name"] == "Updated Client Name"
    assert get_res2.json()["phone"] == "+919876543210"


def test_lawyer_profile_read_and_update(client: TestClient):
    _user_id, headers = _register_and_login(client, "advocate_settings@test.com", "LAWYER", "Adv. Sharma")

    # 1. Read Lawyer Profile
    get_res = client.get("/api/v1/profiles/me", headers=headers)
    assert get_res.status_code == 200, get_res.text
    data = get_res.json()
    assert data["full_name"] == "Adv. Sharma"
    assert data["email"] == "advocate_settings@test.com"
    assert data["verification_status"] == "PENDING"

    # 2. Update Lawyer Profile
    patch_res = client.patch(
        "/api/v1/profiles/lawyer",
        headers=headers,
        json={
            "full_name": "Adv. Rajesh Sharma",
            "bio": "Senior Advocate specializing in Commercial Litigation and Arbitration.",
            "location": "New Delhi, NCR",
            "phone": "+919811122233",
            "consultation_fee": 3500.0,
            "experience_years": 15,
            "practice_areas": ["Corporate Law", "Arbitration", "IPR"],
            "court_jurisdictions": ["Supreme Court of India", "Delhi High Court"],
        },
    )
    assert patch_res.status_code == 200, patch_res.text
    updated = patch_res.json()
    assert updated["full_name"] == "Adv. Rajesh Sharma"
    assert updated["consultation_fee"] == 3500.0
    assert updated["experience_years"] == 15
    assert "Arbitration" in updated["practice_areas"]
    assert "Delhi High Court" in updated["court_jurisdictions"]
    assert updated["phone"] == "+919811122233"


def test_profile_role_based_update_isolation(client: TestClient):
    _c_id, client_headers = _register_and_login(client, "iso_client@test.com", "CLIENT", "Iso Client")
    _l_id, lawyer_headers = _register_and_login(client, "iso_lawyer@test.com", "LAWYER", "Iso Lawyer")

    # Client cannot update lawyer profile (403)
    res1 = client.patch(
        "/api/v1/profiles/lawyer",
        headers=client_headers,
        json={"bio": "Hacker attempt"},
    )
    assert res1.status_code == 403

    # Lawyer cannot update client profile (403)
    res2 = client.patch(
        "/api/v1/profiles/client",
        headers=lawyer_headers,
        json={"location": "Pune"},
    )
    assert res2.status_code == 403


def test_in_app_password_change_lifecycle(client: TestClient):
    _user_id, headers = _register_and_login(client, "pwd_change_user@test.com", "CLIENT", "Password User")

    # 1. Invalid current password rejected
    bad_res = client.post(
        "/api/v1/auth/password/change",
        headers=headers,
        json={"current_password": "WrongPassword123!", "new_password": "BrandNewPassword123!"},
    )
    assert bad_res.status_code == 401

    # 2. Valid password change succeeds
    good_res = client.post(
        "/api/v1/auth/password/change",
        headers=headers,
        json={"current_password": "Password123!", "new_password": "BrandNewPassword123!"},
    )
    assert good_res.status_code == 200, good_res.text
    assert good_res.json()["detail"] == "Password changed successfully"

    # 3. Old password login fails
    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "pwd_change_user@test.com", "password": "Password123!"},
    )
    assert old_login.status_code == 401

    # 4. New password login succeeds
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "pwd_change_user@test.com", "password": "BrandNewPassword123!"},
    )
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()


def test_notification_preferences_get_and_patch(client: TestClient):
    _user_id, headers = _register_and_login(client, "notif_pref_user@test.com", "CLIENT", "Notif User")

    # 1. Default preferences
    get_res = client.get("/api/v1/notifications/preferences", headers=headers)
    assert get_res.status_code == 200, get_res.text
    prefs = get_res.json()
    assert prefs["email_enabled"] is True
    assert prefs["case_updates"] is True
    assert prefs["task_updates"] is True
    assert prefs["consultation_updates"] is True

    # 2. Update preferences
    patch_res = client.patch(
        "/api/v1/notifications/preferences",
        headers=headers,
        json={
            "email_enabled": False,
            "task_updates": False,
        },
    )
    assert patch_res.status_code == 200, patch_res.text
    updated = patch_res.json()
    assert updated["email_enabled"] is False
    assert updated["task_updates"] is False
    assert updated["case_updates"] is True
    assert updated["consultation_updates"] is True

    # 3. Read again to verify persistence
    get_res2 = client.get("/api/v1/notifications/preferences", headers=headers)
    assert get_res2.status_code == 200
    assert get_res2.json()["email_enabled"] is False
    assert get_res2.json()["task_updates"] is False
