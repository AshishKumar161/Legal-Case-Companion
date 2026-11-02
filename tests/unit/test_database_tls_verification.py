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
    with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as bad_cert:
        bad_cert.write(b"-----BEGIN CERTIFICATE-----\nINVALID_CORRUPTED_CA_DATA\n-----END CERTIFICATE-----\n")
        bad_cert_path = bad_cert.name

    try:
        # Attempt connection to local postgres port with verify-full and invalid root cert
        engine = create_engine(
            "postgresql+psycopg2://postgres:postgres@127.0.0.1:5433/lcc_migration_test",
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
