import os

# Force test environment so AI provider factory returns mock instead of making real API calls.
os.environ["ENVIRONMENT"] = "test"

if not os.environ.get("JWT_PRIVATE_KEY") or not os.environ.get("JWT_PUBLIC_KEY"):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    _test_k = Ed25519PrivateKey.generate()
    os.environ.setdefault(
        "JWT_PRIVATE_KEY",
        _test_k.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
    )
    os.environ.setdefault(
        "JWT_PUBLIC_KEY",
        _test_k.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode(),
    )
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

os.environ["EMAIL_PROVIDER"] = "console"
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_secret_123")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

settings.STRIPE_WEBHOOK_SECRET = "whsec_test_secret_123"

# Use PostgreSQL for integration tests as requested
from app.db.database import get_db
from app.main import app
from app.models import Base

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test_pytest.db")

connect_args = (
    {"check_same_thread": False, "timeout": 60}
    if TEST_DB_URL.startswith("sqlite")
    else {}
)
test_engine = create_engine(TEST_DB_URL, connect_args=connect_args)


# Enable WAL mode, busy timeout, and foreign keys for SQLite
@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if TEST_DB_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.close()





TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session")
def db_engine():
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    try:
        if os.path.exists("./test_pytest.db"):
            os.remove("./test_pytest.db")
        for extra in ["./test_pytest.db-wal", "./test_pytest.db-shm"]:
            if os.path.exists(extra):
                os.remove(extra)
    except PermissionError:
        pass


@pytest.fixture(scope="function")
def db(db_engine):
    # Truncate tables for clean state
    from sqlalchemy import text
    session = TestingSessionLocal()
    if TEST_DB_URL.startswith("sqlite"):
        session.execute(text("PRAGMA foreign_keys = OFF"))
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    if TEST_DB_URL.startswith("sqlite"):
        session.execute(text("PRAGMA foreign_keys = ON"))
    session.commit()

    yield session
    session.close()


from collections.abc import Generator


@pytest.fixture(scope="function")
def client(db) -> Generator[TestClient, None, None]:
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# Disable rate limiting during tests
app.state.limiter.enabled = False
