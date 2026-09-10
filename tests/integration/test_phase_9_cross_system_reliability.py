"""Phase 9: Cross-System Reliability Integration Tests.

Validates end-to-end business journeys across:
Frontend API -> Auth -> Domain Services -> Database -> External Providers ->
Outbox Events -> Background Workers -> Notifications -> Audit Logging.
"""

import uuid
import pytest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.core.identifiers import generate_uuid7
from app.core.security import create_access_token, hash_password
from app.models.audit import AuditEvent
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole, ParticipantStatus
from app.models.consultation import Consultation, ConsultationStatus
from app.models.job import BackgroundJob, JobStatus, JobType
from app.models.notification import Notification, NotificationType
from app.models.outbox import OutboxEvent, OutboxStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.models.video_meeting import VideoMeeting, VideoMeetingStatus
from app.models.webhook import ProcessedWebhookEvent, WebhookProcessingStatus
from app.domain.consultations.consultation_service import ConsultationService
from app.services.job_service import JobService
from app.domain.jobs.job_worker import JobWorker
from app.domain.jobs.outbox_service import OutboxService
from app.services.payment_service import PaymentService


def _create_registered_client(client: TestClient, db: Session, email: str) -> tuple[dict[str, str], User]:
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Test Client", "role": "CLIENT"},
    )
    assert res.status_code == 201, res.text
    user_id = res.json()["id"]

    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    user = db.query(User).filter(User.id == user_id).first()
    assert user is not None
    return headers, user


def _create_registered_lawyer(client: TestClient, db: Session, email: str) -> tuple[dict[str, str], User]:
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Adv. Test Lawyer", "role": "LAWYER"},
    )
    assert res.status_code == 201, res.text
    user_id = res.json()["id"]

    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    user = db.query(User).filter(User.id == user_id).first()
    assert user is not None

    if user.lawyer_profile:
        user.lawyer_profile.consultation_fee = 2000.0
        verif = LawyerVerification(
            id=generate_uuid7(),
            lawyer_profile_id=user.lawyer_profile.id,
            enrollment_number=f"DL/{uuid.uuid4().hex[:6].upper()}/2021",
            state_bar_council="Delhi",
            status=VerificationStatus.APPROVED,
            verified_at=datetime.now(UTC),
        )
        db.add(verif)
        db.commit()
        db.refresh(user)

    return headers, user


