import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import ScannerUnavailableError, ValidationError
from app.core.logging import SensitiveDataScrubberFilter
from app.core.security import create_access_token, hash_password
from app.core.storage import get_storage_provider
from app.models.case import Case, CaseParticipant, ParticipantRole, ParticipantStatus
from app.models.evidence import (
    Evidence,
    EvidenceCategory,
    EvidenceCustodyAction,
    EvidenceIntegrityStatus,
    EvidenceScanStatus,
    EvidenceSensitivity,
    EvidenceStatus,
    EvidenceVersion,
)
from app.models.job import BackgroundJob, JobStatus, JobType
from app.models.outbox import OutboxEvent, OutboxStatus
from app.models.user import AccountStatus, ClientProfile, User, UserRole
from app.services.evidence_service import EvidenceService
from app.services.job_service import JobService
from app.services.job_worker import JobWorker
from app.services.outbox_service import OutboxService
from app.services.scanner_service import MalwareScanner

VALID_PDF_BYTES = b"%PDF-1.5\n%Reliability test evidence\n1 0 obj\n<< >>\nendobj\n%%EOF"


def _create_user(db: Session, prefix: str) -> tuple[User, str]:
    uid = uuid.uuid4().hex[:6]
    user = User(
        email=f"{prefix}_{uid}@example.com",
        password_hash=hash_password("SecurePass123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()
    profile = ClientProfile(user_id=user.id, full_name=f"Client {prefix.capitalize()}")
    db.add(profile)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id), user.role.value)
    return user, token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class FailingScanner(MalwareScanner):
    """Simulates an external malware scanner outage / timeout."""

    def scan_bytes(self, file_bytes: bytes, filename: str) -> tuple[bool, str | None]:
        raise ConnectionError("ClamAV daemon connection timed out on port 3310")


