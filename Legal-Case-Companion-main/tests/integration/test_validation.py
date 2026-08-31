from fastapi.testclient import TestClient


def _setup_user(client: TestClient, email: str):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePassword123!",
            "role": "CLIENT",
            "full_name": "Test User",
        },
    )
    res = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"}
    )
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_validation_error_canonical_format(client: TestClient):
    headers = _setup_user(client, "valid@test.com")

    # Test missing required field
    res = client.post(
        "/api/v1/cases", json={"description": "Missing title"}, headers=headers
    )
    assert res.status_code == 422
    json_data = res.json()
    assert "error" in json_data
    assert json_data["error"]["code"] == "VALIDATION_ERROR"
    assert "request_id" in json_data["error"]
    assert "details" in json_data["error"]
    assert any(
        detail["loc"] == ["body", "title"] for detail in json_data["error"]["details"]
    )

    # Test invalid field type (case_id as invalid string instead of UUID)
    res = client.get("/api/v1/cases/not-a-uuid", headers=headers)
    assert res.status_code == 422
    json_data = res.json()
    assert json_data["error"]["code"] == "VALIDATION_ERROR"
    assert any(
        detail["loc"] == ["path", "case_id"] for detail in json_data["error"]["details"]
    )

    # Test malformed request body (invalid JSON)
    res = client.post(
        "/api/v1/cases",
        content="invalid json",
        headers={"Content-Type": "application/json", **headers},
    )
    assert res.status_code == 422
    json_data = res.json()
    assert json_data["error"]["code"] == "VALIDATION_ERROR"

    # Test malformed query parameter (skip parameter as string)
    res = client.get("/api/v1/cases?skip=abc", headers=headers)
    assert res.status_code == 422
    json_data = res.json()
    assert json_data["error"]["code"] == "VALIDATION_ERROR"
    assert any(
        detail["loc"] == ["query", "skip"] for detail in json_data["error"]["details"]
    )
