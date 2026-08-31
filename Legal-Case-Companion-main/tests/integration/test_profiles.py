from fastapi.testclient import TestClient


def test_admin_registration_forbidden(client: TestClient):
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@test.com",
            "password": "SecurePassword123!",
            "full_name": "Admin User",
            "role": "ADMIN",
        },
    )
    assert res.status_code == 403
    assert "Cannot register as ADMIN" in res.json()["error"]["message"]


def test_profile_read_client(client: TestClient):
    # Register client
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "clientprofile@test.com",
            "password": "SecurePassword123!",
            "full_name": "Test Client",
            "role": "CLIENT",
        },
    )
    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "clientprofile@test.com", "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]

    # Read Profile
    profile_res = client.get(
        "/api/v1/profiles/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert profile_res.status_code == 200
    data = profile_res.json()
    assert data["full_name"] == "Test Client"
    assert "password" not in data
    assert "password_hash" not in data


def test_profile_update_client_allowed_fields(client: TestClient):
    # Register client
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "clientupdate@test.com",
            "password": "SecurePassword123!",
            "full_name": "Test Client",
            "role": "CLIENT",
        },
    )
    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "clientupdate@test.com", "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]

    # Update Profile
    update_res = client.patch(
        "/api/v1/profiles/client",
        headers={"Authorization": f"Bearer {token}"},
        json={"location": "Mumbai", "full_name": "Updated Name"},
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["location"] == "Mumbai"
    assert data["full_name"] == "Updated Name"


def test_profile_update_mass_assignment_protection(client: TestClient):
    # Register client
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "clientmass@test.com",
            "password": "SecurePassword123!",
            "full_name": "Test Client",
            "role": "CLIENT",
        },
    )
    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "clientmass@test.com", "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]

    # Update Profile with protected fields (mass assignment attempt)
    # Because of extra='forbid', this should return 422
    update_res = client.patch(
        "/api/v1/profiles/client",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "location": "Delhi",
            "account_status": "ADMIN",
            "role": "ADMIN",
            "password_hash": "hacked",
        },
    )
    assert update_res.status_code == 422
    assert "error" in update_res.json()
    assert update_res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_profile_read_admin_not_found(client: TestClient, db):
    from app.core.identifiers import generate_uuid7
    from app.core.security import create_access_token, hash_password
    from app.models.user import AccountStatus, User, UserRole

    admin_user = User(
        id=generate_uuid7(),
        email="admin_profile_test@test.com",
        password_hash=hash_password("Pass123!"),
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(admin_user)
    db.commit()

    token = create_access_token(str(admin_user.id), admin_user.role.value)
    res = client.get(
        "/api/v1/profiles/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 404
    body = res.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert "Profile not found" in body["error"]["message"]


def test_profile_read_lawyer(client: TestClient):
    # Register lawyer
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "lawyer_profile_test@test.com",
            "password": "SecurePassword123!",
            "full_name": "Advocate Sharma",
            "role": "LAWYER",
        },
    )
    assert reg_res.status_code == 201

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "lawyer_profile_test@test.com", "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]

    res = client.get(
        "/api/v1/profiles/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["full_name"] == "Advocate Sharma"
    assert "practice_areas" in data
    assert "consultation_fee" in data
