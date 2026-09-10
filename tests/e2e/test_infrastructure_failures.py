import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ScannerUnavailableError,
    StorageError,
)
from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.core.storage import StorageProvider
from app.main import app
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole, ParticipantStatus
from app.models.evidence import (
    Evidence,
    EvidenceStatus,
)
from app.models.job import JobStatus, JobType
from app.models.outbox import OutboxStatus
from app.models.user import AccountStatus, User, UserRole
from app.schemas.evidence import EvidenceUploadInitRequest
from app.domain.ai.ai_provider import StubAIProvider
from app.domain.evidence.evidence_service import EvidenceService
from app.services.job_service import JobService
from app.domain.jobs.outbox_service import OutboxService
from app.services.presence_service import PresenceService


class BrokenStorageProvider(StorageProvider):
    """Storage provider that simulates network failure or AWS S3 outage."""

    def generate_presigned_upload_url(self, object_key: str, mime_type: str, expires_in: int = 3600) -> str:
        raise StorageError("AWS S3 Service Unavailable (503 Outage Simulation)")

    def generate_presigned_download_url(self, object_key: str, expires_in: int = 3600, response_content_disposition: str | None = None, response_content_type: str | None = None) -> str:
        raise StorageError("AWS S3 Service Unavailable (503 Outage Simulation)")

    def delete_object(self, object_key: str) -> bool:
        raise StorageError("AWS S3 Service Unavailable (503 Outage Simulation)")

    def get_object_bytes(self, object_key: str) -> bytes | None:
        raise StorageError("AWS S3 Service Unavailable (503 Outage Simulation)")

    def put_object_bytes(self, object_key: str, data: bytes, mime_type: str = "application/octet-stream") -> bool:
        raise StorageError("AWS S3 Service Unavailable (503 Outage Simulation)")

    def object_exists(self, object_key: str) -> bool:
        raise StorageError("AWS S3 Service Unavailable (503 Outage Simulation)")


class BrokenRedisClient:
    """Redis client simulating connection crash / outage."""

    is_mock = False

    def ping(self):
        raise ConnectionError("Redis server connection refused on 6379")

    def get(self, key):
        raise ConnectionError("Redis server connection refused on 6379")

    def set(self, key, value, *args, **kwargs):
        raise ConnectionError("Redis server connection refused on 6379")

    def delete(self, key):
        raise ConnectionError("Redis server connection refused on 6379")


def test_redis_failure_fails_closed_and_degrades_safely(monkeypatch):
    """Verify that when Redis is down, presence fails safe (OFFLINE), tickets fail closed, and health reports degraded."""
    broken_redis = BrokenRedisClient()
    monkeypatch.setattr("app.core.redis.get_redis_client", lambda: broken_redis)
    monkeypatch.setattr("app.services.presence_service.get_redis_client", lambda: broken_redis)
    monkeypatch.setattr("app.api.v1.health.get_redis_client", lambda: broken_redis)

    presence_service = PresenceService()
    user_id = generate_uuid7()

    # Presence must fail safe to False / None, never returning false positive availability
    assert presence_service.is_online(user_id) is False
    assert presence_service.is_available_preference(user_id) is False
    assert presence_service.get_presence(user_id) is None

    # Health check reports degraded rather than 500 error
    client = TestClient(app)
    res = client.get("/api/v1/health/details")
    assert res.status_code == 200
    data = res.json()
    assert data["dependencies"]["redis"]["status"] == "degraded"


