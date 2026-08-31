from fastapi.testclient import TestClient


def test_security_headers(client: TestClient):
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert (
        response.headers.get("Strict-Transport-Security")
        == "max-age=31536000; includeSubDomains"
    )
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "default-src 'none'" in response.headers.get("Content-Security-Policy")


def test_payload_too_large(client: TestClient):
    # Payload > 5MB
    large_payload = "{" + '"data": "' + "x" * (6 * 1024 * 1024) + '"}'
    # Use content= for raw bytes instead of data=
    response = client.post(
        "/api/v1/auth/login",
        content=large_payload,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
