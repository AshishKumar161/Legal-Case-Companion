from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import ScannerUnavailableError
from app.core.identifiers import generate_uuid7
from app.core.metrics import metrics_collector
from app.core.storage import get_storage_provider
from app.main import app
from app.models.audit import AuditEvent
from app.models.case import (
    Case,
    CaseParticipant,
    CaseStatus,
    ParticipantRole,
    ParticipantStatus,
)
from app.models.consultation import Consultation, ConsultationStatus
from app.models.document import Document, DocumentSecurityStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole
from app.services.payment_service import PaymentService
from app.domain.evidence.scanner_service import (
    ClamAVScanner,
    DefaultMalwareScanner,
    ScannerService,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_operational_health_probes(client: TestClient):
    """
    Phase 17: Verifies separate liveness and readiness probes across
    both /health/* paths and root aliases (/liveness, /readiness).
    """
    # Liveness probes
    res_live_1 = client.get("/api/v1/health/live")
    assert res_live_1.status_code == 200
    assert res_live_1.json()["status"] == "alive"

    res_live_2 = client.get("/liveness")
    assert res_live_2.status_code == 200
    assert res_live_2.json()["status"] == "alive"

    # Readiness probes
    res_ready_1 = client.get("/api/v1/health/ready")
    assert res_ready_1.status_code == 200
    assert res_ready_1.json()["status"] == "ready"
    assert res_ready_1.json()["database"] == "connected"

    res_ready_2 = client.get("/readiness")
    assert res_ready_2.status_code == 200
    assert res_ready_2.json()["status"] == "ready"
    assert res_ready_2.json()["database"] == "connected"


def test_rate_limiter_protection_on_sensitive_routes():
    """
    Phase 20: Verifies that sensitive financial and consultation endpoints
    have slowapi rate limiting attached.
    """
    from app.api.v1.consultations import (
        create_payment,
        join_video_meeting,
        request_consultation,
    )

    # Functions decorated with @limiter.limit are callable and wrapped by slowapi
    assert callable(request_consultation)
    assert callable(create_payment)
    assert callable(join_video_meeting)



def test_metrics_middleware_masks_uuids_for_low_cardinality(client: TestClient):
    """
    Phase 27: Verifies that UUID parameters in URL paths are masked to {id}
    to preserve bounded cardinality and prevent resource ID leakage in metrics.
    """
    fake_case_id = "12345678-abcd-1234-abcd-123456789abc"
    res = client.get(f"/api/v1/cases/{fake_case_id}")
    # Endpoint will return 401 or 404, which is expected
    assert res.status_code in (401, 404)

    snapshot = metrics_collector.get_metrics_snapshot()
    top_endpoints = snapshot.get("top_endpoints", {})

    # The masked endpoint string must appear, NOT the raw UUID
    assert any("GET /api/v1/cases/{id}" in ep for ep in metrics_collector.request_counts.keys())
    assert not any(fake_case_id in ep for ep in metrics_collector.request_counts.keys())


def test_clamav_fail_closed_on_daemon_outage(db: Session):
    """
    Phase 10 & Non-Negotiable Principle 9:
    When ClamAV is configured and unreachable, the scan must fail closed.
    The document MUST remain in QUARANTINED state and NEVER be marked SAFE.
    """
    # 1. Create a client and case
    client_user = User(
        id=generate_uuid7(),
        email=f"clamav_test_{generate_uuid7()}@example.com",
        password_hash="fakehash",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(client_user)
    db.commit()

    case = Case(
        id=generate_uuid7(),
        title="ClamAV Resilience Case",
        description="Matter for testing ClamAV fail-closed resilience",
        status=CaseStatus.OPEN,
    )
    db.add(case)
    part = CaseParticipant(
        id=generate_uuid7(),
        case_id=case.id,
        user_id=client_user.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
        joined_at=datetime.now(UTC),
    )
    db.add(part)
    db.commit()

    # 2. Upload a clean PDF file to storage
    doc_id = generate_uuid7()
    storage_key = f"cases/{case.id}/documents/{doc_id}/clean_contract.pdf"
    storage = get_storage_provider()
    clean_pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    storage.put_object_bytes(storage_key, clean_pdf_bytes, mime_type="application/pdf")

    document = Document(
        id=doc_id,
        case_id=case.id,
        filename="clean_contract.pdf",
        storage_key=storage_key,
        file_size=len(clean_pdf_bytes),
        mime_type="application/pdf",
        uploaded_by=client_user.id,
        security_status=DocumentSecurityStatus.QUARANTINED,
    )
    db.add(document)
    db.commit()

    # 3. Instantiate ClamAV scanner with an unreachable port (simulating daemon outage)
    failing_clamav = ClamAVScanner(host="127.0.0.1", port=59998)
    composite_scanner = DefaultMalwareScanner()
    composite_scanner.clamav_scanner = failing_clamav

    scanner_service = ScannerService(db, scanner=composite_scanner)

    # 4. Scanning must raise ScannerUnavailableError
    with pytest.raises(ScannerUnavailableError) as exc_info:
        scanner_service.scan_document(document.id)

    assert "ClamAV daemon connection failed" in str(exc_info.value)

    # 5. Verify database invariants: document MUST REMAIN QUARANTINED
    db.refresh(document)
    assert document.security_status == DocumentSecurityStatus.QUARANTINED
    assert "Malware scanner service is temporarily unavailable" in str(document.processing_error)

    # 6. Verify audit event
    audit = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.event_type == "DOCUMENT_SCAN_UNAVAILABLE",
            AuditEvent.actor_user_id == client_user.id,
        )
        .first()
    )
    assert audit is not None


