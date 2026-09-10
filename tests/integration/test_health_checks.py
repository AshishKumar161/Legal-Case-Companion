from fastapi.testclient import TestClient


class TestHealthChecks:
    """Verifies liveness, readiness, and deep dependency health check endpoints."""

    def test_liveness_check(self, client: TestClient):
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "service" in data

    def test_root_liveness_check(self, client: TestClient):
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_readiness_check(self, client: TestClient):
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"

    def test_root_readiness_check(self, client: TestClient):
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_dependency_health_details(self, client: TestClient):
        response = client.get("/api/v1/health/details")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        deps = data["dependencies"]
        assert "database" in deps
        assert deps["database"]["status"] == "connected"
        assert "redis" in deps
        assert "storage" in deps
        assert "scanner" in deps
        assert "queues" in deps

    def test_health_details_zero_secret_leakage(self, client: TestClient):
        response = client.get("/api/v1/health/details")
        raw_text = response.text.lower()
        forbidden_substrings = [
            "password",
            "postgres:",
            "redis://:",
            "secret",
            "aws_secret",
            "bearer",
            "private_key",
        ]
        for forbidden in forbidden_substrings:
            assert forbidden not in raw_text, f"Potential secret leak in /health/details: '{forbidden}' found"
