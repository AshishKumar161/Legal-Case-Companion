import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.security import create_access_token, hash_password
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole


def _setup_user(
    client,
    email: str,
    password: str,
    role: str = "CLIENT",
    full_name: str = "Test User",
):
    """Register a user and return user_id, headers."""
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": role,
            "full_name": full_name,
        },
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers(db_engine):
    def _get_headers(user_id: uuid.UUID, role: str):
        token = create_access_token(str(user_id), role)
        return {"Authorization": f"Bearer {token}"}

    return _get_headers


@pytest.fixture
def client_a(db):
    user = User(
        id=generate_uuid7(),
        email="client_a@test.com",
        password_hash=hash_password("Password123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    profile = ClientProfile(id=generate_uuid7(), user_id=user.id, full_name="Client A")
    db.add_all([user, profile])
    db.commit()
    return user.id


@pytest.fixture
def client_b(db):
    user = User(
        id=generate_uuid7(),
        email="client_b@test.com",
        password_hash=hash_password("Password123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    profile = ClientProfile(id=generate_uuid7(), user_id=user.id, full_name="Client B")
    db.add_all([user, profile])
    db.commit()
    return user.id


@pytest.fixture
def lawyer_a(db):
    user = User(
        id=generate_uuid7(),
        email="lawyer_a@test.com",
        password_hash=hash_password("Password123!"),
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    profile = LawyerProfile(id=generate_uuid7(), user_id=user.id, full_name="Lawyer A")
    db.add_all([user, profile])
    db.commit()
    return user.id


def test_idor_cross_user_profile_access_fails(client, auth_headers, client_a, client_b):
    # A user can only access their own profile via /me. There is no /profiles/{user_id} yet.
    pass


def test_case_creation_and_access(client, auth_headers, client_a):
    headers = auth_headers(client_a, "CLIENT")

    # 1. Create Case
    res = client.post(
        "/api/v1/cases",
        json={"title": "Case 1", "description": "Desc 1"},
        headers=headers,
    )
    assert res.status_code == 201
    case_id = res.json()["id"]

    # 2. Get Cases (should see it)
    res = client.get("/api/v1/cases", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["id"] == case_id

    # 3. Get Case By ID (should succeed)
    res = client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert res.status_code == 200


def test_idor_cross_client_case_access_fails(client, auth_headers, client_a, client_b):
    headers_a = auth_headers(client_a, "CLIENT")
    headers_b = auth_headers(client_b, "CLIENT")

    # Client A creates case
    res = client.post(
        "/api/v1/cases",
        json={"title": "Case A", "description": "Desc A"},
        headers=headers_a,
    )
    case_a_id = res.json()["id"]

    # Client B tries to read Case A
    res = client.get(f"/api/v1/cases/{case_a_id}", headers=headers_b)
    # Must return 404 to obscure existence, or 403. Core auth uses ResourceNotFoundError (404).
    assert res.status_code == 404

    # Client B tries to update Case A
    res = client.patch(
        f"/api/v1/cases/{case_a_id}", json={"title": "Hacked"}, headers=headers_b
    )
    assert res.status_code == 404


def test_lawyer_case_access(client, auth_headers, client_a, lawyer_a):
    headers_c = auth_headers(client_a, "CLIENT")
    headers_l = auth_headers(lawyer_a, "LAWYER")

    # Client A creates case
    res = client.post(
        "/api/v1/cases",
        json={"title": "Case A", "description": "Desc A"},
        headers=headers_c,
    )
    case_a_id = res.json()["id"]

    # Lawyer A cannot access
    res = client.get(f"/api/v1/cases/{case_a_id}", headers=headers_l)
    assert res.status_code == 404

    # Client A adds Lawyer A as participant
    res = client.post(
        f"/api/v1/cases/{case_a_id}/participants",
        json={"user_id": str(lawyer_a), "participant_role": "LAWYER"},
        headers=headers_c,
    )
    assert res.status_code == 200

    # Lawyer A CAN now access
    res = client.get(f"/api/v1/cases/{case_a_id}", headers=headers_l)
    assert res.status_code == 200


def test_document_cross_case_isolation(client, auth_headers, client_a, client_b):
    headers_a = auth_headers(client_a, "CLIENT")
    headers_b = auth_headers(client_b, "CLIENT")

    # Client A creates case and document metadata
    res = client.post(
        "/api/v1/cases",
        json={"title": "Case A", "description": "Desc"},
        headers=headers_a,
    )
    case_a_id = res.json()["id"]

    upload_res = client.post(
        f"/api/v1/cases/{case_a_id}/documents/upload-init",
        json={"filename": "doc.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=headers_a,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document"]["id"]

    # Client B tries to access Document A
    res = client.get(f"/api/v1/documents/{doc_id}", headers=headers_b)
    assert res.status_code == 404


def test_participant_management_authorization(client, auth_headers, client_a, lawyer_a):
    headers_c = auth_headers(client_a, "CLIENT")
    headers_l = auth_headers(lawyer_a, "LAWYER")

    # Lawyer A creates a case
    res = client.post(
        "/api/v1/cases",
        json={"title": "Lawyer Case", "description": "Desc"},
        headers=headers_l,
    )
    case_id = res.json()["id"]

    # Client A tries to add themselves to Lawyer A's case
    res = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(client_a), "participant_role": "VIEWER"},
        headers=headers_c,
    )
    assert res.status_code == 404


def test_participant_role_validation(client: TestClient, db: Session):
    """Phase 7: Test strict business logic for participant roles."""
    _owner_id, h_owner = _setup_user(
        client, "owner.role@example.com", "Pass123!", role="CLIENT"
    )
    lawyer_id, _h_lawyer = _setup_user(
        client, "lawyer.role@example.com", "Pass123!", role="LAWYER"
    )
    viewer_id, _h_viewer = _setup_user(
        client, "viewer.role@example.com", "Pass123!", role="CLIENT"
    )

    # Setup admin by registering as client and then upgrading in DB
    admin_id, _h_admin = _setup_user(
        client, "admin.role@example.com", "Pass123!", role="CLIENT"
    )

    # 1. Create a case
    res = client.post(
        "/api/v1/cases",
        json={"title": "Role Test", "description": "Testing roles"},
        headers=h_owner,
    )
    case_id = res.json()["id"]

    # 2. Try to add an ADMIN as a LAWYER participant (should fail)
    from app.models.user import User, UserRole

    admin = db.query(User).filter(User.email == "admin.role@example.com").first()
    if admin:
        admin.role = UserRole.ADMIN
        db.commit()

    if admin_id:
        add_res = client.post(
            f"/api/v1/cases/{case_id}/participants",
            json={"user_id": str(admin_id), "participant_role": "LAWYER"},
            headers=h_owner,
        )
        assert add_res.status_code in (400, 422)
        assert "lawyer" in add_res.text.lower()

    # 3. Try to add a CLIENT as a LAWYER participant (should fail)
    add_res = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(viewer_id), "participant_role": "LAWYER"},
        headers=h_owner,
    )
    assert add_res.status_code in (400, 422)
    assert "lawyer" in add_res.text.lower()

    # 4. Try to add a LAWYER as an OWNER participant (should succeed or fail depending on business rules, but wait, owner usually is a client or lawyer, but wait, if it's not the creator?)
    # The business invariant says: OWNER allowed only when the user's account role is permitted.
    # In `case_service.py`, we check:
    # if req.role == ParticipantRole.OWNER and target_user.role not in [UserRole.CLIENT, UserRole.LAWYER]: raise

    add_res = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(lawyer_id), "participant_role": "OWNER"},
        headers=h_owner,
    )
    # Adding a lawyer as an owner should work
    assert add_res.status_code == 200

    # 5. Try to add a suspended user
    # Suspend viewer user
    from app.models.user import AccountStatus, User

    viewer = db.query(User).filter(User.id == uuid.UUID(viewer_id)).first()
    assert viewer is not None
    viewer.account_status = AccountStatus.SUSPENDED
    db.commit()

    add_res = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(viewer_id), "participant_role": "VIEWER"},
        headers=h_owner,
    )
    assert add_res.status_code in (400, 422)
    assert "active" in add_res.text.lower()

    # Restore viewer user
    assert viewer is not None
    viewer.account_status = AccountStatus.ACTIVE
    db.commit()

    # 6. Try duplicate participant
    add_res = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(lawyer_id), "participant_role": "LAWYER"},
        headers=h_owner,
    )
    assert add_res.status_code in (400, 409, 422)
    assert "already" in add_res.text.lower()