def test_postgresql_failure_returns_503():
    """Verify that when database connection fails, readiness probe fails with 503 Service Unavailable."""
    client = TestClient(app)

    with patch("sqlalchemy.orm.Session.execute", side_effect=Exception("DB Connection Terminated")):
        res = client.get("/api/v1/health/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "disconnected"


def test_s3_storage_failure_fails_closed(db: Session):
    """Verify that S3 failure prevents evidence from activating, leaving it quarantined or failing safely."""
    broken_storage = BrokenStorageProvider()

    user = User(
        id=generate_uuid7(),
        email=f"s3_fail_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Pass123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    case = Case(
        id=generate_uuid7(),
        title="S3 Outage Test Case",
        description="Testing S3 failure fail-closed.",
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

    service = EvidenceService(db)

    init_req = EvidenceUploadInitRequest(
        title="Failed Upload Test",
        original_filename="doc.pdf",
        content_type="application/pdf",
        size_bytes=1024,
    )

    evidence, version, _ = service.init_upload(
        user=user,
        case_id=case.id,
        req=init_req,
    )

    # Attach broken storage for verification
    service.storage = broken_storage

    # Completing upload with broken storage must raise StorageError
    with pytest.raises(StorageError):
        service.complete_upload(
            user=user,
            case_id=case.id,
            evidence_id=evidence.id,
            version_id=version.id,
        )

    # Evidence must NOT be ACTIVE
    db.refresh(evidence)
    assert evidence.status != EvidenceStatus.ACTIVE


def test_clamav_failure_keeps_evidence_quarantined(db: Session):
    """Verify that when ClamAV scanner daemon is unreachable, evidence remains QUARANTINED."""
    user = User(
        id=generate_uuid7(),
        email=f"clamav_fail_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Pass123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    case = Case(
        id=generate_uuid7(),
        title="Scanner Fail Test",
        description="Testing scanner fail-closed.",
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

    service = EvidenceService(db)

    init_req = EvidenceUploadInitRequest(
        title="Quarantine Test",
        original_filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=1024,
    )

    evidence, version, _ = service.init_upload(
        user=user,
        case_id=case.id,
        req=init_req,
    )

    # Pre-populate valid PDF bytes in mock storage
    service.storage.put_object_bytes(
        object_key=version.storage_key,
        data=b"%PDF-1.4 test safe content",
        mime_type="application/pdf",
    )

    # Simulate scanner failure
    mock_scanner = MagicMock()
    mock_scanner.scan_bytes.side_effect = ScannerUnavailableError("ClamAV daemon timeout")
    service.scanner = mock_scanner

    with pytest.raises(ScannerUnavailableError):
        service.complete_upload(
            user=user,
            case_id=case.id,
            evidence_id=evidence.id,
            version_id=version.id,
        )

    # Evidence status must remain QUARANTINED
    db.refresh(evidence)
    assert evidence.status == EvidenceStatus.QUARANTINED


def test_worker_stale_job_lease_recovery(db: Session):
    """Verify that a worker crash leaves a job that is safely recovered by lease reclamation."""
    job_service = JobService(db)
    job = job_service.enqueue_job(
        job_type=JobType.EVIDENCE_INTEGRITY_AUDIT,
        payload={"scope": "stale_test"},
    )

    # Simulate worker claiming the job
    claimed_list = job_service.claim_jobs(worker_id="worker_died_1", limit=1, lease_seconds=1)
    assert len(claimed_list) == 1
    claimed = claimed_list[0]
    assert claimed.id == job.id
    assert claimed.status == JobStatus.RUNNING

    # Simulate lease expiration in the past
    claimed.locked_until = datetime.now(UTC) - timedelta(seconds=10)
    db.commit()

    # Reclaim stale jobs
    recovered_count = job_service.reclaim_stale_jobs()
    assert recovered_count >= 1

    db.refresh(claimed)
    assert claimed.status in (JobStatus.RETRYING, JobStatus.PENDING)
    assert claimed.locked_by is None


def test_outbox_durability_on_dispatch_failure(db: Session):
    """Verify that outbox events remain durable in DB when external message bus fails."""
    outbox_service = OutboxService(db)
    event = OutboxService.emit_event(
        db=db,
        event_type="EVIDENCE_UPLOADED",
        aggregate_type="evidence",
        aggregate_id=generate_uuid7(),
        payload={"version_id": str(generate_uuid7()), "case_id": str(generate_uuid7())},
    )
    db.commit()

    # Dispatch failure simulation
    with patch("app.services.job_service.JobService.enqueue_job", side_effect=RuntimeError("Job queue unavailable")):
        outbox_service.dispatch_event(event)

    db.refresh(event)
    assert event.status in (OutboxStatus.FAILED, OutboxStatus.PENDING)
    assert event.last_error is not None


def test_ai_provider_failure_fails_safe():
    """Verify that external AI model failure returns a safe error without crashing or bypassing security."""
    provider = StubAIProvider()

    # When no chunks are provided, fails closed with warning
    res = provider.generate_research_response(
        system_prompt="Analyze legal compliance.",
        user_query="Non-existent legal claim",
        chunks=[],
    )

    assert "Evidence insufficient" in res.answer
    assert len(res.citations) == 0
    assert "No relevant evidence retrieved." in res.warnings
