from fastapi.testclient import TestClient

from app.core.identifiers import generate_uuid7


def _register_user(
    client: TestClient,
    email: str,
    role: str = "CLIENT",
    full_name: str = "Test API User",
):
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "role": role,
            "full_name": full_name,
        },
    )
    user_id = res.json().get("id")
    res_login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Password123!"}
    )
    token = res_login.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_api_unauthenticated_matrix(client: TestClient):
    """Ensure all protected routes return 401 when accessed without credentials."""
    dummy_uuid = str(generate_uuid7())
    protected_endpoints = [
        ("GET", "/api/v1/profiles/me"),
        ("PATCH", "/api/v1/profiles/client"),
        ("PATCH", "/api/v1/profiles/lawyer"),
        ("POST", "/api/v1/profiles/lawyer/verification"),
        ("GET", "/api/v1/cases"),
        ("POST", "/api/v1/cases"),
        ("GET", f"/api/v1/cases/{dummy_uuid}"),
        ("PATCH", f"/api/v1/cases/{dummy_uuid}"),
        ("DELETE", f"/api/v1/cases/{dummy_uuid}"),
        ("GET", f"/api/v1/cases/{dummy_uuid}/workspace"),
        ("GET", f"/api/v1/cases/{dummy_uuid}/timeline"),
        ("GET", f"/api/v1/cases/{dummy_uuid}/participants"),
        ("POST", f"/api/v1/cases/{dummy_uuid}/participants"),
        ("GET", f"/api/v1/cases/{dummy_uuid}/notes"),
        ("POST", f"/api/v1/cases/{dummy_uuid}/notes"),
        ("GET", f"/api/v1/cases/{dummy_uuid}/tasks"),
        ("POST", f"/api/v1/cases/{dummy_uuid}/tasks"),
        ("GET", f"/api/v1/cases/{dummy_uuid}/documents"),
        ("POST", f"/api/v1/cases/{dummy_uuid}/documents/upload-init"),
        ("GET", f"/api/v1/documents/{dummy_uuid}"),
        ("DELETE", f"/api/v1/documents/{dummy_uuid}"),
        ("POST", f"/api/v1/documents/{dummy_uuid}/complete"),
        ("GET", f"/api/v1/documents/{dummy_uuid}/download"),
        ("GET", "/api/v1/consultations"),
        ("POST", "/api/v1/consultations"),
        ("GET", f"/api/v1/consultations/{dummy_uuid}"),
        ("POST", f"/api/v1/consultations/{dummy_uuid}/accept"),
        ("POST", f"/api/v1/consultations/{dummy_uuid}/reject"),
        ("POST", f"/api/v1/consultations/{dummy_uuid}/schedule"),
        ("POST", f"/api/v1/consultations/{dummy_uuid}/cancel"),
        ("POST", f"/api/v1/consultations/{dummy_uuid}/complete"),
        ("GET", f"/api/v1/consultations/{dummy_uuid}/messages"),
        ("POST", f"/api/v1/consultations/{dummy_uuid}/messages"),
        ("GET", f"/api/v1/consultations/{dummy_uuid}/payments"),
        ("POST", f"/api/v1/consultations/{dummy_uuid}/payments"),
        ("GET", f"/api/v1/payments/{dummy_uuid}"),
        ("GET", "/api/v1/notifications"),
        ("GET", "/api/v1/notifications/unread-count"),
        ("POST", f"/api/v1/notifications/{dummy_uuid}/read"),
        ("POST", f"/api/v1/notifications/{dummy_uuid}/unread"),
        ("DELETE", f"/api/v1/notifications/{dummy_uuid}"),
        ("POST", "/api/v1/notifications/read-all"),
        ("GET", "/api/v1/admin/verifications"),
        ("POST", f"/api/v1/admin/verifications/{dummy_uuid}/approve"),
        ("POST", f"/api/v1/admin/verifications/{dummy_uuid}/reject"),
        ("GET", "/api/v1/analytics/funnel"),
        ("GET", "/api/v1/analytics/ai-health"),
        ("POST", "/api/v1/feedback"),
        ("POST", f"/api/v1/cases/{dummy_uuid}/ai/research"),
        ("GET", f"/api/v1/cases/{dummy_uuid}/ai/conversations"),
        ("POST", f"/api/v1/cases/{dummy_uuid}/ai/conversations"),
    ]

    for method, path in protected_endpoints:
        if method == "GET":
            res = client.get(path)
        elif method == "POST":
            res = client.post(path, json={})
        elif method == "PATCH":
            res = client.patch(path, json={})
        elif method == "DELETE":
            res = client.delete(path)
        else:
            continue

        assert (
            res.status_code == 401
        ), f"Expected 401 for {method} {path}, got {res.status_code}"
        assert "error" in res.json()
        assert res.json()["error"]["code"] in (
            "UNAUTHORIZED",
            "INVALID_TOKEN",
            "HTTP_ERROR",
        )


def test_api_public_health_endpoints(client: TestClient):
    """Ensure health checks respond without credentials."""
    res_live = client.get("/api/v1/health/live")
    assert res_live.status_code == 200
    assert res_live.json().get("status") == "alive"

    res_ready = client.get("/api/v1/health/ready")
    assert res_ready.status_code == 200
    assert res_ready.json().get("status") == "ready"


def test_api_invalid_uuid_format_handling(client: TestClient):
    """Ensure malformed UUID path parameters return 422 rather than 500."""
    _uid, headers = _register_user(client, "uuid_test@api.com")

    res = client.get("/api/v1/cases/not-a-valid-uuid", headers=headers)
    assert res.status_code == 422
    data = res.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_api_pagination_boundaries(client: TestClient):
    """Ensure limit and skip query parameters enforce schema validation."""
    _uid, headers = _register_user(client, "page_test@api.com")

    # Negative limit must be rejected by FastAPI schema validator (ge=1)
    res_neg = client.get("/api/v1/cases?limit=-5", headers=headers)
    assert res_neg.status_code == 422
    assert res_neg.json()["error"]["code"] == "VALIDATION_ERROR"

    # Limit > 100 must be rejected by FastAPI schema validator (le=100)
    res_over = client.get("/api/v1/cases?limit=500", headers=headers)
    assert res_over.status_code == 422
    assert res_over.json()["error"]["code"] == "VALIDATION_ERROR"

    # Valid pagination
    res_valid = client.get("/api/v1/cases?skip=0&limit=10", headers=headers)
    assert res_valid.status_code == 200
    assert res_valid.json()["limit"] == 10