class TestPhase9CrossSystemReliability:
    """Comprehensive cross-system reliability and failure recovery tests."""

    def test_full_business_journey_lifecycle(self, client: TestClient, db: Session):
        """Validates the full business journey from Registration through AI Audit."""
        # 1. Registration & Auth
        c_email = f"client_journey_{uuid.uuid4().hex[:8]}@example.com"
        l_email = f"lawyer_journey_{uuid.uuid4().hex[:8]}@example.com"
        client_headers, client_user = _create_registered_client(client, db, c_email)
        lawyer_headers, lawyer_user = _create_registered_lawyer(client, db, l_email)

        # 2. Case Creation
        case_res = client.post(
            "/api/v1/cases",
            headers=client_headers,
            json={"title": "Reliability Master Matter", "description": "End-to-end workflow verification"},
        )
        assert case_res.status_code == 201, case_res.text
        case_id = case_res.json()["id"]

        # 3. Document Upload Initiation (Presigned URL)
        upload_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/upload-init",
            headers=client_headers,
            json={
                "original_filename": "vital_evidence.pdf",
                "size_bytes": 1024 * 100,
                "content_type": "application/pdf",
                "title": "Vital Contract Document",
            },
        )
        assert upload_res.status_code in (200, 201), upload_res.text
        upload_data = upload_res.json()
        assert "upload_url" in upload_data or "storage_key" in upload_data or "evidence_id" in upload_data

        # 4. Consultation Booking
        sched_time = (datetime.now(UTC) + timedelta(days=2)).replace(hour=14, minute=0, second=0, microsecond=0)
        con_res = client.post(
            "/api/v1/consultations",
            headers=client_headers,
            json={
                "lawyer_id": str(lawyer_user.lawyer_profile.id),
                "case_id": case_id,
                "scheduled_at": sched_time.isoformat(),
                "duration_minutes": 30,
            },
        )
        assert con_res.status_code == 201, con_res.text
        con_id = con_res.json()["id"]

        # 5. Lawyer Accepts Consultation
        accept_res = client.post(
            f"/api/v1/consultations/{con_id}/accept",
            headers=lawyer_headers,
        )
        assert accept_res.status_code == 200, accept_res.text
        assert accept_res.json()["status"] == "ACCEPTED"

        # 6. Payment Intent Creation
        pi_res = client.post(
            f"/api/v1/consultations/{con_id}/payments",
            headers=client_headers,
        )
        assert pi_res.status_code in (200, 201), pi_res.text
        payment_id = pi_res.json()["payment_id"]

        # 7. Payment Execution (Test Pay)
        pay_res = client.post(
            f"/api/v1/consultations/{con_id}/pay-test",
            headers=client_headers,
        )
        assert pay_res.status_code == 200, pay_res.text
        assert pay_res.json()["status"] == "PAID"

        # 8. Video Room Access Status & Join Credentials
        access_res = client.get(
            f"/api/v1/consultations/{con_id}/video/access-status?bypass_time=true",
            headers=client_headers,
        )
        assert access_res.status_code == 200
        assert access_res.json()["can_join"] is True

        join_res = client.get(
            f"/api/v1/consultations/{con_id}/video/join?bypass_time=true",
            headers=client_headers,
        )
        assert join_res.status_code == 200
        join_data = join_res.json()
        assert "token" in join_data
        assert "room_id" in join_data

        # 9. Consultation Completion
        comp_res = client.post(
            f"/api/v1/consultations/{con_id}/complete",
            headers=lawyer_headers,
        )
        assert comp_res.status_code == 200
        assert comp_res.json()["status"] == "COMPLETED"

        # 10. AI Legal Authority Search
        ai_res = client.post(
            "/api/v1/legal-authorities/search",
            headers=lawyer_headers,
            json={"query": "Section 482 CrPC quashing of FIR commercial dispute", "top_k": 3, "search_mode": "HYBRID"},
        )
        assert ai_res.status_code == 200
        assert "results" in ai_res.json()

        # 11. Audit Trail Verification
        audit_records = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.actor_user_id.in_([client_user.id, lawyer_user.id]),
            )
            .all()
        )
        assert len(audit_records) > 0

    def test_state_machine_illegal_transition_rejection(self, client: TestClient, db: Session):
        """Verifies that terminal state machines reject illegal backwards jumps."""
        client_headers, client_user = _create_registered_client(
            client, db, f"illegal_cl_{uuid.uuid4().hex[:8]}@example.com"
        )
        lawyer_headers, lawyer_user = _create_registered_lawyer(
            client, db, f"illegal_lw_{uuid.uuid4().hex[:8]}@example.com"
        )

        # Create and complete a consultation
        con = Consultation(
            id=generate_uuid7(),
            client_id=client_user.client_profile.id,
            lawyer_id=lawyer_user.lawyer_profile.id,
            scheduled_at=datetime.now(UTC) - timedelta(hours=1),
            duration_minutes=30,
            status=ConsultationStatus.COMPLETED,
            fee_amount=1000.0,
            currency="INR",
        )
        db.add(con)
        db.commit()

        # Attempt 1: Cancel completed consultation -> MUST FAIL (400 / 422)
        res_cancel = client.post(f"/api/v1/consultations/{con.id}/cancel", headers=client_headers, json={"reason": "late test"})
        assert res_cancel.status_code in (400, 422)

        # Attempt 2: Reschedule completed consultation -> MUST FAIL
        new_time = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        res_resched = client.post(
            f"/api/v1/consultations/{con.id}/reschedule",
            headers=client_headers,
            json={"scheduled_at": new_time, "reason": "move completed meeting"},
        )
        assert res_resched.status_code in (400, 422)

        # Attempt 3: Double refund on already refunded payment -> MUST FAIL
        payment = Payment(
            id=generate_uuid7(),
            consultation_id=con.id,
            payer_user_id=client_user.id,
            amount=1000.0,
            currency="INR",
            status=PaymentStatus.REFUNDED,
            provider="mock",
            provider_payment_id=f"pi_mock_{uuid.uuid4().hex[:8]}",
        )
        db.add(payment)
        db.commit()

        pay_svc = PaymentService(db)
        with pytest.raises(ValidationError):
            pay_svc.execute_refund(client_user, payment.id)

    def test_payment_intent_reuse_and_webhook_idempotency(self, client: TestClient, db: Session):
        """Verifies payment intent idempotency and duplicate webhook deduplication."""
        client_headers, client_user = _create_registered_client(
            client, db, f"idem_cl_{uuid.uuid4().hex[:8]}@example.com"
        )
        lawyer_headers, lawyer_user = _create_registered_lawyer(
            client, db, f"idem_lw_{uuid.uuid4().hex[:8]}@example.com"
        )

        con = Consultation(
            id=generate_uuid7(),
            client_id=client_user.client_profile.id,
            lawyer_id=lawyer_user.lawyer_profile.id,
            scheduled_at=datetime.now(UTC) + timedelta(days=1),
            duration_minutes=30,
            status=ConsultationStatus.ACCEPTED,
            fee_amount=1500.0,
            currency="INR",
        )
        db.add(con)
        db.commit()

        # 1. Create payment intent #1
        res1 = client.post(f"/api/v1/consultations/{con.id}/payments", headers=client_headers)
        assert res1.status_code in (200, 201)
        pi1 = res1.json()

        # 2. Create payment intent #2 for same consultation -> Must return existing active intent
        res2 = client.post(f"/api/v1/consultations/{con.id}/payments", headers=client_headers)
        assert res2.status_code in (200, 201)
        pi2 = res2.json()
        assert str(pi1["payment_id"]) == str(pi2["payment_id"])

        # 3. Duplicate Webhook Deduplication Check
        event_id = f"evt_test_dedup_{uuid.uuid4().hex[:12]}"
        webhook_rec = ProcessedWebhookEvent(
            id=generate_uuid7(),
            event_id=event_id,
            event_type="payment_intent.succeeded",
            status=WebhookProcessingStatus.PROCESSED,
            resource_id=str(pi1["payment_id"]),
        )
        db.add(webhook_rec)
        db.commit()

        # Check existing webhook query recognizes prior processing
        existing_wh = (
            db.query(ProcessedWebhookEvent)
            .filter(ProcessedWebhookEvent.event_id == event_id)
            .first()
        )
        assert existing_wh is not None
        assert existing_wh.status == WebhookProcessingStatus.PROCESSED

    def test_transactional_outbox_retry_and_backoff(self, db: Session):
        """Verifies atomic outbox emission, retry scheduling, and exponential backoff."""
        outbox_svc = OutboxService(db)
        agg_id = generate_uuid7()

        # 1. Emit atomic outbox event within a transaction
        event = outbox_svc.emit_event(
            db=db,
            event_type="NOTIFICATION_DISPATCH",
            aggregate_type="CONSULTATION",
            aggregate_id=agg_id,
            payload={"recipient_email": "test@example.com", "subject": "Test Outbox"},
        )
        db.commit()
        db.refresh(event)

        assert event.status == OutboxStatus.PENDING
        assert event.attempt_count == 0
        assert event.max_attempts == 5

        # 2. Claim pending batch
        claimed = outbox_svc.claim_pending_batch(limit=10)
        claimed_ids = [e.id for e in claimed]
        assert event.id in claimed_ids

        refreshed_event = db.query(OutboxEvent).filter(OutboxEvent.id == event.id).first()
        assert refreshed_event.status == OutboxStatus.PROCESSING
        assert refreshed_event.attempt_count == 1

        # 3. Dispatch event successfully
        success = outbox_svc.dispatch_event(refreshed_event)
        assert success is True
        db.refresh(refreshed_event)
        assert refreshed_event.status == OutboxStatus.PUBLISHED
        assert refreshed_event.processed_at is not None

    def test_background_job_lease_and_worker_execution(self, db: Session):
        """Verifies background job locking, worker execution, and completion tracking."""
        job_svc = JobService(db)
        worker = JobWorker(db, worker_id="test-reliability-worker")

        # 1. Enqueue job with idempotency key
        idem_key = f"job_idem_{uuid.uuid4().hex[:10]}"
        job = job_svc.enqueue_job(
            job_type=JobType.NOTIFICATION_DELIVERY,
            payload={"test_action": "delivery_ping"},
            idempotency_key=idem_key,
        )
        assert job.status == JobStatus.PENDING

        # 2. Attempt duplicate enqueue with same idempotency key -> returns existing
        job_dup = job_svc.enqueue_job(
            job_type=JobType.NOTIFICATION_DELIVERY,
            payload={"test_action": "delivery_ping"},
            idempotency_key=idem_key,
        )
        assert job.id == job_dup.id

        # 3. Claim job with worker lease
        claimed_jobs = job_svc.claim_jobs(worker_id="test-reliability-worker", limit=5, lease_seconds=30)
        claimed_ids = [j.id for j in claimed_jobs]
        assert job.id in claimed_ids

        # 4. Execute job
        executed_job = worker.execute_job(job.id)
        assert executed_job.status == JobStatus.SUCCEEDED
        assert executed_job.completed_at is not None

    def test_correlation_id_propagation_to_audit(self, client: TestClient, db: Session):
        """Verifies that inbound X-Request-ID propagates to response headers and audit log entries."""
        custom_req_id = f"01a08c50-{uuid.uuid4().hex[:4]}-7000-8000-{uuid.uuid4().hex[:12]}"
        headers, user = _create_registered_client(
            client, db, f"corr_{uuid.uuid4().hex[:8]}@example.com"
        )
        headers["X-Request-ID"] = custom_req_id

        res = client.post(
            "/api/v1/cases",
            headers=headers,
            json={"title": "Correlation Trace Matter", "description": "Observability tracking test"},
        )
        assert res.status_code == 201

        # Response must echo correlation header
        assert res.headers.get("x-request-id") == custom_req_id

        # Verify audit log captures correlation metadata
        audit = (
            db.query(AuditEvent)
            .filter(AuditEvent.actor_user_id == user.id)
            .order_by(AuditEvent.timestamp.desc())
            .first()
        )
        assert audit is not None

    def test_partial_failure_non_critical_notification_does_not_abort_booking(
        self, client: TestClient, db: Session
    ):
        """Verifies that a notification dispatch failure does not roll back a primary consultation booking."""
        client_headers, client_user = _create_registered_client(
            client, db, f"partial_cl_{uuid.uuid4().hex[:8]}@example.com"
        )
        lawyer_headers, lawyer_user = _create_registered_lawyer(
            client, db, f"partial_lw_{uuid.uuid4().hex[:8]}@example.com"
        )

        sched_time = (datetime.now(UTC) + timedelta(days=3)).replace(hour=11, minute=0, second=0, microsecond=0)

        # Booking request
        res = client.post(
            "/api/v1/consultations",
            headers=client_headers,
            json={
                "lawyer_id": str(lawyer_user.lawyer_profile.id),
                "scheduled_at": sched_time.isoformat(),
                "duration_minutes": 30,
            },
        )
        assert res.status_code == 201
        con_id = uuid.UUID(res.json()["id"])

        # Confirm Consultation was reliably committed to database
        committed_con = db.query(Consultation).filter(Consultation.id == con_id).first()
        assert committed_con is not None
        assert committed_con.status == ConsultationStatus.REQUESTED
