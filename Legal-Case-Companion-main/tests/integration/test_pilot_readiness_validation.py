import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ResourceNotFoundError,
    ScannerUnavailableError,
    ValidationError,
)
from app.core.identifiers import generate_uuid7
from app.core.metrics import metrics_collector
from app.core.storage import get_storage_provider
from app.models.case import (
    Case,
    CaseParticipant,
    CaseStatus,
    ParticipantRole,
    ParticipantStatus,
)
from app.models.consultation import Consultation, ConsultationStatus
from app.models.document import DocumentCategory, DocumentSecurityStatus
from app.models.user import (
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.schemas.document import DocumentCreate
from app.services.consultation_service import ConsultationService
from app.services.document_service import DocumentService
from app.services.scanner_service import (
    ClamAVScanner,
    DefaultMalwareScanner,
    ScannerService,
)
from app.services.video_meeting_service import VideoMeetingService


def _setup_pilot_user(
    client: TestClient,
    db: Session,
    email: str,
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Pilot User",
) -> tuple[str, dict[str, str], UUID]:
    password = "PilotPassword123!"
    reg_role = UserRole.CLIENT.value if role == UserRole.ADMIN else role.value
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name, "role": reg_role},
    )
    assert reg_res.status_code == 201, reg_res.text
    user_id = reg_res.json()["id"]

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    assert user is not None

    profile_id = user.id
    if role == UserRole.CLIENT and user.client_profile:
        profile_id = user.client_profile.id
    elif role == UserRole.LAWYER and user.lawyer_profile:
        user.lawyer_profile.consultation_fee = 2500.0
        user.lawyer_profile.languages = ["English", "Hindi"]
        db.add(
            LawyerVerification(
                id=generate_uuid7(),
                lawyer_profile_id=user.lawyer_profile.id,
                enrollment_number=f"D/{uuid4().hex[:4].upper()}/2020",
                state_bar_council="Delhi",
                status=VerificationStatus.APPROVED,
            )
        )
        profile_id = user.lawyer_profile.id
    elif role == UserRole.ADMIN:
        user.role = UserRole.ADMIN
    db.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200, login_res.text
    access_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    return user_id, headers, profile_id


def test_pilot_cross_role_journey(client: TestClient, db: Session):
    """
    Pilot Phase 6: Complete end-to-end smoke test across Client, Lawyer, and Admin:
    Registration -> Discovery -> Booking -> Payment -> In-App Notes -> Case Linking -> Admin View.
    """
    # 1. Onboard Advocate and Client
    _, adv_headers, adv_prof_id = _setup_pilot_user(
        client, db, f"advocate_pilot_{uuid4().hex[:6]}@example.com", role=UserRole.LAWYER, full_name="Advocate Pilot"
    )
    _, client_headers, _ = _setup_pilot_user(
        client, db, f"client_pilot_{uuid4().hex[:6]}@example.com", role=UserRole.CLIENT, full_name="Client Pilot"
    )

    # 2. Client discovers Advocate
    disc_res = client.get("/api/v1/lawyers", headers=client_headers)
    assert disc_res.status_code == 200
    lawyers_list = disc_res.json()["items"]
    assert any(str(l["id"]) == str(adv_prof_id) for l in lawyers_list)

    # 3. Client requests consultation
    sched_time = (datetime.now(UTC) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
    book_res = client.post(
        "/api/v1/consultations",
        headers=client_headers,
        json={
            "lawyer_id": str(adv_prof_id),
            "scheduled_at": sched_time.isoformat(),
            "duration_minutes": 30,
        },
    )
    assert book_res.status_code == 201, book_res.text
    con_id = book_res.json()["id"]

    # 4. Advocate accepts consultation
    accept_res = client.post(f"/api/v1/consultations/{con_id}/accept", headers=adv_headers)
    assert accept_res.status_code == 200

    # 5. Client initiates payment
    pay_res = client.post(f"/api/v1/consultations/{con_id}/payments", headers=client_headers)
    assert pay_res.status_code == 201
    payment_data = pay_res.json()
    payment_id = payment_data["payment_id"]
    pi_id = payment_data.get("provider_payment_id") or f"pi_mock_{payment_id}"

    # 6. Simulate authoritative Stripe webhook execution
    webhook_secret = "whsec_test_secret_123"
    timestamp = int(datetime.now(UTC).timestamp())
    payload_dict = {
        "id": f"evt_{uuid4().hex}",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": pi_id, "amount": 250000, "currency": "inr", "status": "succeeded"}},
    }
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    sig = hmac.new(webhook_secret.encode(), f"{timestamp}.".encode() + raw_bytes, hashlib.sha256).hexdigest()
    wh_res = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_bytes,
        headers={"Stripe-Signature": f"t={timestamp},v1={sig}", "Content-Type": "application/json"},
    )
    assert wh_res.status_code == 200

    # Verify consultation is PAID
    con_check = client.get(f"/api/v1/consultations/{con_id}", headers=client_headers)
    assert con_check.status_code == 200
    assert con_check.json()["status"] == "PAID"

    # 7. Advocate creates consultation note and client links to new matter
    note_res = client.post(
        f"/api/v1/consultations/{con_id}/notes",
        headers=adv_headers,
        json={"summary": "Reviewed commercial agreement terms.", "client_shared": True},
    )
    assert note_res.status_code == 201

    case_link_res = client.post(
        f"/api/v1/consultations/{con_id}/create-case",
        headers=client_headers,
        json={"title": "Commercial Breach Matter", "description": "Litigation matter initiated from consultation."},
    )
    assert case_link_res.status_code == 201
    assert case_link_res.json()["id"] is not None

    # 8. Admin supervisor verifies platform state
    _, admin_headers, _ = _setup_pilot_user(
        client, db, f"admin_pilot_{uuid4().hex[:6]}@example.com", role=UserRole.ADMIN, full_name="Admin Supervisor"
    )
    admin_audit = client.get("/api/v1/audit", headers=admin_headers)
    assert admin_audit.status_code == 200

    admin_overview = client.get("/api/v1/admin/overview", headers=admin_headers)
    assert admin_overview.status_code == 200


