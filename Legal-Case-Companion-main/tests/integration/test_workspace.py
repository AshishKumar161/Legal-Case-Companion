from fastapi.testclient import TestClient


def _setup_user(
    client: TestClient,
    email: str,
    password: str,
    role: str = "CLIENT",
    full_name: str = "Test User",
):
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


def test_workspace_permissions(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "workspace.owner@example.com", "Pass123!")

    # Create case
    res = client.post(
        "/api/v1/cases",
        json={"title": "Workspace Case", "description": "D"},
        headers=h_owner,
    )
    case_id = res.json()["id"]

    # Get Workspace
    res_ws = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_owner)
    assert res_ws.status_code == 200
    ws = res_ws.json()

    perms = ws["effective_permissions"]
    assert "UPDATE_CASE" in perms
    assert "UPLOAD_DOCUMENT" in perms
    assert "VIEW_DOCUMENTS" in perms

    # Close case
    client.patch(f"/api/v1/cases/{case_id}", json={"status": "CLOSED"}, headers=h_owner)

    # Get Workspace again
    res_ws_closed = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_owner)
    assert res_ws_closed.status_code == 200
    perms_closed = res_ws_closed.json()["effective_permissions"]

    # Mutable permissions should be gone
    assert "UPDATE_CASE" not in perms_closed
    assert "UPLOAD_DOCUMENT" not in perms_closed
    assert "VIEW_DOCUMENTS" in perms_closed  # Can still view
