import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.auth import EmailVerificationToken, RefreshTokenSession
from app.models.commercial import (
    CommercialTransaction,
    TransactionStatus,
    TransactionType,
)
from app.models.consultation import Consultation, ConsultationStatus
from app.models.job import BackgroundJob, JobStatus, JobType
from app.models.payment import Payment, PaymentStatus
from app.models.user import ClientProfile, LawyerProfile, User, UserRole
from app.models.video_meeting import VideoMeeting, VideoMeetingStatus
from app.models.video_recording import VideoRecording, VideoRecordingStatus
from app.models.webhook import ProcessedWebhookEvent, WebhookProcessingStatus
from app.domain.jobs.job_scheduler import JobScheduler
from app.services.job_service import JobService
from app.domain.jobs.job_worker import JobWorker
from app.domain.consultations.recording_storage import LocalRecordingStorageProvider, get_recording_storage_provider
from app.domain.consultations.video_recording_service import VideoRecordingService


def _setup_base_consultation(db: Session, status: ConsultationStatus = ConsultationStatus.IN_PROGRESS):
    client_user = User(
        id=generate_uuid7(),
        email=f"client_bg_{uuid.uuid4().hex[:6]}@test.com",
        role=UserRole.CLIENT,
    )
    lawyer_user = User(
        id=generate_uuid7(),
        email=f"lawyer_bg_{uuid.uuid4().hex[:6]}@test.com",
        role=UserRole.LAWYER,
    )
    db.add_all([client_user, lawyer_user])
    db.flush()

    c_prof = ClientProfile(user_id=client_user.id, full_name="BG Client")
    l_prof = LawyerProfile(
        id=generate_uuid7(),
        user_id=lawyer_user.id,
        full_name="BG Lawyer",
        consultation_fee=2500.0,
    )
    db.add_all([c_prof, l_prof])
    db.flush()

    now = datetime.now(UTC)
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=c_prof.id,
        lawyer_id=l_prof.id,
        scheduled_at=now - timedelta(hours=3),
        duration_minutes=30,
        fee_amount=2500.0,
        currency="INR",
        status=status,
    )
    db.add(consultation)
    db.commit()
    return client_user, lawyer_user, consultation


def test_stale_meeting_cleanup_job(db: Session):
    """
    Verify that the STALE_MEETING_CLEANUP job transitions active meetings past scheduled_end + 2h
    to ENDED and consultations to COMPLETED, and repeated runs are safe no-ops.
    """
    _, _, consultation = _setup_base_consultation(db, status=ConsultationStatus.IN_PROGRESS)

    past_time = datetime.now(UTC) - timedelta(hours=4)
    meeting = VideoMeeting(
        id=generate_uuid7(),
        consultation_id=consultation.id,
        room_id=f"room_stale_{uuid.uuid4().hex[:6]}",
        status=VideoMeetingStatus.ACTIVE,
        scheduled_start=past_time,
        scheduled_end=past_time + timedelta(minutes=30),
    )
    db.add(meeting)
    db.commit()

    # Enqueue STALE_MEETING_CLEANUP job
    job_svc = JobService(db)
    job = job_svc.enqueue_job(
        job_type=JobType.STALE_MEETING_CLEANUP,
        payload={"max_idle_hours": 2},
    )

    # Execute via JobWorker
    worker = JobWorker(db, worker_id="test-worker")
    executed = worker.execute_job(job.id)

    assert executed.status == JobStatus.SUCCEEDED
    assert executed.result_metadata["cleaned_meetings_count"] == 1

    # Verify meeting transitioned to ENDED and consultation to COMPLETED
    db.refresh(meeting)
    db.refresh(consultation)
    assert meeting.status == VideoMeetingStatus.ENDED
    assert consultation.status == ConsultationStatus.COMPLETED

    # Idempotent second execution: finds 0 stale meetings and does not error
    job_2 = job_svc.enqueue_job(
        job_type=JobType.STALE_MEETING_CLEANUP,
        payload={"max_idle_hours": 2},
    )
    executed_2 = worker.execute_job(job_2.id)
    assert executed_2.status == JobStatus.SUCCEEDED
    assert executed_2.result_metadata["cleaned_meetings_count"] == 0


