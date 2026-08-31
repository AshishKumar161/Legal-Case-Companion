import uuid

from fastapi.testclient import TestClient


def _setup_lawyer(
    client: TestClient, email: str, password: str, full_name: str = "Test Lawyer"
):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": "LAWYER",
            "full_name": full_name,
        },
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_lawyer_profile_read_verification_status(client: TestClient):
    _user_id, headers = _setup_lawyer(client, "lawyer1@test.com", "Pass123!")

    # Read Profile
    profile_res = client.get("/api/v1/profiles/me", headers=headers)
    assert profile_res.status_code == 200
    data = profile_res.json()
    assert data["verification_status"] == "PENDING"
    assert "password" not in data


def test_lawyer_verification_workflow(client: TestClient):
    _user_id, headers = _setup_lawyer(client, "lawyer2@test.com", "Pass123!")

    # Submit Verification
    res_submit = client.post(
        "/api/v1/profiles/lawyer/verification",
        json={"enrollment_number": "ABC/123/2023", "state_bar_council": "Delhi"},
        headers=headers,
    )
    assert res_submit.status_code == 200
    assert res_submit.json()["status"] == "PENDING"

    # Check Profile has verification_status
    profile_res = client.get("/api/v1/profiles/me", headers=headers)
    assert profile_res.json()["verification_status"] == "PENDING"

    # Duplicate submission fails
    res_dup = client.post(
        "/api/v1/profiles/lawyer/verification",
        json={"enrollment_number": "XYZ/123/2023", "state_bar_council": "Mumbai"},
        headers=headers,
    )
    assert res_dup.status_code == 422
    assert "already in progress" in res_dup.json()["error"]["message"]


def test_lawyer_mass_assignment_protection(client: TestClient):
    _user_id, headers = _setup_lawyer(client, "lawyer3@test.com", "Pass123!")

    # Attempt to mass-assign verification_status
    update_res = client.patch(
        "/api/v1/profiles/lawyer",
        json={"verification_status": "APPROVED", "location": "Delhi"},
        headers=headers,
    )

    assert update_res.status_code == 422
    assert update_res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_lawyer_suspension_visibility(client: TestClient):
    # Setup Lawyer
    user_id, _headers = _setup_lawyer(
        client, "lawyer4@test.com", "Pass123!", "Suspended Lawyer"
    )

    # Register as client
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "client2@test.com",
            "password": "SecurePassword123!",
            "full_name": "Client User",
            "role": "CLIENT",
        },
    )
    res_login = client.post(
        "/api/v1/auth/login",
        json={"email": "client2@test.com", "password": "SecurePassword123!"},
    )
    client_headers = {"Authorization": f"Bearer {res_login.json()['access_token']}"}

    import typing

    from fastapi import FastAPI

    from app.api.deps import get_db
    from app.models.user import AccountStatus, User

    app = typing.cast(FastAPI, client.app)
    db_gen = app.dependency_overrides.get(get_db, get_db)()
    db = next(db_gen)

    # Update lawyer4 to SUSPENDED manually to simulate admin action
    lawyer_user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    assert lawyer_user is not None
    lawyer_user.account_status = AccountStatus.SUSPENDED
    db.commit()

    # Search Lawyers
    res_search = client.get("/api/v1/lawyers", headers=client_headers)
    assert res_search.status_code == 200

    # Verify the suspended lawyer is NOT in the search results
    items = res_search.json()["items"]
    for item in items:
        assert item["full_name"] != "Suspended Lawyer"


def test_admin_approve_verification_creates_persisted_audit_event(client: TestClient, db):
    from app.core.identifiers import generate_uuid7
    from app.core.security import create_access_token, hash_password
    from app.models.audit import AuditEvent
    from app.models.user import AccountStatus, User, UserRole

    # Setup lawyer and submit verification
    _lawyer_id, l_headers = _setup_lawyer(
        client, "lawyer_audit_appr@test.com", "Pass123!", "Advocate Verma"
    )
    submit_res = client.post(
        "/api/v1/profiles/lawyer/verification",
        json={"enrollment_number": "D/999/2024", "state_bar_council": "Delhi"},
        headers=l_headers,
    )
    assert submit_res.status_code == 200
    verification_id = submit_res.json()["id"]

    # Setup Admin
    admin_user = User(
        id=generate_uuid7(),
        email="admin_audit_test@test.com",
        password_hash=hash_password("Pass123!"),
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(admin_user)
    db.commit()

    admin_token = create_access_token(str(admin_user.id), admin_user.role.value)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin approves verification
    approve_res = client.post(
        f"/api/v1/admin/verifications/{verification_id}/approve",
        headers=admin_headers,
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    # Query database to assert AuditEvent is actually committed
    audit = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.event_type == "LAWYER_VERIFICATION_APPROVED",
            AuditEvent.actor_user_id == admin_user.id,
        )
        .first()
    )
    assert audit is not None
    assert audit.action == "admin_mutation"
    assert audit.metadata_["verification_id"] == str(verification_id)


def test_admin_reject_verification_creates_persisted_audit_event(client: TestClient, db):
    from app.core.identifiers import generate_uuid7
    from app.core.security import create_access_token, hash_password
    from app.models.audit import AuditEvent
    from app.models.user import AccountStatus, User, UserRole

    # Setup lawyer and submit verification
    _lawyer_id, l_headers = _setup_lawyer(
        client, "lawyer_audit_rej@test.com", "Pass123!", "Advocate Kumar"
    )
    submit_res = client.post(
        "/api/v1/profiles/lawyer/verification",
        json={"enrollment_number": "D/888/2024", "state_bar_council": "Punjab"},
        headers=l_headers,
    )
    assert submit_res.status_code == 200
    verification_id = submit_res.json()["id"]

    # Setup Admin
    admin_user = User(
        id=generate_uuid7(),
        email="admin_audit_rej_test@test.com",
        password_hash=hash_password("Pass123!"),
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(admin_user)
    db.commit()

    admin_token = create_access_token(str(admin_user.id), admin_user.role.value)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin rejects verification
    reject_res = client.post(
        f"/api/v1/admin/verifications/{verification_id}/reject",
        headers=admin_headers,
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "REJECTED"

    # Query database to assert AuditEvent is actually committed
    audit = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.event_type == "LAWYER_VERIFICATION_REJECTED",
            AuditEvent.actor_user_id == admin_user.id,
        )
        .first()
    )
    assert audit is not None
    assert audit.action == "admin_mutation"
    assert audit.metadata_["verification_id"] == str(verification_id)
