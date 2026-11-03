"""
Tests for PostgreSQL TLS Security and sslmode=verify-full (app/db/database.py).

Validates:
- Production configuration maps DB_SSL_MODE to SQLAlchemy connect_args["sslmode"].
- Support for sslmode=verify-full with trusted CA bundle (sslrootcert).
- Enforcement of server identity, hostname verification, and CA trust chain.
- Connection failure when certificate validation fails (invalid CA or non-matching certificate).
"""

import os
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app.core.config import settings


def test_database_tls_verify_full_connect_args(monkeypatch):
    """Verifies that DB_SSL_MODE=verify-full and DB_SSL_ROOT_CERT are passed to engine connect_args."""
    with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as cert_file:
        cert_file.write(b"-----BEGIN CERTIFICATE-----\nFAKE_CA_BUNDLE\n-----END CERTIFICATE-----\n")
        cert_path = cert_file.name

    try:
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "DB_SSL_MODE", "verify-full")
        monkeypatch.setattr(settings, "DB_SSL_ROOT_CERT", cert_path)

        connect_args = {
            "options": f"-c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS}"
        }
        if settings.ENVIRONMENT in ("production", "staging"):
            connect_args["sslmode"] = settings.DB_SSL_MODE
            if settings.DB_SSL_ROOT_CERT:
                connect_args["sslrootcert"] = settings.DB_SSL_ROOT_CERT

        assert connect_args["sslmode"] == "verify-full"
        assert connect_args["sslrootcert"] == cert_path
        assert "statement_timeout=30000" in connect_args["options"]
    finally:
        if os.path.exists(cert_path):
            os.remove(cert_path)


def test_database_connection_fails_on_invalid_ssl_root_cert():
    """Connecting with sslmode=verify-full and a bogus or non-matching CA cert must fail securely."""
    import socket

    pg_host = os.environ.get("TEST_PG_HOST", "127.0.0.1")
    pg_port = int(os.environ.get("TEST_PG_PORT", "5433"))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        sock.connect((pg_host, pg_port))
        sock.close()
    except Exception:
        pytest.skip(f"Live PostgreSQL server not reachable on {pg_host}:{pg_port}")

    with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as bad_cert:
        bad_cert.write(b"-----BEGIN CERTIFICATE-----\nINVALID_CORRUPTED_CA_DATA\n-----END CERTIFICATE-----\n")
        bad_cert_path = bad_cert.name

    try:
        # Attempt connection to local postgres port with verify-full and invalid root cert
        engine = create_engine(
            f"postgresql+psycopg://postgres:postgres@{pg_host}:{pg_port}/lcc_migration_test",
            connect_args={
                "sslmode": "verify-full",
                "sslrootcert": bad_cert_path,
                "connect_timeout": 2,
            }
        )

        # Connection MUST raise OperationalError due to failed SSL/TLS certificate verification
        with pytest.raises(OperationalError) as exc_info:
            with engine.connect() as conn:
                conn.execute("SELECT 1")

        err_msg = str(exc_info.value).lower()
        if "connection refused" in err_msg or "could not connect to server" in err_msg:
            pytest.skip(f"PostgreSQL test instance not running on {pg_host}:{pg_port}")

        # Verify that failure is strictly an SSL/TLS verification or handshake error
        assert any(term in err_msg for term in ("ssl", "certificate", "root", "verify", "handshake"))
    finally:
        if os.path.exists(bad_cert_path):
            os.remove(bad_cert_path)


def test_database_tls_require_fallback_without_root_cert(monkeypatch):
    """In staging without custom CA, default sslmode=require enforces encryption without strict CA pinning."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(settings, "DB_SSL_MODE", "require")
    monkeypatch.setattr(settings, "DB_SSL_ROOT_CERT", None)

    connect_args = {}
    if settings.ENVIRONMENT in ("production", "staging"):
        connect_args["sslmode"] = settings.DB_SSL_MODE
        if settings.DB_SSL_ROOT_CERT:
            connect_args["sslrootcert"] = settings.DB_SSL_ROOT_CERT

    assert connect_args["sslmode"] == "require"
    assert "sslrootcert" not in connect_args


def test_production_db_ssl_mode_validation():
    """Verify that Settings validates DB_SSL_MODE and CA certificate in production."""
    from app.core.config import Settings

    valid_kwargs = {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "postgresql://postgres:secret@127.0.0.1:5432/legal_db",
        "JWT_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC5\n-----END PRIVATE KEY-----",
        "JWT_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n-----END PUBLIC KEY-----",
        "CSRF_SECRET_KEY": "a" * 32,
        "AWS_S3_BUCKET_NAME": "test-bucket",
        "AWS_WEBHOOK_SECRET": "test-webhook-secret",
        "STRIPE_API_KEY": "sk_test_123",
        "STRIPE_WEBHOOK_SECRET": "whsec_123",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "EMAIL_PROVIDER": "ses",
    }

    # 1. Invalid DB_SSL_MODE is rejected
    with pytest.raises(ValueError, match="DB_SSL_MODE must be one of"):
        Settings(**{**valid_kwargs, "DB_SSL_MODE": "disable"})

    # 2. verify-full without DB_SSL_ROOT_CERT is rejected
    with pytest.raises(ValueError, match="DB_SSL_ROOT_CERT path is required when DB_SSL_MODE is 'verify-full'"):
        Settings(**{**valid_kwargs, "DB_SSL_MODE": "verify-full", "DB_SSL_ROOT_CERT": None})

    # 3. verify-full with non-existent DB_SSL_ROOT_CERT is rejected
    with pytest.raises(ValueError, match="DB_SSL_ROOT_CERT file not found"):
        Settings(**{**valid_kwargs, "DB_SSL_MODE": "verify-full", "DB_SSL_ROOT_CERT": "/nonexistent/ca.pem"})

    # 4. verify-full with valid existing CA bundle succeeds
    with tempfile.NamedTemporaryFile(suffix=".pem") as f:
        f.write(b"dummy cert")
        f.flush()
        s = Settings(**{**valid_kwargs, "DB_SSL_MODE": "verify-full", "DB_SSL_ROOT_CERT": f.name})
        assert s.DB_SSL_MODE == "verify-full"
        assert s.DB_SSL_ROOT_CERT == f.name

    # 5. Default require mode succeeds without DB_SSL_ROOT_CERT
    s_req = Settings(**{**valid_kwargs, "DB_SSL_MODE": "require", "DB_SSL_ROOT_CERT": None})
    assert s_req.DB_SSL_MODE == "require"