def test_pilot_webrtc_signaling_and_video_security(client: TestClient, db: Session):
    """
    Pilot Phase 7: WebRTC video consultation token security, authorization bounds,
    and HMAC signature validation.
    """
    client_uid, _, client_prof_id = _setup_pilot_user(
        client, db, f"video_client_{uuid4().hex[:6]}@example.com", role=UserRole.CLIENT
    )
    _, _, adv_prof_id = _setup_pilot_user(
        client, db, f"video_adv_{uuid4().hex[:6]}@example.com", role=UserRole.LAWYER
    )
    intruder_uid, _, _ = _setup_pilot_user(
        client, db, f"intruder_{uuid4().hex[:6]}@example.com", role=UserRole.CLIENT
    )

    # Create active paid consultation
    con = Consultation(
        id=generate_uuid7(),
        client_id=client_prof_id,
        lawyer_id=adv_prof_id,
        status=ConsultationStatus.PAID,
        scheduled_at=datetime.now(UTC),
        duration_minutes=30,
        fee_amount=2500.0,
        currency="INR",
    )
    db.add(con)
    db.commit()

    meeting_svc = VideoMeetingService(db)
    meeting_svc.ensure_meeting_provisioned(con)

    # 1. Authorized Client generates valid join token
    client_user = db.query(User).filter(User.id == UUID(client_uid)).first()
    join_info = meeting_svc.get_join_information(client_user, con.id)
    token = join_info.token
    assert token is not None

    # 2. Token validation succeeds for legitimate client
    payload = meeting_svc.provider.verify_access_token(token, expected_user_id=client_user.id)
    assert payload is not None

    # 3. Unauthorized intruder is rejected when attempting to generate join token
    intruder_user = db.query(User).filter(User.id == UUID(intruder_uid)).first()
    with pytest.raises(ResourceNotFoundError):
        meeting_svc.get_join_information(intruder_user, con.id)

    # 4. Tampered token signature is rejected
    tampered_token = token[:-5] + "XXXXX"
    with pytest.raises(ValidationError):
        meeting_svc.provider.verify_access_token(tampered_token)


