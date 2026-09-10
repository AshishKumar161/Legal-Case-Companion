import pytest

from app.core.config import Settings


def test_production_config_missing_secrets():
    # If we force environment=production but don't provide keys, it must raise a validation error
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            AWS_S3_BUCKET_NAME="",
            STRIPE_API_KEY=None,
            STRIPE_WEBHOOK_SECRET=None,
            OPENAI_API_KEY=None,
            EMAIL_PROVIDER="console",
            CSRF_SECRET_KEY="mock-secret-for-dev",
            DATABASE_URL="sqlite:///./test.db",
            JWT_PRIVATE_KEY="-" * 100,
            JWT_PUBLIC_KEY="-" * 50,
        )

    assert (
        "CSRF_SECRET_KEY must be a secure secret in production" in str(excinfo.value)
        or "AWS_S3_BUCKET_NAME is required in production" in str(excinfo.value)
        or "validation error" in str(excinfo.value).lower()
    )


def test_production_config_debug_is_forced_false():
    # Even if DEBUG=True is passed, it should be overridden or rejected
    # In our implementation, model_validator mode=after explicitly sets self.DEBUG = False

    # We need to bypass the secret requirements to test this specific logic
    settings = Settings(
        ENVIRONMENT="production",
        DEBUG=True,  # Attempting to enable debug in production
        AWS_S3_BUCKET_NAME="bucket",
        AWS_WEBHOOK_SECRET="secret",
        STRIPE_API_KEY="sk_test",
        STRIPE_WEBHOOK_SECRET="whsec",
        OPENAI_API_KEY="sk-proj",
        EMAIL_PROVIDER="ses",
        CSRF_SECRET_KEY="real_secret_that_is_at_least_32_chars_long_for_prod",
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/legal_db",
        REDIS_URL="redis://localhost:6379/0",
        JWT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n" + "-" * 100,
        JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n" + "-" * 50,
    )

    assert settings.DEBUG is False


def test_invalid_jwt_signature(client):
    response = client.get(
        "/api/v1/profiles/me", headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_refresh_token_replay(client):
    # This logic is already tested in test_auth.py: test_refresh_token_reuse_detection
    pass
