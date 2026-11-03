import io
import logging
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.logging import JsonFormatter, SensitiveDataScrubberFilter
from app.core.security import create_access_token, hash_password
from app.main import app
from app.middleware.payload import RequestSizeLimitMiddleware
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole, ParticipantStatus
from app.models.user import AccountStatus, ClientProfile, User, UserRole


def test_trusted_host_middleware_enforcement():
    """Verify TrustedHostMiddleware prevents Host header injection and cache poisoning."""
    client = TestClient(app)

    # 1. Allowed host header (testserver is default TestClient host)
    res_valid = client.get("/api/v1/health/live", headers={"Host": "testserver"})
    assert res_valid.status_code == 200

    # 2. Spoofed host header outside ALLOWED_HOSTS
    res_spoofed = client.get("/api/v1/health/live", headers={"Host": "evil-attacker.com"})
    assert res_spoofed.status_code == 400
    assert "Invalid host header" in res_spoofed.text


def test_chunked_streaming_request_size_limit():
    """Verify RequestSizeLimitMiddleware protects against unbounded chunked streaming DoS."""
    mini_app = FastAPI()
    # Configure with small 1024 byte limit for testing
    mini_app.add_middleware(RequestSizeLimitMiddleware, max_upload_size=1024)

    @mini_app.post("/stream-endpoint")
    async def stream_endpoint():
        return {"status": "received"}

    client = TestClient(mini_app)

    # 1. Stream under limit
    def small_chunks():
        yield b"chunk1_"
        yield b"chunk2_"

    res_small = client.post("/stream-endpoint", content=small_chunks())
    assert res_small.status_code == 200

    # 2. Stream exceeding limit
    def large_chunks():
        for _ in range(20):
            yield b"X" * 100  # 2000 bytes > 1024

    res_large = client.post("/stream-endpoint", content=large_chunks())
    assert res_large.status_code == 413
    assert res_large.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_sensitive_data_scrubber_traceback_and_args():
    """Verify SensitiveDataScrubberFilter redacts secrets in args and tracebacks."""
    filter_instance = SensitiveDataScrubberFilter()
    logger = logging.getLogger("test_security_scrubber")
    logger.setLevel(logging.INFO)
    logger.addFilter(filter_instance)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    # 1. Test argument scrubbing
    logger.info(
        "User auth attempt with token: %s and aadhaar: %s",
        "eyJh.secret_jwt_token.signature",
        "9876 5432 1098",
    )

    output = stream.getvalue()
    assert "secret_jwt_token" not in output
    assert "9876 5432 1098" not in output
    assert "***REDACTED***" in output
    assert "***REDACTED-AADHAAR***" in output

    # 2. Test Exception traceback scrubbing
    stream.truncate(0)
    stream.seek(0)
    try:
        raise ValueError("Database connection failed with password=SuperSecretPassword123! and pan=ABCDE1234F")
    except ValueError:
        logger.exception("Error during execution")

    output_exc = stream.getvalue()
    assert "SuperSecretPassword123!" not in output_exc
    assert "ABCDE1234F" not in output_exc
    assert "***REDACTED***" in output_exc
    assert "***REDACTED-PAN***" in output_exc


def test_api_vs_docs_content_security_policy():
    """Verify strict CSP on APIs while permitting safe docs rendering."""
    client = TestClient(app)

    # 1. API endpoint receives strict lockdown CSP
    api_res = client.get("/api/v1/health/live")
    assert api_res.status_code == 200
    csp_api = api_res.headers.get("Content-Security-Policy", "")
    assert "default-src 'none'" in csp_api
    assert "frame-ancestors 'none'" in csp_api
    assert "sandbox" in csp_api

    # 2. Docs endpoint receives functional doc CSP without breaking Swagger UI
    docs_res = client.get("/api/v1/docs")
    assert docs_res.status_code == 200
    csp_docs = docs_res.headers.get("Content-Security-Policy", "")
    assert "https://cdn.jsdelivr.net" in csp_docs
    assert "default-src 'self'" in csp_docs


