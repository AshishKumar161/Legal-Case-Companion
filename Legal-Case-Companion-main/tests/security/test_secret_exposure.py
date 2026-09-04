import logging

from app.core.logging import SensitiveDataScrubberFilter
from app.schemas.user import UserResponse


def test_user_response_schema_excludes_sensitive_fields():
    """Verify that UserResponse Pydantic schema strictly omits password_hash and secrets."""
    schema = UserResponse.model_json_schema()
    properties = schema.get("properties", {})

    # Critical sensitive fields must NEVER be in UserResponse schema
    assert "password_hash" not in properties
    assert "password" not in properties
    assert "token" not in properties
    assert "secret" not in properties


def test_log_scrubber_redacts_credentials_and_tokens():
    """Verify that SensitiveDataScrubberFilter scrubs passwords, tokens, and signed URLs from log records."""
    scrubber = SensitiveDataScrubberFilter()

    # Create dummy LogRecord
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Login failed for user with password='SuperSecretPassword123!' and token=dG9rZW5fdmFsdWVfc2FtcGxl",
        args=(),
        exc_info=None,
    )

    scrubber.filter(record)
    scrubbed = record.getMessage()

    assert "SuperSecretPassword123!" not in scrubbed
    assert "***REDACTED***" in scrubbed


def test_log_scrubber_redacts_bearer_and_presigned_urls():
    """Verify that Bearer tokens and S3 presigned signature parameters are scrubbed."""
    scrubber = SensitiveDataScrubberFilter()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=100,
        msg="Request with Authorization: Bearer eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.e30.signature and url=https://s3.amazonaws.com/bucket/doc.pdf?X-Amz-Signature=abcdef1234567890",
        args=(),
        exc_info=None,
    )

    scrubber.filter(record)
    scrubbed = record.getMessage()

    assert "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9" not in scrubbed
    assert "abcdef1234567890" not in scrubbed
    assert "***REDACTED***" in scrubbed
