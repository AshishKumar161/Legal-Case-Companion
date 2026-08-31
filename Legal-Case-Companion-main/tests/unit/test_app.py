from unittest.mock import patch

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    # Verify correlation ID is injected
    assert "X-Request-ID" in response.headers


def test_correlation_id_propagation(client: TestClient) -> None:
    test_id = "test-request-123"
    response = client.get("/api/v1/health/live", headers={"X-Request-ID": test_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == test_id


@patch("sqlalchemy.orm.Session.execute")
def test_readiness_check_success(mock_execute, client: TestClient) -> None:
    # Mocks a successful DB connection
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}


@patch("sqlalchemy.orm.Session.execute")
def test_readiness_check_failure(mock_execute, client: TestClient) -> None:
    # Mocks a DB connection failure
    mock_execute.side_effect = Exception("DB Down")
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_standardized_error_response(client: TestClient) -> None:
    # Test triggering a 404 to see standard FastAPI errors
    response = client.get("/non-existent-route")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_ERROR"
    assert data["error"]["request_id"] == response.headers["X-Request-ID"]
    assert data["error"]["request_id"] != "-"


def test_correlation_id_propagated_to_error_body(client: TestClient) -> None:
    custom_id = "custom-err-uuid-999"
    response = client.get("/non-existent-route", headers={"X-Request-ID": custom_id})
    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == custom_id
    assert response.json()["error"]["request_id"] == custom_id


def test_correlation_id_filter_log_record() -> None:
    import logging

    from app.core.logging import CorrelationIdFilter
    from app.middleware.correlation_id import correlation_id_ctx

    token = correlation_id_ctx.set("log-test-id-123")
    try:
        filt = CorrelationIdFilter()
        record = logging.LogRecord("test", logging.INFO, "path", 1, "msg", (), None)
        assert filt.filter(record) is True
        assert record.correlation_id == "log-test-id-123"
    finally:
        correlation_id_ctx.reset(token)