def test_recording_upload_retry_job(db: Session, tmp_path: Path):
    """
    Verify that the RECORDING_UPLOAD_RETRY job safely finalizes recordings
    stuck in FAILED or PROCESSING when physical storage files exist.
    """
    storage_provider = get_recording_storage_provider()

    client_user, _, consultation = _setup_base_consultation(db)

    # Create a recording row in FAILED state
    storage_path = f"{consultation.id}/recording_test.webm"
    full_path = storage_provider.base_dir / storage_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(b"VALID_PHYSICAL_RECORDING_PAYLOAD_12345")

    rec = VideoRecording(
        id=generate_uuid7(),
        consultation_id=consultation.id,
        status=VideoRecordingStatus.FAILED,
        storage_path=storage_path,
        file_size_bytes=0,
        mime_type="video/webm",
    )
    # Backdate updated_at so it passes the grace period
    rec.updated_at = datetime.now(UTC) - timedelta(minutes=10)
    db.add(rec)
    db.commit()

    # Execute RECORDING_UPLOAD_RETRY job
    job_svc = JobService(db)
    job = job_svc.enqueue_job(
        job_type=JobType.RECORDING_UPLOAD_RETRY,
        payload={"max_age_minutes": 60, "grace_period_minutes": 5},
    )

    worker = JobWorker(db, worker_id="test-worker")
    executed = worker.execute_job(job.id)

    assert executed.status == JobStatus.SUCCEEDED
    assert executed.result_metadata["recovered_count"] >= 1

    db.refresh(rec)
    assert rec.status == VideoRecordingStatus.AVAILABLE
    assert rec.file_size_bytes == len(b"VALID_PHYSICAL_RECORDING_PAYLOAD_12345")
    assert rec.checksum_sha256 is not None


def test_webhook_reprocess_job(db: Session):
    """
    Verify that the WEBHOOK_REPROCESS job safely re-evaluates stale/failed webhooks
    and synchronizes domain payment records idempotently without duplicating side effects.
    """
    client_user, lawyer_user, consultation = _setup_base_consultation(db, status=ConsultationStatus.REQUESTED)

    provider_id = f"pi_retry_{uuid.uuid4().hex[:10]}"
    payment = Payment(
        id=generate_uuid7(),
        consultation_id=consultation.id,
        payer_user_id=client_user.id,
        amount=2500.0,
        currency="INR",
        status=PaymentStatus.CREATED,
        provider="stripe",
        provider_payment_id=provider_id,
    )
    db.add(payment)
    db.flush()

    # Add failed webhook event
    shared_evt_id = f"evt_reproc_{uuid.uuid4().hex[:10]}"
    webhook_rec = ProcessedWebhookEvent(
        id=generate_uuid7(),
        event_id=shared_evt_id,
        provider="STRIPE",
        event_type="payment_intent.succeeded",
        status=WebhookProcessingStatus.FAILED,
        resource_id=provider_id,
        payload={
            "id": shared_evt_id,
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": provider_id,
                    "amount": 250000,
                    "currency": "inr",
                    "status": "succeeded",
                }
            },
        },
        error_message="Transient network timeout during original processing",
    )
    db.add(webhook_rec)
    db.commit()

    # Execute WEBHOOK_REPROCESS job
    job_svc = JobService(db)
    job = job_svc.enqueue_job(
        job_type=JobType.WEBHOOK_REPROCESS,
        payload={"stale_minutes": 0, "limit": 10},
    )

    worker = JobWorker(db, worker_id="test-worker")
    executed = worker.execute_job(job.id)

    assert executed.status == JobStatus.SUCCEEDED
    assert executed.result_metadata["reprocessed_count"] >= 1

    # Verify domain state synchronized
    db.refresh(payment)
    db.refresh(consultation)
    db.refresh(webhook_rec)

    assert payment.status == PaymentStatus.SUCCEEDED
    assert consultation.status == ConsultationStatus.PAID
    assert webhook_rec.status == WebhookProcessingStatus.PROCESSED
    assert webhook_rec.error_message is None

    # Verify commercial transaction captured
    comm_txn = db.query(CommercialTransaction).filter(CommercialTransaction.consultation_id == consultation.id).first()
    assert comm_txn is not None
    assert comm_txn.status == TransactionStatus.CAPTURED

    # Re-run WEBHOOK_REPROCESS job: strictly idempotent, no duplicate transaction created
    job_2 = job_svc.enqueue_job(
        job_type=JobType.WEBHOOK_REPROCESS,
        payload={"stale_minutes": 0, "limit": 10},
    )
    executed_2 = worker.execute_job(job_2.id)
    assert executed_2.status == JobStatus.SUCCEEDED

    txn_count = db.query(CommercialTransaction).filter(CommercialTransaction.consultation_id == consultation.id).count()
    assert txn_count == 1


def test_commercial_reconciliation_job(db: Session):
    """
    Verify that the COMMERCIAL_RECONCILIATION job executes the authoritative
    reconciliation engine and produces structured findings without mutating financial data.
    """
    job_svc = JobService(db)
    job = job_svc.enqueue_job(
        job_type=JobType.COMMERCIAL_RECONCILIATION,
        payload={},
    )

    worker = JobWorker(db, worker_id="test-worker")
    executed = worker.execute_job(job.id)

    assert executed.status == JobStatus.SUCCEEDED
    meta = executed.result_metadata
    assert "variance_inr" in meta
    assert "discrepancy_count" in meta
    assert "gross_volume_inr" in meta


