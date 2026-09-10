from uuid import uuid4

from fastapi.testclient import TestClient


def _setup_user(
    client: TestClient,
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


def test_case_create_and_read(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "owner.cases@example.com", "Pass123!")

    # Create case
    res = client.post(
        "/api/v1/cases",
        json={"title": "My New Case", "description": "Case description"},
        headers=h_owner,
    )

    assert res.status_code == 201
    case_data = res.json()
    assert case_data["title"] == "My New Case"
    case_id = case_data["id"]

    # Read case as owner
    res_get = client.get(f"/api/v1/cases/{case_id}", headers=h_owner)
    assert res_get.status_code == 200
    assert res_get.json()["id"] == case_id


def test_case_bola_protection(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "bola.owner@example.com", "Pass123!")
    _other_id, h_other = _setup_user(client, "bola.other@example.com", "Pass123!")

    # Owner creates case
    res = client.post(
        "/api/v1/cases",
        json={"title": "Top Secret Case", "description": "Secret"},
        headers=h_owner,
    )
    case_id = res.json()["id"]

    # Other user tries to read case
    res_get = client.get(f"/api/v1/cases/{case_id}", headers=h_other)
    assert res_get.status_code == 404  # BOLA protection should obscure existence!

    # Other user tries to update case
    res_update = client.patch(
        f"/api/v1/cases/{case_id}", json={"title": "Hacked"}, headers=h_other
    )
    assert res_update.status_code == 404

    # Other user tries to delete case
    res_delete = client.delete(f"/api/v1/cases/{case_id}", headers=h_other)
    assert res_delete.status_code == 404


def test_case_list_isolation_and_ordering(client: TestClient):
    _u1_id, h_u1 = _setup_user(client, "list1@example.com", "Pass123!")
    _u2_id, h_u2 = _setup_user(client, "list2@example.com", "Pass123!")

    # U1 creates 2 cases
    client.post(
        "/api/v1/cases", json={"title": "U1 Case 1", "description": "D"}, headers=h_u1
    )
    client.post(
        "/api/v1/cases", json={"title": "U1 Case 2", "description": "D"}, headers=h_u1
    )

    # U2 creates 1 case
    client.post(
        "/api/v1/cases", json={"title": "U2 Case 1", "description": "D"}, headers=h_u2
    )

    # Check U1 list
    res_u1 = client.get("/api/v1/cases", headers=h_u1)
    assert res_u1.status_code == 200
    data_u1 = res_u1.json()
    assert data_u1["total"] == 2
    assert data_u1["items"][0]["title"] == "U1 Case 2"  # Ordered by created_at desc!
    assert data_u1["items"][1]["title"] == "U1 Case 1"

    # Check U2 list
    res_u2 = client.get("/api/v1/cases", headers=h_u2)
    data_u2 = res_u2.json()
    assert data_u2["total"] == 1
    assert data_u2["items"][0]["title"] == "U2 Case 1"


def test_case_mass_assignment_protection(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "mass.cases@example.com", "Pass123!")

    # Attempt to create case with injected ID
    res = client.post(
        "/api/v1/cases",
        json={
            "title": "Hacked Case",
            "description": "D",
            "id": str(uuid4()),
            "status": "CLOSED",
        },
        headers=h_owner,
    )

    assert res.status_code == 422  # Because extra fields are forbidden

    # Create valid case
    res2 = client.post(
        "/api/v1/cases",
        json={"title": "Valid Case", "description": "D"},
        headers=h_owner,
    )
    case_id = res2.json()["id"]

    # Attempt to mass assign status and deleted_at
    res_patch = client.patch(
        f"/api/v1/cases/{case_id}",
        json={"deleted_at": "2030-01-01T00:00:00Z"},
        headers=h_owner,
    )
    assert res_patch.status_code == 422


def test_case_delete_lifecycle(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "delete.cases@example.com", "Pass123!")

    # Create case
    res = client.post(
        "/api/v1/cases",
        json={"title": "To Be Deleted", "description": "D"},
        headers=h_owner,
    )
    case_id = res.json()["id"]

    # Delete case
    res_del = client.delete(f"/api/v1/cases/{case_id}", headers=h_owner)
    assert res_del.status_code == 204

    # Verify it is no longer readable
    res_get = client.get(f"/api/v1/cases/{case_id}", headers=h_owner)
    assert res_get.status_code == 404

    # Verify it is no longer listed
    res_list = client.get("/api/v1/cases", headers=h_owner)
    assert res_list.json()["total"] == 0

    # Verify second delete returns 404 (already deleted/obscured)
    res_del2 = client.delete(f"/api/v1/cases/{case_id}", headers=h_owner)
    assert res_del2.status_code == 404


def test_case_unauthenticated_creation(client: TestClient):
    res = client.post(
        "/api/v1/cases", json={"title": "New Case", "description": "Desc"}
    )
    assert res.status_code == 401


def test_case_update_authorized(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "owner.update@example.com", "Pass123!")
    res = client.post(
        "/api/v1/cases",
        json={"title": "Old Title", "description": "Old Desc"},
        headers=h_owner,
    )
    case_id = res.json()["id"]

    res_patch = client.patch(
        f"/api/v1/cases/{case_id}", json={"title": "New Title"}, headers=h_owner
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["title"] == "New Title"