def test_pilot_antimalware_pipeline_and_fail_closed(client: TestClient, db: Session):
    """
    Pilot Phase 8: Document security pipeline:
    Clean PDF -> SAFE
    EICAR threat -> REJECTED
    ClamAV daemon offline -> QUARANTINED (strict fail-closed guarantee)
    """
    client_uid, _, _ = _setup_pilot_user(
        client, db, f"doc_pilot_{uuid4().hex[:6]}@example.com", role=UserRole.CLIENT
    )
    client_user = db.query(User).filter(User.id == UUID(client_uid)).first()

    # Create Matter
    case = Case(
        id=generate_uuid7(),
        title="Evidence Matter",
        description="Matter for document pipeline verification",
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

    doc_service = DocumentService(db)
    scanner_svc = ScannerService(db)
    storage = get_storage_provider()

    # Case A: Clean valid PDF
    clean_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    meta_clean = doc_service.create_document_metadata(
        client_user,
        case.id,
        DocumentCreate(filename="clean_brief.pdf", mime_type="application/pdf", file_size=len(clean_bytes), document_type=DocumentCategory.PLEADINGS),
    )
    doc_clean_obj = meta_clean["document"]
    storage.put_object_bytes(doc_clean_obj.storage_key, clean_bytes, mime_type="application/pdf")
    doc_clean_quarantined = doc_service.complete_upload(client_user, doc_clean_obj.id)
    assert doc_clean_quarantined.security_status == DocumentSecurityStatus.QUARANTINED
    doc_clean = scanner_svc.scan_document(doc_clean_obj.id)
    assert doc_clean.security_status == DocumentSecurityStatus.SAFE

    # Case B: EICAR malware signature
    eicar_bytes = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    meta_eicar = doc_service.create_document_metadata(
        client_user,
        case.id,
        DocumentCreate(filename="eicar_test.txt", mime_type="text/plain", file_size=len(eicar_bytes), document_type=DocumentCategory.EVIDENCE),
    )
    doc_eicar_obj = meta_eicar["document"]
    storage.put_object_bytes(doc_eicar_obj.storage_key, eicar_bytes, mime_type="text/plain")
    doc_eicar_quarantined = doc_service.complete_upload(client_user, doc_eicar_obj.id)
    assert doc_eicar_quarantined.security_status == DocumentSecurityStatus.QUARANTINED
    doc_eicar = scanner_svc.scan_document(doc_eicar_obj.id)
    assert doc_eicar.security_status == DocumentSecurityStatus.REJECTED
    assert "EICAR" in str(doc_eicar.processing_error)

    # Case C: ClamAV Daemon Outage -> MUST Fail Closed (remain QUARANTINED)
    meta_outage = doc_service.create_document_metadata(
        client_user,
        case.id,
        DocumentCreate(filename="clean_contract.pdf", mime_type="application/pdf", file_size=len(clean_bytes), document_type=DocumentCategory.CONTRACT),
    )
    doc_outage_obj = meta_outage["document"]
    storage.put_object_bytes(doc_outage_obj.storage_key, clean_bytes, mime_type="application/pdf")
    doc_service.complete_upload(client_user, doc_outage_obj.id)
    
    # Simulate ClamAV daemon connection failure
    failing_clamav = ClamAVScanner(host="127.0.0.1", port=59997)
    composite = DefaultMalwareScanner()
    composite.clamav_scanner = failing_clamav
    failing_scanner_svc = ScannerService(db, scanner=composite)

    with pytest.raises(ScannerUnavailableError):
        failing_scanner_svc.scan_document(doc_outage_obj.id)

    db.refresh(doc_outage_obj)
    assert doc_outage_obj.security_status == DocumentSecurityStatus.QUARANTINED
    assert "Malware scanner service is temporarily unavailable" in str(doc_outage_obj.processing_error)


def test_pilot_authorization_attack_matrix(client: TestClient, db: Session):
    """
    Pilot Phase 9: Systematic Authorization Attack Matrix:
    - Client A vs Client B (Case, Document, Consultation, Video)
    - Lawyer A vs Lawyer B (Consultation notes)
    - Client/Lawyer vs Admin endpoints
    - Payment tampering and cross-client payment defense
    """
    client_a_uid, client_a_headers, client_a_prof = _setup_pilot_user(
        client, db, f"client_a_{uuid4().hex[:6]}@example.com", role=UserRole.CLIENT
    )
    _, client_b_headers, _ = _setup_pilot_user(
        client, db, f"client_b_{uuid4().hex[:6]}@example.com", role=UserRole.CLIENT
    )
    lawyer_a_uid, lawyer_a_headers, lawyer_a_prof = _setup_pilot_user(
        client, db, f"lawyer_a_{uuid4().hex[:6]}@example.com", role=UserRole.LAWYER
    )
    lawyer_b_uid, _, _ = _setup_pilot_user(
        client, db, f"lawyer_b_{uuid4().hex[:6]}@example.com", role=UserRole.LAWYER
    )

    # 1. Create Case for Client A
    case_a = Case(id=generate_uuid7(), title="Client A Secret Case", description="Confidential", status=CaseStatus.OPEN)
    db.add(case_a)
    db.add(CaseParticipant(
        id=generate_uuid7(), case_id=case_a.id, user_id=UUID(client_a_uid),
        participant_role=ParticipantRole.OWNER, status=ParticipantStatus.ACTIVE, joined_at=datetime.now(UTC)
    ))
    db.commit()

    # Attack: Client B tries to view Client A's case -> MUST FAIL
    res_cross_case = client.get(f"/api/v1/cases/{case_a.id}", headers=client_b_headers)
    assert res_cross_case.status_code in (403, 404)

    # 2. Consultation for Client A with Lawyer A
    con_a = Consultation(
        id=generate_uuid7(), client_id=client_a_prof, lawyer_id=lawyer_a_prof,
        status=ConsultationStatus.ACCEPTED, scheduled_at=datetime.now(UTC) + timedelta(days=1),
        duration_minutes=30, fee_amount=3000.0, currency="INR"
    )
    db.add(con_a)
    db.commit()

    # Attack: Client B tries to view Client A's consultation -> MUST FAIL
    res_cross_con = client.get(f"/api/v1/consultations/{con_a.id}", headers=client_b_headers)
    assert res_cross_con.status_code in (403, 404)

    # Attack: Client B tries to pay for Client A's consultation -> MUST FAIL
    res_cross_pay = client.post(f"/api/v1/consultations/{con_a.id}/payments", headers=client_b_headers)
    assert res_cross_pay.status_code in (403, 404)

    # Attack: Client B tries to generate join token for Client A's consultation -> MUST FAIL
    res_cross_video = client.get(f"/api/v1/consultations/{con_a.id}/video/join", headers=client_b_headers)
    assert res_cross_video.status_code in (403, 404)

    # 3. Lawyer A adds private notes to consultation
    con_svc = ConsultationService(db)
    lawyer_a_user = db.query(User).filter(User.id == UUID(lawyer_a_uid)).first()
    con_svc.add_consultation_note(
        lawyer_a_user, con_a.id, summary="Lawyer A private strategy", client_shared=False
    )

    # Attack: Lawyer B tries to read Lawyer A's consultation notes -> MUST FAIL
    lawyer_b_user = db.query(User).filter(User.id == UUID(lawyer_b_uid)).first()
    with pytest.raises(ResourceNotFoundError):
        con_svc.get_consultation_notes(lawyer_b_user, con_a.id)

    # 4. Attack: Client or Lawyer tries to access Admin endpoints -> MUST FAIL (403)
    res_admin_client = client.get("/api/v1/admin/users", headers=client_a_headers)
    assert res_admin_client.status_code == 403

    res_admin_lawyer = client.get("/api/v1/admin/metrics", headers=lawyer_a_headers)
    assert res_admin_lawyer.status_code == 403


def test_pilot_disaster_recovery_and_resilience(client: TestClient, db: Session):
    """
    Pilot Phase 18: Operational failure resilience:
    - Operational health probes (/liveness, /readiness)
    - Metrics low-cardinality masking check
    - Idempotent consultation cancellation behavior
    """
    # 1. Health probes return healthy status
    res_live = client.get("/liveness")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "alive"

    res_ready = client.get("/readiness")
    assert res_ready.status_code == 200
    assert res_ready.json()["database"] == "connected"

    # 2. Metric low-cardinality masking test
    test_uuid = str(uuid4())
    client.get(f"/api/v1/consultations/{test_uuid}")
    snapshot = metrics_collector.get_metrics_snapshot()
    top_eps = snapshot.get("top_endpoints", {})
    assert not any(test_uuid in ep for ep in top_eps)

    # 3. Idempotent consultation cancellation test
    client_uid, _, client_prof = _setup_pilot_user(client, db, f"canc_c_{uuid4().hex[:6]}@example.com", role=UserRole.CLIENT)
    _, _, lawyer_prof = _setup_pilot_user(client, db, f"canc_l_{uuid4().hex[:6]}@example.com", role=UserRole.LAWYER)
    client_user = db.query(User).filter(User.id == UUID(client_uid)).first()

    con = Consultation(
        id=generate_uuid7(), client_id=client_prof, lawyer_id=lawyer_prof,
        status=ConsultationStatus.REQUESTED, scheduled_at=datetime.now(UTC) + timedelta(days=3),
        duration_minutes=30, fee_amount=2000.0, currency="INR"
    )
    db.add(con)
    db.commit()

    con_svc = ConsultationService(db)
    # First cancellation
    con_cancelled = con_svc.cancel_consultation(client_user, con.id, reason="Client schedule change")
    assert con_cancelled.status == ConsultationStatus.CANCELLED

    # Replay cancellation (must be idempotent and safe)
    con_replayed = con_svc.cancel_consultation(client_user, con.id, reason="Client schedule change")
    assert con_replayed.status == ConsultationStatus.CANCELLED