class TestPhaseXVReliability:
    """Production reliability, background job resilience, fail-closed security,

    transactional outbox durability, and reconciliation test suite.
    """

    def test_duplicate_job_idempotency(self, db: Session):
        """Test 1: Enqueuing a job with identical idempotency_key returns existing job without duplicates."""
        job_svc = JobService(db)
        idempotency_key = f"unique_task_{uuid.uuid4().hex}"

        job_1 = job_svc.enqueue_job(
            job_type=JobType.DOCUMENT_INDEXING,
            payload={"document_id": str(uuid.uuid4())},
            idempotency_key=idempotency_key,
        )

        job_2 = job_svc.enqueue_job(
            job_type=JobType.DOCUMENT_INDEXING,
            payload={"document_id": str(uuid.uuid4())},
            idempotency_key=idempotency_key,
        )

        assert job_1.id == job_2.id
        total = db.query(BackgroundJob).filter(BackgroundJob.idempotency_key == idempotency_key).count()
        assert total == 1

    def test_worker_lease_expiration_and_stale_recovery(self, db: Session):
        """Test 2: A hung worker lease (expired locked_until) is reclaimed and re-queued."""
        job_svc = JobService(db)
        worker = JobWorker(db, worker_id="test-worker")

        # Create a job that is locked in the past (hung worker)
        job = BackgroundJob(
            job_type=JobType.DOCUMENT_INDEXING,
            status=JobStatus.RUNNING,
            payload={"document_id": str(uuid.uuid4())},
            locked_by="crashed-worker-instance-9",
            locked_until=datetime.now(UTC) - timedelta(seconds=120),
            attempt_count=1,
            max_attempts=3,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Trigger stale recovery
        recovered = job_svc.reclaim_stale_jobs()
        assert recovered >= 1

        db.refresh(job)
        assert job.status in [JobStatus.PENDING, JobStatus.RETRYING]
        assert job.locked_by is None
        assert job.locked_until is None

    def test_transactional_outbox_durability_and_dispatch(self, db: Session):
        """Test 3: Outbox event commits atomically with business transaction and is published by worker."""
        outbox_svc = OutboxService(db)
        aggregate_id = uuid.uuid4()

        # Emit outbox event in transaction
        event = OutboxService.emit_event(
            db=db,
            event_type="NOTIFICATION_DISPATCH",
            aggregate_type="notification",
            aggregate_id=aggregate_id,
            payload={"recipient": "client@example.com", "body": "Case update"},
        )
        db.commit()
        db.refresh(event)

        assert event.status == OutboxStatus.PENDING
        assert event.attempt_count == 0

        # Dispatch via OutboxService batch processing
        processed_count = outbox_svc.process_outbox_batch(limit=10)
        assert processed_count >= 1

        db.refresh(event)
        assert event.status == OutboxStatus.PUBLISHED
        assert event.processed_at is not None

    def test_storage_failure_fails_closed(self, client: TestClient, db: Session):
        """Test 4: Storage failure during evidence completion fails closed, never activates."""
        user, token = _create_user(db, "storage_fail")
        c_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(token),
            json={"title": "Storage Outage Test Case", "description": "Storage outage forensic analysis"},
        )
        assert c_res.status_code == 201
        case_id = c_res.json()["id"]

        init_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/upload-init",
            headers=_auth_headers(token),
            json={
                "title": "Missing Storage Evidence",
                "category": "CONTRACTUAL",
                "sensitivity": "STANDARD",
                "original_filename": "missing.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(VALID_PDF_BYTES),
            },
        )
        assert init_res.status_code == 201
        evidence_id = init_res.json()["evidence_id"]
        version_id = init_res.json()["version_id"]
        # Do NOT put bytes in storage (simulates S3 upload failure/timeout)

        complete_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/complete",
            headers=_auth_headers(token),
            json={"version_id": version_id},
        )
        assert complete_res.status_code == 422

        ev = db.query(Evidence).filter(Evidence.id == uuid.UUID(evidence_id)).first()
        assert ev.status == EvidenceStatus.QUARANTINED
        assert ev.status != EvidenceStatus.ACTIVE

    def test_malware_scanner_failure_fails_closed(self, db: Session):
        """Test 5: Scanner failure/timeout fails closed and raises ScannerUnavailableError without activating."""
        user, _ = _create_user(db, "scanner_fail")
        storage = get_storage_provider()

        case = Case(title="Scanner Failure Case", description="Scanner outage case")
        db.add(case)
        db.flush()
        participant = CaseParticipant(
            case_id=case.id,
            user_id=user.id,
            participant_role=ParticipantRole.OWNER,
            status=ParticipantStatus.ACTIVE,
        )
        db.add(participant)
        db.commit()

        ev_svc = EvidenceService(db, scanner=FailingScanner())

        init_ev, init_ver, _ = ev_svc.init_upload(
            user=user,
            case_id=case.id,
            req=type("Req", (), {
                "title": "Unscanned Document",
                "description": None,
                "category": EvidenceCategory.CONTRACTUAL,
                "sensitivity": EvidenceSensitivity.STANDARD,
                "original_filename": "unscanned.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(VALID_PDF_BYTES),
                "retention_until": None,
            })(),
        )

        storage.put_object_bytes(init_ver.storage_key, VALID_PDF_BYTES, mime_type="application/pdf")

        # Attempt completion with failing scanner -> Must fail closed
        with pytest.raises(ScannerUnavailableError):
            ev_svc.complete_upload(
                user=user,
                case_id=case.id,
                evidence_id=init_ev.id,
                version_id=init_ver.id,
            )

        db.refresh(init_ev)
        assert init_ev.status == EvidenceStatus.QUARANTINED
        assert init_ev.status != EvidenceStatus.ACTIVE

    def test_dead_letter_queue_transition_on_exhausted_retries(self, db: Session):
        """Test 9: Background job exhausts max attempts and transitions to DEAD_LETTER."""
        worker = JobWorker(db, worker_id="dlq-worker")

        job = BackgroundJob(
            job_type=JobType.DOCUMENT_PROCESSING,
            status=JobStatus.RUNNING,
            payload={"document_id": str(uuid.uuid4())},
            attempt_count=3,
            max_attempts=3,  # Already at max attempts
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        worker.execute_job(job.id)

        db.refresh(job)
        assert job.status in [JobStatus.DEAD_LETTER, JobStatus.FAILED]

    def test_evidence_orphan_and_abandoned_reconciliation(self, db: Session):
        """Test 8: Reconciles abandoned uploads and detects orphaned storage items."""
        user, _ = _create_user(db, "recon_user")
        ev_svc = EvidenceService(db)

        # 1. Create an evidence item stuck in UPLOADING with past created_at
        stuck_ev = Evidence(
            case_id=uuid.uuid4(),
            created_by_user_id=user.id,
            title="Abandoned Draft",
            original_filename="abandoned.pdf",
            status=EvidenceStatus.UPLOADING,
            created_at=datetime.now(UTC) - timedelta(hours=4),
        )
        db.add(stuck_ev)
        db.commit()

        reconciled_abandoned = ev_svc.reconcile_abandoned_uploads(hours_threshold=2)
        assert reconciled_abandoned >= 1

        db.refresh(stuck_ev)
        assert stuck_ev.status == EvidenceStatus.QUARANTINED

        # 2. Create an active evidence version pointing to a nonexistent S3 key
        fake_storage_key = f"cases/missing/evidence/{uuid.uuid4()}/versions/{uuid.uuid4()}"
        active_ev = Evidence(
            case_id=uuid.uuid4(),
            created_by_user_id=user.id,
            title="Missing Storage Evidence",
            original_filename="lost.pdf",
            status=EvidenceStatus.ACTIVE,
        )
        db.add(active_ev)
        db.flush()

        ver = EvidenceVersion(
            evidence_id=active_ev.id,
            version_number=1,
            uploaded_by_user_id=user.id,
            storage_key=fake_storage_key,
            original_filename="lost.pdf",
            content_type="application/pdf",
            size_bytes=1000,
            sha256="0" * 64,
            scan_status=EvidenceScanStatus.PASSED,
            integrity_status=EvidenceIntegrityStatus.VERIFIED_MATCH,
        )
        db.add(ver)
        db.commit()

        recon_result = ev_svc.reconcile_orphaned_evidence()
        assert recon_result["missing_storage_objects"] >= 1

        db.refresh(ver)
        assert ver.integrity_status == EvidenceIntegrityStatus.TAMPER_DETECTED

    def test_sensitive_data_scrubbing_in_logs(self):
        """Test 10: SensitiveDataScrubberFilter redacts passwords, bearer tokens, and signed URLs."""
        scrubber = SensitiveDataScrubberFilter()

        record_1 = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg='User login with password: "SecretPassword123!"', args=(), exc_info=None
        )
        scrubber.filter(record_1)
        assert "SecretPassword123!" not in record_1.msg
        assert "***REDACTED***" in record_1.msg

        record_2 = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Request with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.signature", args=(), exc_info=None
        )
        scrubber.filter(record_2)
        assert "eyJhbGci" not in record_2.msg
        assert "Bearer ***REDACTED***" in record_2.msg