def test_evidence_pagination_bounds_and_validation(client: TestClient, db: Session):
    """Verify evidence listing enforces max page limits (le=100) and reject negative offsets."""
    from sqlalchemy.orm import Session as SessionType

    uid = uuid.uuid4().hex[:6]
    user = User(
        id=generate_uuid7(),
        email=f"client_paging_{uid}@example.com",
        password_hash=hash_password("SecurePassword123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()
    profile = ClientProfile(id=generate_uuid7(), user_id=user.id, full_name="Paging User")
    db.add(profile)

    case = Case(
        id=generate_uuid7(),
        title="Evidence Paging Case",
        description="Case for testing evidence pagination bounds",
        status=CaseStatus.OPEN,
    )
    db.add(case)
    db.flush()

    participant = CaseParticipant(
        id=generate_uuid7(),
        case_id=case.id,
        user_id=user.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(participant)
    db.commit()

    token = create_access_token(str(user.id), user.role.value)

    # 1. Valid pagination query (default)
    res_valid = client.get(
        f"/api/v1/cases/{case.id}/evidence?skip=0&limit=50",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_valid.status_code == 200
    assert isinstance(res_valid.json(), list)

    # 2. Exceeding max limit (101 > 100) -> 422 Unprocessable Entity
    res_excessive = client.get(
        f"/api/v1/cases/{case.id}/evidence?skip=0&limit=101",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_excessive.status_code == 422

    # 3. Negative skip offset (-1 < 0) -> 422 Unprocessable Entity
    res_neg_skip = client.get(
        f"/api/v1/cases/{case.id}/evidence?skip=-1&limit=50",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_neg_skip.status_code == 422


def test_frontend_next_config_csp_no_unsafe_eval():
    """Verify frontend next.config.ts production CSP excludes 'unsafe-eval'."""
    from pathlib import Path

    next_config_path = Path("frontend/next.config.ts")
    assert next_config_path.exists(), "frontend/next.config.ts must exist"
    content = next_config_path.read_text(encoding="utf-8")

    # In production branch, unsafe-eval must not be present
    assert "script-src 'self' 'unsafe-inline'" in content
    assert "'unsafe-eval'" not in content or "process.env.NODE_ENV !== \"production\"" in content


def test_auth_fail_closed_on_invalid_token():
    """Verify fail-closed behavior on corrupted/tampered JWT tokens."""
    client = TestClient(app)
    res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.tampered.token"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHENTICATED"


def test_environment_specific_allowed_hosts():
    """Verify environment-specific ALLOWED_HOSTS resolution without wildcards."""
    from app.core.config import Settings

    # 1. Production defaults: strictly explicit LCC production domains without wildcards
    prod_settings = Settings(
        ENVIRONMENT="production",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        JWT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMC4CAQAwBQYDK2VwBCIEIFfakekeyfakekeyfakekeyfakekeyfakekeyfakekey123456\n-----END PRIVATE KEY-----",
        JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAfakekeyfakekeyfakekeyfakekeyfakekeyfakekey123456\n-----END PUBLIC KEY-----",
        CSRF_SECRET_KEY="a" * 32,
        AWS_S3_BUCKET_NAME="lcc-bucket",
        AWS_WEBHOOK_SECRET="whsec_123",
        STRIPE_API_KEY="sk_live_123",
        STRIPE_WEBHOOK_SECRET="whsec_456",
        REDIS_URL="redis://localhost:6379",
        EMAIL_PROVIDER="smtp",
        SMTP_HOST="smtp.example.com",
    )
    assert prod_settings.ALLOWED_HOSTS == [
        "legalcasecompanion.in",
        "api.legalcasecompanion.in",
        "www.legalcasecompanion.in",
    ]
    assert "*.onrender.com" not in prod_settings.ALLOWED_HOSTS

    # 2. Production with explicit Render hostname (single specific hostname, no wildcard)
    render_settings = Settings(
        ENVIRONMENT="production",
        RENDER_EXTERNAL_HOSTNAME="lcc-backend.onrender.com",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        JWT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMC4CAQAwBQYDK2VwBCIEIFfakekeyfakekeyfakekeyfakekeyfakekeyfakekey123456\n-----END PRIVATE KEY-----",
        JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAfakekeyfakekeyfakekeyfakekeyfakekeyfakekey123456\n-----END PUBLIC KEY-----",
        CSRF_SECRET_KEY="a" * 32,
        AWS_S3_BUCKET_NAME="lcc-bucket",
        AWS_WEBHOOK_SECRET="whsec_123",
        STRIPE_API_KEY="sk_live_123",
        STRIPE_WEBHOOK_SECRET="whsec_456",
        REDIS_URL="redis://localhost:6379",
        EMAIL_PROVIDER="smtp",
        SMTP_HOST="smtp.example.com",
    )
    assert "lcc-backend.onrender.com" in render_settings.ALLOWED_HOSTS
    assert "*.onrender.com" not in render_settings.ALLOWED_HOSTS

    # 3. Development / Test defaults
    dev_settings = Settings(ENVIRONMENT="development")
    assert dev_settings.ALLOWED_HOSTS == ["localhost", "127.0.0.1", "testserver"]


def test_production_database_ssl_configuration():
    """Verify production rejects sslmode=disable."""
    from app.core.config import Settings

    with pytest.raises(ValueError, match="DATABASE_URL must not disable SSL"):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql://user:pass@localhost:5432/db?sslmode=disable",
            JWT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMC4CAQAwBQYDK2VwBCIEIFfakekeyfakekeyfakekeyfakekeyfakekeyfakekey123456\n-----END PRIVATE KEY-----",
            JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAfakekeyfakekeyfakekeyfakekeyfakekeyfakekey123456\n-----END PUBLIC KEY-----",
            CSRF_SECRET_KEY="a" * 32,
            AWS_S3_BUCKET_NAME="lcc-bucket",
            AWS_WEBHOOK_SECRET="whsec_123",
            STRIPE_API_KEY="sk_live_123",
            STRIPE_WEBHOOK_SECRET="whsec_456",
            REDIS_URL="redis://localhost:6379",
            EMAIL_PROVIDER="smtp",
            SMTP_HOST="smtp.example.com",
        )


def test_full_authentication_lifecycle_and_multitab(client: TestClient, db: Session):
    """Verify complete authentication lifecycle: login, expired token rejection, CSRF validation,

    refresh rotation, replay family revocation, and logout.
    """
    from datetime import UTC, datetime, timedelta
    import jwt
    from app.core.config import settings

    uid = uuid.uuid4().hex[:6]
    email = f"auth_lifecycle_{uid}@example.com"
    pwd = "SecureLifecyclePass123!"

    # 1. Register & Login
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pwd, "role": "CLIENT", "full_name": "Auth Lifecycle User"},
    )
    assert reg_res.status_code == 201

    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert login_res.status_code == 200
    login_data = login_res.json()
    access_token1 = login_data["access_token"]
    refresh_token1 = login_res.cookies.get("refresh_token")
    csrf_token1 = login_res.cookies.get("csrf_token")
    assert access_token1 and refresh_token1 and csrf_token1

    # 2. Expired access token rejection
    expired_token = jwt.encode(
        {
            "sub": str(reg_res.json()["id"]),
            "iss": "legal-case-companion",
            "aud": "legal-case-companion",
            "role": "CLIENT",
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(minutes=5),
        },
        key=settings.JWT_PRIVATE_KEY,
        algorithm=settings.ALGORITHM,
    )
    expired_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert expired_res.status_code == 401
    assert expired_res.json()["error"]["code"] == "UNAUTHENTICATED"

    # 3. Refresh without CSRF header -> fails
    res_no_csrf = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token1, "csrf_token": csrf_token1},
    )
    assert res_no_csrf.status_code == 401

    # 4. Refresh with mismatched CSRF header -> fails
    res_bad_csrf = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": "invalid-mismatched-csrf-token"},
        cookies={"refresh_token": refresh_token1, "csrf_token": csrf_token1},
    )
    assert res_bad_csrf.status_code == 401

    # 5. Valid refresh with CSRF -> rotation succeeds
    res_ref1 = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token1},
        cookies={"refresh_token": refresh_token1, "csrf_token": csrf_token1},
    )
    assert res_ref1.status_code == 200
    access_token2 = res_ref1.json()["access_token"]
    refresh_token2 = res_ref1.cookies.get("refresh_token")
    csrf_token2 = res_ref1.cookies.get("csrf_token")
    assert refresh_token2 != refresh_token1

    # 6. Replayed old refresh token -> fails and revokes family
    client.cookies.clear()
    replay_res = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token1},
        cookies={"refresh_token": refresh_token1, "csrf_token": csrf_token1},
    )
    assert replay_res.status_code == 401

    # 7. Use active refresh_token2 after replay -> fails due to family revocation
    client.cookies.clear()
    victim_res = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token2},
        cookies={"refresh_token": refresh_token2, "csrf_token": csrf_token2},
    )
    assert victim_res.status_code == 401

    # 8. Re-login and logout clears session and cookies
    login_res2 = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert login_res2.status_code == 200
    acc_tok = login_res2.json()["access_token"]
    ref_tok = login_res2.cookies.get("refresh_token")

    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {acc_tok}"},
        cookies={"refresh_token": ref_tok},
    )
    assert logout_res.status_code == 200