def test_expired_session_cleanup_job(db: Session):
    """
    Verify that EXPIRED_SESSION_CLEANUP prunes RefreshTokenSessions expired beyond 30 days
    and EmailVerificationTokens expired beyond 7 days, while keeping active tokens intact.
    """
    client_user, _, _ = _setup_base_consultation(db)
    now = datetime.now(UTC)

    # 1. Stale refresh token session (> 35 days ago) -> MUST BE PRUNED
    old_rt = RefreshTokenSession(
        id=generate_uuid7(),
        user_id=client_user.id,
        token_family_id=generate_uuid7(),
        token_hash="hash_old_rt",
        created_at=now - timedelta(days=60),
        last_used_at=now - timedelta(days=40),
        expires_at=now - timedelta(days=35),
    )
    # 2. Fresh refresh token session -> MUST BE KEPT
    fresh_rt = RefreshTokenSession(
        id=generate_uuid7(),
        user_id=client_user.id,
        token_family_id=generate_uuid7(),
        token_hash="hash_fresh_rt",
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(days=7),
    )

    # 3. Stale verification token (> 10 days ago) -> MUST BE PRUNED
    old_vt = EmailVerificationToken(
        id=generate_uuid7(),
        user_id=client_user.id,
        email=client_user.email,
        token_hash="hash_old_vt",
        created_at=now - timedelta(days=20),
        expires_at=now - timedelta(days=10),
    )
    # 4. Fresh verification token -> MUST BE KEPT
    fresh_vt = EmailVerificationToken(
        id=generate_uuid7(),
        user_id=client_user.id,
        email=client_user.email,
        token_hash="hash_fresh_vt",
        created_at=now,
        expires_at=now + timedelta(minutes=15),
    )

    old_rt_id = old_rt.id
    fresh_rt_id = fresh_rt.id
    old_vt_id = old_vt.id
    fresh_vt_id = fresh_vt.id

    db.add_all([old_rt, fresh_rt, old_vt, fresh_vt])
    db.commit()

    # Execute EXPIRED_SESSION_CLEANUP job
    job_svc = JobService(db)
    job = job_svc.enqueue_job(
        job_type=JobType.EXPIRED_SESSION_CLEANUP,
        payload={"refresh_token_retention_days": 30, "verification_token_retention_days": 7},
    )

    worker = JobWorker(db, worker_id="test-worker")
    executed = worker.execute_job(job.id)

    assert executed.status == JobStatus.SUCCEEDED
    assert executed.result_metadata["pruned_refresh_token_sessions"] >= 1
    assert executed.result_metadata["pruned_verification_tokens"] >= 1

    # Verify old records deleted, fresh records retained
    assert db.query(RefreshTokenSession).filter(RefreshTokenSession.id == old_rt_id).first() is None
    assert db.query(RefreshTokenSession).filter(RefreshTokenSession.id == fresh_rt_id).first() is not None
    assert db.query(EmailVerificationToken).filter(EmailVerificationToken.id == old_vt_id).first() is None
    assert db.query(EmailVerificationToken).filter(EmailVerificationToken.id == fresh_vt_id).first() is not None


def test_periodic_scans_enqueue_idempotently(db: Session):
    """
    Verify that JobScheduler.trigger_periodic_scans() enqueues all periodic maintenance jobs
    with time-bucketed idempotency keys and running it again within the same time bucket
    returns the identical jobs without duplicates.
    """
    scheduler = JobScheduler(worker_id="scheduler-test")
    batch_1 = scheduler.trigger_periodic_scans(db)

    assert "stale_meeting_cleanup_job_id" in batch_1
    assert "recording_retry_job_id" in batch_1
    assert "webhook_reprocess_job_id" in batch_1
    assert "commercial_reconciliation_job_id" in batch_1
    assert "expired_session_cleanup_job_id" in batch_1

    # Second trigger within same time bucket returns exact same job IDs
    batch_2 = scheduler.trigger_periodic_scans(db)

    assert batch_1["stale_meeting_cleanup_job_id"] == batch_2["stale_meeting_cleanup_job_id"]
    assert batch_1["recording_retry_job_id"] == batch_2["recording_retry_job_id"]
    assert batch_1["webhook_reprocess_job_id"] == batch_2["webhook_reprocess_job_id"]
    assert batch_1["commercial_reconciliation_job_id"] == batch_2["commercial_reconciliation_job_id"]
    assert batch_1["expired_session_cleanup_job_id"] == batch_2["expired_session_cleanup_job_id"]
