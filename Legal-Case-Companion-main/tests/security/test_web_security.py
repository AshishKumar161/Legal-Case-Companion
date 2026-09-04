from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_production_security_headers():
    """Verify that all hardened production security headers are set on HTTP responses."""
    client = TestClient(app)
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200

    headers = response.headers

    # HSTS Preload
    assert "Strict-Transport-Security" in headers
    assert "preload" in headers["Strict-Transport-Security"]
    assert "includeSubDomains" in headers["Strict-Transport-Security"]

    # MIME type sniffing
    assert headers.get("X-Content-Type-Options") == "nosniff"

    # Clickjacking & Framing
    assert headers.get("X-Frame-Options") == "DENY"

    # Strict API Content Security Policy
    assert "default-src 'none'" in headers.get("Content-Security-Policy", "")
    assert "frame-ancestors 'none'" in headers.get("Content-Security-Policy", "")

    # Referrer Policy
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    # Cross-Origin Isolation
    assert headers.get("Cross-Origin-Opener-Policy") == "same-origin"
    assert headers.get("Cross-Origin-Resource-Policy") == "same-site"

    # Permissions Policy
    assert "geolocation=()" in headers.get("Permissions-Policy", "")


def test_csrf_double_submit_protection():
    """Verify double-submit cookie CSRF validation on refresh endpoint."""
    client = TestClient(app)

    # 1. Missing CSRF header and cookie -> fails
    res1 = client.post("/api/v1/auth/refresh")
    assert res1.status_code == 401

    # 2. Cookie present, header missing -> fails
    client.cookies.set("csrf_token", "token_value_abc123")
    res2 = client.post("/api/v1/auth/refresh")
    assert res2.status_code == 401

    # 3. Cookie and header mismatch -> fails
    res3 = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": "different_token_xyz987"},
    )
    assert res3.status_code == 401


def test_cors_configuration_boundaries(monkeypatch):
    """Verify CORS origins are restricted and do not allow wildcards with credentials."""
    # Ensure BACKEND_CORS_ORIGINS does not contain wildcard in any config
    origins = [str(o) for o in settings.BACKEND_CORS_ORIGINS]
    assert "*" not in origins

    client = TestClient(app)

    # Allowed origin preflight
    res_allowed = client.options(
        "/api/v1/health/live",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"

    # Disallowed origin preflight
    res_disallowed = client.options(
        "/api/v1/health/live",
        headers={
            "Origin": "https://malicious-attacker-site.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_disallowed.headers.get("access-control-allow-origin") is None