def test_evidence_duplicate_detection(client: TestClient, db: Session):
    """Verify Evidence Locker detects duplicate files within case scope and logs advisory custody event."""
    from app.core.storage import get_storage_provider

    uid = uuid.uuid4().hex[:6]
    user = User(
        id=generate_uuid7(),
        email=f"dup_user_{uid}@example.com",
        password_hash=hash_password("SecurePass123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()
    profile = ClientProfile(id=generate_uuid7(), user_id=user.id, full_name="Dup User")
    db.add(profile)

    case = Case(
        id=generate_uuid7(),
        title="Duplicate Detection Case",
        description="Testing duplicate detection",
        status=CaseStatus.OPEN,
    )
    db.add(case)
    db.flush()

    participant = CaseParticipant(
        id=generate_uuid7(),
        case_id=case.id,
        user_id=user.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(participant)
    db.commit()

    token = create_access_token(str(user.id), user.role.value)
    storage = get_storage_provider()

    file_content = b"%PDF-1.5\nDuplicate contract copy\n%%EOF"

    # Upload 1
    init1 = client.post(
        f"/api/v1/cases/{case.id}/evidence/upload-init",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Contract Copy 1",
            "category": "CONTRACTUAL",
            "sensitivity": "STANDARD",
            "original_filename": "contract_orig.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(file_content),
        },
    ).json()
    storage.put_object_bytes(init1["storage_key"], file_content, mime_type="application/pdf")
    client.post(
        f"/api/v1/cases/{case.id}/evidence/{init1['evidence_id']}/complete",
        headers={"Authorization": f"Bearer {token}"},
        json={"version_id": init1["version_id"]},
    )

    # Upload 2 with identical content in same case
    init2 = client.post(
        f"/api/v1/cases/{case.id}/evidence/upload-init",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Contract Copy 2 (Duplicate)",
            "category": "CONTRACTUAL",
            "sensitivity": "STANDARD",
            "original_filename": "contract_copy.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(file_content),
        },
    ).json()
    storage.put_object_bytes(init2["storage_key"], file_content, mime_type="application/pdf")
    comp2 = client.post(
        f"/api/v1/cases/{case.id}/evidence/{init2['evidence_id']}/complete",
        headers={"Authorization": f"Bearer {token}"},
        json={"version_id": init2["version_id"]},
    )
    assert comp2.status_code == 200
    assert comp2.json()["status"] == "ACTIVE"

    # Custody log indicates duplicate was detected
    custody = client.get(
        f"/api/v1/cases/{case.id}/evidence/{init2['evidence_id']}/custody",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    scan_passed = [evt for evt in custody if evt["action"] == "SCAN_PASSED"][0]
    meta = scan_passed.get("metadata") or scan_passed.get("event_metadata") or {}
    assert meta.get("duplicate_detected") is True
    assert meta.get("duplicate_of_evidence_id") == init1["evidence_id"]