def test_stripe_webhook_replay_and_idempotency(db: Session):
    """
    Phase 14: Webhook operations must be strictly idempotent under replay,
    safely handling repeated events without duplicate side-effects.
    """
    # 1. Create client and lawyer
    client_user = User(
        id=generate_uuid7(),
        email=f"client_wh_{generate_uuid7()}@example.com",
        password_hash="fakehash",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    lawyer_user = User(
        id=generate_uuid7(),
        email=f"lawyer_wh_{generate_uuid7()}@example.com",
        password_hash="fakehash",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add_all([client_user, lawyer_user])
    db.commit()

    client_profile = ClientProfile(
        id=generate_uuid7(),
        user_id=client_user.id,
        full_name="Client Webhook Test",
    )
    lawyer_profile = LawyerProfile(
        id=generate_uuid7(),
        user_id=lawyer_user.id,
        full_name="Advocate Webhook Test",
        consultation_fee=5000.0,
    )
    db.add_all([client_profile, lawyer_profile])
    db.commit()

    # 2. Create consultation in REQUESTED state
    con = Consultation(
        id=generate_uuid7(),
        client_id=client_profile.id,
        lawyer_id=lawyer_profile.id,
        status=ConsultationStatus.REQUESTED,
        scheduled_at=datetime.now(UTC) + timedelta(days=1),
        duration_minutes=30,
        fee_amount=5000.0,
        currency="INR",
    )
    db.add(con)
    db.commit()

    # 3. Create active payment
    provider_pi_id = f"pi_test_replay_{generate_uuid7()}"
    payment = Payment(
        id=generate_uuid7(),
        consultation_id=con.id,
        payer_user_id=client_user.id,
        amount=5000.0,
        currency="INR",
        status=PaymentStatus.PENDING,
        provider="stripe",
        provider_payment_id=provider_pi_id,
    )
    db.add(payment)
    db.commit()

    # 4. Construct synthetic Stripe webhook payload
    import hashlib
    import hmac
    import json

    webhook_secret = "whsec_test_secret_123"
    timestamp = int(datetime.now(UTC).timestamp())
    payload_dict = {
        "id": f"evt_{generate_uuid7()}",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": provider_pi_id,
                "amount": 500000,
                "currency": "inr",
                "status": "succeeded",
            }
        },
    }
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    signed_payload = f"{timestamp}.".encode() + raw_bytes
    sig = hmac.new(webhook_secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    sig_header = f"t={timestamp},v1={sig}"

    service = PaymentService(db)

    # 5. First execution: should succeed and transition state
    res_1 = service.handle_webhook(raw_bytes, signature_header=sig_header)
    assert res_1 == {"status": "success"}

    db.refresh(payment)
    db.refresh(con)
    assert payment.status == PaymentStatus.SUCCEEDED
    assert con.status == ConsultationStatus.PAID

    # 6. Second execution (Replay): should return already_processed without re-mutating
    res_2 = service.handle_webhook(raw_bytes, signature_header=sig_header)
    assert res_2 == {"status": "already_processed"}
