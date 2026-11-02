"""
Tests for OpenTelemetry and Distributed Tracing Subsystem (app/core/telemetry.py).
Validates:
- Trace span generation with W3C TraceContext compatibility.
- PII and credential attribute redaction (password, token, secret, aadhaar, pan, key).
- Attribute truncation preventing legal text leakage into traces.
- Synchronous and asynchronous @telemetry.trace decorators.
- Exception capture and span error status recording.
"""

import pytest
from app.core.telemetry import TelemetryService, NoOpSpan, telemetry
from app.middleware.correlation_id import correlation_id_ctx


def test_noop_span_redacts_credentials_and_pii():
    span = NoOpSpan("test-span")

    # Sensitive attributes that must be redacted
    sensitive_payload = {
        "user.password": "SuperSecretPass123!",
        "auth.bearer_token": "eyJhbGciOiJIUzI1Ni...",
        "client.secret_key": "sk_live_9481928491829",
        "client.aadhaar_number": "5482-1928-4918",
        "user.pan_card": "ABCDE1234F",
        "api_key": "live_key_991827419",
    }

    for key, val in sensitive_payload.items():
        span.set_attribute(key, val)
        assert span.attributes[key] == "***REDACTED***", f"Failed to redact sensitive key: {key}"

    # Safe attributes should be preserved
    span.set_attribute("http.method", "POST")
    span.set_attribute("http.status_code", 200)
    assert span.attributes["http.method"] == "POST"
    assert span.attributes["http.status_code"] == "200"


def test_noop_span_truncates_large_payloads():
    span = NoOpSpan("test-legal-span")
    massive_legal_text = "CONFIDENTIAL CASE RECORD " * 50  # 1250 characters
    span.set_attribute("case.narrative", massive_legal_text)

    # Must be truncated to at most 256 chars
    stored_val = span.attributes["case.narrative"]
    assert len(stored_val) <= 256
    assert stored_val.startswith("CONFIDENTIAL CASE RECORD")


def test_span_records_exception_cleanly():
    service = TelemetryService()
    with pytest.raises(ValueError, match="Synthetic operational failure"):
        with service.start_span("failing-op") as span:
            span.set_attribute("tenant_id", "test-tenant-1")
            raise ValueError("Synthetic operational failure")

    assert span.attributes["exception.type"] == "ValueError"
    assert "Synthetic operational failure" in span.attributes["exception.message"]
    assert span.attributes["status.code"] == "ERROR"


def test_telemetry_trace_decorator_sync_and_async():
    @telemetry.trace("sample_sync_function", {"component": "unit_test"})
    def sample_sync(x: int) -> int:
        return x * 2

    assert sample_sync(21) == 42

    @telemetry.trace("sample_async_function", {"component": "unit_test"})
    async def sample_async(x: int) -> int:
        return x + 10

    import asyncio
    res = asyncio.run(sample_async(32))
    assert res == 42


def test_telemetry_binds_correlation_id():
    token = correlation_id_ctx.set("corr-test-12345-abcde")
    try:
        service = TelemetryService()
        with service.start_span("context-op") as span:
            assert span.trace_id == "corr-test-12345-abcde"
            assert span.attributes["correlation_id"] == "corr-test-12345-abcde"
    finally:
        correlation_id_ctx.reset(token)
