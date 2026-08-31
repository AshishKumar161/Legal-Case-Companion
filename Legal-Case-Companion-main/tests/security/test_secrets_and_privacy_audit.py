from fastapi.testclient import TestClient


def test_security_headers_and_error_privacy(client: TestClient):
    """Red Team: Validates that security headers are enforced and standard error envelopes do not leak server internals or stack traces."""
    # 1. Health check headers
    res = client.get("/health")
    assert res.status_code == 200
    headers = {k.lower(): v for k, v in res.headers.items()}
    assert "x-content-type-options" in headers
    assert headers["x-content-type-options"] == "nosniff"
    assert "x-frame-options" in headers
    assert headers["x-frame-options"] == "DENY"

    # 2. 404 Not Found error envelope privacy
    err_res = client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000")
    assert err_res.status_code in [401, 404]
    err_json = err_res.json()
    # Ensure error response has structured format and no Python traceback
    err_str = str(err_json).lower()
    assert "traceback" not in err_str
    assert "file \"" not in err_str
    assert "line " not in err_str

    # 3. 422 Unprocessable Content error envelope privacy
    val_res = client.post("/api/v1/auth/login", json={"malformed": 123})
    assert val_res.status_code == 422
    val_str = str(val_res.json()).lower()
    assert "traceback" not in val_str
    assert "password_hash" not in val_str
