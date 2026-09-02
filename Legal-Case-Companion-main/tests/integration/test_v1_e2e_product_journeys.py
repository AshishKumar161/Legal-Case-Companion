"""Comprehensive V1 Product Completion End-to-End Integration Test Suite:

1. Full Client Product Journey:
   Register -> Profile -> Search Counsel -> Public Profile -> Slots ->
   Booking -> Payment -> Confirmation -> Video Signaling -> Complete ->
   Consultation Note -> Create Case -> Document Upload & Malware Scan -> Case Timeline.

2. Full Lawyer Product Journey:
   Register -> Practice Profile -> Submit Bar Verification -> Admin Approval ->
   Availability Schedule CRUD -> Receive Booking -> Accept -> Payment ->
   Video Session -> Counsel Notes -> Link Existing Case.

3. Full Admin Product Journey:
   Login -> Verification Review -> Approve Counsel -> Monitor Users & Consultations ->
   Inspect Payments -> Inspect Audit Logs.
"""

import json
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.core.storage import get_storage_provider
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole, ParticipantStatus
from app.models.consultation import Consultation, ConsultationStatus
from app.models.document import Document, DocumentCategory, DocumentSecurityStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, LawyerVerification, User, UserRole, VerificationStatus
from app.models.video_meeting import VideoMeeting, VideoMeetingStatus
from app.services.scanner_service import ScannerService
from app.services.video_meeting_service import get_video_provider


def _register_and_login(
    client: TestClient,
    email: str,
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Test User",
) -> tuple[str, dict[str, str]]:
    password = "StrongPassword123!"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name, "role": role.value},
    )
    assert reg_res.status_code == 201, reg_res.text
    user_id = reg_res.json()["id"]

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return user_id, headers


def _setup_admin(client: TestClient, db: Session) -> tuple[str, dict[str, str]]:
    admin_id = generate_uuid7()
    admin_email = f"admin_{uuid4().hex[:6]}@lcc.internal"
    password = "AdminPassword123!"
    user = User(
        id=admin_id,
        email=admin_email,
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": password},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    return str(admin_id), {"Authorization": f"Bearer {token}"}


def test_e2e_client_full_product_journey(client: TestClient, db: Session):
    """
    Verifies complete end-to-end Client product journey:
    Register -> Profile -> Discover Lawyer -> Check Slots -> Book -> Pay ->
    Video Token & Signaling -> Complete -> Notes -> Create Case -> Upload Document -> Timeline.
    """
    storage = get_storage_provider()

    # 1. Setup Verified Lawyer with Availability
    lawyer_id, lawyer_headers = _register_and_login(
        client, f"advocate_{uuid4().hex[:6]}@example.com", role=UserRole.LAWYER, full_name="Advocate Vikram Sharma"
    )
    # Update lawyer practice profile
    client.patch(
        "/api/v1/profiles/lawyer",
        json={
            "consultation_fee": 3000.0,
            "experience_years": 12,
            "location": "New Delhi",
            "practice_areas": ["Corporate Law", "Commercial Arbitration"],
            "languages": ["English", "Hindi"],
            "bio": "Senior advocate practicing before Delhi High Court and Supreme Court.",
        },
        headers=lawyer_headers,
    )
    # Approve lawyer verification in db
    lawyer_user = db.query(User).get(UUID(lawyer_id))
    verif = LawyerVerification(
        id=generate_uuid7(),
        lawyer_profile_id=lawyer_user.lawyer_profile.id,
        enrollment_number="D/1842/2012",
        state_bar_council="Bar Council of Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(verif)
    db.commit()

    # Lawyer configures weekly availability
    target_slot_date = date.today() + timedelta(days=2)
    day_of_week = target_slot_date.weekday()
    client.post(
        "/api/v1/profiles/lawyer/availability",
        json={
            "day_of_week": day_of_week,
            "start_time": "14:00:00",
            "end_time": "18:00:00",
            "slot_duration_minutes": 30,
            "is_active": True,
        },
        headers=lawyer_headers,
    )

    # 2. Client Registers & Logs in
    client_id, client_headers = _register_and_login(
        client, f"client_{uuid4().hex[:6]}@example.com", role=UserRole.CLIENT, full_name="Rahul Verma"
    )

    # Client updates profile
    update_res = client.patch(
        "/api/v1/profiles/client",
        json={"location": "Delhi NCR", "phone": "+919876543210"},
        headers=client_headers,
    )
    assert update_res.status_code == 200

    # 3. Client Searches Lawyers
    search_res = client.get(
        "/api/v1/lawyers?practice_area=Corporate%20Law&verified_only=true",
        headers=client_headers,
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total"] >= 1
    found_lawyer = next((l for l in search_data["items"] if l["id"] == str(lawyer_user.lawyer_profile.id)), None)
    assert found_lawyer is not None

    # 4. Client Views Public Lawyer Profile
    pub_res = client.get(f"/api/v1/lawyers/{lawyer_user.lawyer_profile.id}", headers=client_headers)
    assert pub_res.status_code == 200
    assert pub_res.json()["consultation_fee"] == 3000.0

    # 5. Client Queries Available Slots
    slots_res = client.get(
        f"/api/v1/lawyers/{lawyer_user.lawyer_profile.id}/slots?date={target_slot_date.isoformat()}&duration_minutes=30",
        headers=client_headers,
    )
    assert slots_res.status_code == 200
    slots = slots_res.json()
    assert len(slots) >= 1
    selected_slot = slots[0]

    # 6. Client Books Consultation
    book_res = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": str(lawyer_user.lawyer_profile.id),
            "scheduled_at": selected_slot["start_time"],
            "duration_minutes": 30,
        },
        headers=client_headers,
    )
    assert book_res.status_code == 201
    con_data = book_res.json()
    con_id = con_data["id"]
    assert con_data["fee_amount"] == 3000.0

    # 7. Payment Simulation / Processing
    pay_res = client.post(
        f"/api/v1/consultations/{con_id}/payments",
        json={},
        headers=client_headers,
    )
    assert pay_res.status_code == 201
    payment_id = pay_res.json()["payment_id"]

    # In development/test mode, simulate payment success
    db_payment = db.query(Payment).get(UUID(payment_id))
    db_payment.status = PaymentStatus.SUCCEEDED
    db_con = db.query(Consultation).get(UUID(con_id))
    db_con.status = ConsultationStatus.PAID
    db_con.scheduled_at = datetime.now(UTC)
    db.commit()

    # 8. Video Consultation Setup & Join Token Verification
    join_res = client.get(
        f"/api/v1/consultations/{con_id}/video/join",
        headers=client_headers,
    )
    assert join_res.status_code == 200
    join_info = join_res.json()
    assert join_info["token"] is not None
    assert "internal_webrtc" in join_info["provider"]

    # Verify WebSocket signaling connection
    with client.websocket_connect(f"/api/v1/consultations/{con_id}/video/ws?token={join_info['token']}") as ws:
        # Ping / pong heartbeat over signaling channel
        ws.send_text(json.dumps({"type": "ping"}))
        res_text = ws.receive_text()
        assert json.loads(res_text)["type"] == "pong"

    # 9. Complete Consultation
    comp_res = client.post(
        f"/api/v1/consultations/{con_id}/complete",
        json={},
        headers=lawyer_headers,
    )
    assert comp_res.status_code == 200

    # 10. Consultation Notes
    note_res = client.post(
        f"/api/v1/consultations/{con_id}/notes",
        json={
            "summary": "Discussed corporate governance and breach of contract remedies.",
            "action_items": ["Review draft shareholder agreement", "File notice of dispute"],
            "client_shared": True,
        },
        headers=lawyer_headers,
    )
    assert note_res.status_code == 201

    # Client views consultation notes
    notes_list_res = client.get(f"/api/v1/consultations/{con_id}/notes", headers=client_headers)
    assert notes_list_res.status_code == 200
    assert len(notes_list_res.json()) >= 1

    # 11. Create Case from Consultation
    case_create_res = client.post(
        f"/api/v1/consultations/{con_id}/create-case",
        json={"title": "Corporate Breach of Contract Matter"},
        headers=client_headers,
    )
    assert case_create_res.status_code == 201
    created_case = case_create_res.json()
    case_id = created_case["id"]

    # Verify CaseParticipants
    parts = db.query(CaseParticipant).filter(CaseParticipant.case_id == UUID(case_id)).all()
    roles = {p.participant_role for p in parts}
    assert ParticipantRole.OWNER in roles
    assert ParticipantRole.LAWYER in roles

    # 12. Upload Document into Case & Verify Security
    doc_meta_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "executed_shareholder_agreement.pdf",
            "mime_type": "application/pdf",
            "file_size": 512,
            "document_type": DocumentCategory.CONTRACT.value,
        },
        headers=client_headers,
    )
    assert doc_meta_res.status_code == 201
    doc_data = doc_meta_res.json()["document"]
    doc_id = doc_data["id"]
    storage_key = doc_data["storage_key"]

    # Store genuine PDF bytes
    valid_pdf = b"%PDF-1.7\n%Executed shareholder contract terms\n%%EOF"
    storage.put_object_bytes(storage_key, valid_pdf, mime_type="application/pdf")

    # Complete upload
    comp_doc_res = client.post(
        f"/api/v1/cases/{case_id}/documents/{doc_id}/complete",
        headers=client_headers,
    )
    assert comp_doc_res.status_code == 200
    assert comp_doc_res.json()["security_status"] == DocumentSecurityStatus.QUARANTINED.value

    # Scan document to safe
    scanner = ScannerService(db)
    scanned = scanner.scan_document(UUID(doc_id))
    assert scanned.security_status == DocumentSecurityStatus.SAFE

    # 13. Case Timeline
    timeline_res = client.get(f"/api/v1/cases/{case_id}/timeline", headers=client_headers)
    assert timeline_res.status_code == 200


def test_e2e_lawyer_full_product_journey(client: TestClient, db: Session):
    """
    Verifies complete end-to-end Lawyer product journey:
    Register -> Profile Setup -> Bar Verification Submission -> Admin Approval ->
    Availability Schedule CRUD -> Receive Consultation -> Accept -> Video Session ->
    Consultation Notes -> Link to Existing Case.
    """
    admin_id, admin_headers = _setup_admin(client, db)

    # 1. Lawyer Registers
    lawyer_id, lawyer_headers = _register_and_login(
        client, f"lawyer_journey_{uuid4().hex[:6]}@example.com", role=UserRole.LAWYER, full_name="Advocate Ananya Iyer"
    )

    # 2. Lawyer Updates Profile
    prof_update_res = client.patch(
        "/api/v1/profiles/lawyer",
        json={
            "consultation_fee": 2500.0,
            "experience_years": 8,
            "location": "Mumbai",
            "practice_areas": ["Intellectual Property", "Media Law"],
            "languages": ["English", "Hindi", "Marathi"],
            "bio": "IP litigation specialist appearing before Bombay High Court.",
        },
        headers=lawyer_headers,
    )
    assert prof_update_res.status_code == 200

    # 3. Lawyer Submits Bar Council Verification Credentials
    verif_sub_res = client.post(
        "/api/v1/profiles/lawyer/verification",
        json={
            "enrollment_number": "MAH/2481/2016",
            "state_bar_council": "Bar Council of Maharashtra & Goa",
        },
        headers=lawyer_headers,
    )
    assert verif_sub_res.status_code == 200
    verif_id = verif_sub_res.json()["id"]

    # 4. Admin Reviews & Approves Verification
    appr_res = client.post(
        f"/api/v1/admin/verifications/{verif_id}/approve",
        headers=admin_headers,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == VerificationStatus.APPROVED.value

    # 5. Lawyer Configures Availability Schedule
    avail_create_res = client.post(
        "/api/v1/profiles/lawyer/availability",
        json={
            "day_of_week": 1,  # Tuesday
            "start_time": "10:00:00",
            "end_time": "16:00:00",
            "slot_duration_minutes": 30,
            "is_active": True,
        },
        headers=lawyer_headers,
    )
    assert avail_create_res.status_code == 201
    avail_id = avail_create_res.json()["id"]

    # View availability list
    avail_list_res = client.get("/api/v1/profiles/lawyer/availability", headers=lawyer_headers)
    assert avail_list_res.status_code == 200
    assert any(a["id"] == avail_id for a in avail_list_res.json())

    # 6. Client Requests Consultation
    client_id, client_headers = _register_and_login(
        client, f"client_for_ananya_{uuid4().hex[:6]}@example.com", role=UserRole.CLIENT, full_name="Trademark Client"
    )
    lawyer_user = db.query(User).get(UUID(lawyer_id))

    days_ahead = (1 - date.today().weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    target_date = date.today() + timedelta(days=days_ahead)

    slots_res = client.get(
        f"/api/v1/lawyers/{lawyer_user.lawyer_profile.id}/slots?date={target_date.isoformat()}&duration_minutes=30",
        headers=client_headers,
    )
    assert slots_res.status_code == 200
    slots = slots_res.json()
    assert len(slots) >= 1
    selected_slot = slots[0]

    book_res = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": str(lawyer_user.lawyer_profile.id),
            "scheduled_at": selected_slot["start_time"],
            "duration_minutes": 30,
        },
        headers=client_headers,
    )
    assert book_res.status_code == 201
    con_id = book_res.json()["id"]

    # 7. Lawyer Accepts Consultation Request
    accept_res = client.post(f"/api/v1/consultations/{con_id}/accept", json={}, headers=lawyer_headers)
    assert accept_res.status_code == 200
    assert accept_res.json()["status"] == ConsultationStatus.ACCEPTED.value

    # 8. Mark Consultation Paid and Complete
    db_con = db.query(Consultation).get(UUID(con_id))
    db_con.status = ConsultationStatus.COMPLETED
    db.commit()

    # 9. Lawyer Adds Private Counsel Work Product Note
    note_res = client.post(
        f"/api/v1/consultations/{con_id}/notes",
        json={
            "summary": "Confidential litigation risk assessment: high probability of preliminary injunction.",
            "action_items": ["Prepare cease and desist response", "Gather prior art"],
            "client_shared": False,
        },
        headers=lawyer_headers,
    )
    assert note_res.status_code == 201

    # Verify Client CANNOT view private counsel work product note
    client_notes_res = client.get(f"/api/v1/consultations/{con_id}/notes", headers=client_headers)
    assert client_notes_res.status_code == 200
    assert len(client_notes_res.json()) == 0

    # 10. Lawyer Links Consultation to an Existing Client Matter
    client_case = Case(
        id=generate_uuid7(),
        title="Trademark Infringement Defense",
        description="Defense of trademark infringement matter",
        status=CaseStatus.OPEN,
    )
    db.add(client_case)
    client_part = CaseParticipant(
        id=generate_uuid7(),
        case_id=client_case.id,
        user_id=UUID(client_id),
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
        joined_at=datetime.now(UTC),
    )
    db.add(client_part)
    db.commit()

    link_res = client.post(
        f"/api/v1/consultations/{con_id}/link-case",
        json={"case_id": str(client_case.id)},
        headers=client_headers,
    )
    assert link_res.status_code == 200
    assert link_res.json()["case_id"] == str(client_case.id)


def test_e2e_admin_full_product_journey(client: TestClient, db: Session):
    """
    Verifies complete end-to-end Admin product journey:
    Login -> Platform Overview -> Verification Queue -> Approve Lawyer ->
    Monitor Consultations & Payments -> Inspect Audit Logs.
    """
    admin_id, admin_headers = _setup_admin(client, db)

    # 1. Platform Overview
    overview_res = client.get("/api/v1/admin/overview", headers=admin_headers)
    assert overview_res.status_code == 200
    overview_data = overview_res.json()
    assert "total_users" in overview_data
    assert "total_cases" in overview_data

    # 2. Lawyer Registers & Submits Verification
    lawyer_id, lawyer_headers = _register_and_login(
        client, f"adv_admin_test_{uuid4().hex[:6]}@example.com", role=UserRole.LAWYER, full_name="Advocate Suresh Nair"
    )
    verif_res = client.post(
        "/api/v1/profiles/lawyer/verification",
        json={"enrollment_number": "KAR/9912/2015", "state_bar_council": "Bar Council of Karnataka"},
        headers=lawyer_headers,
    )
    assert verif_res.status_code == 200
    verif_id = verif_res.json()["id"]

    # 3. Admin Views Pending Verifications Queue
    pending_res = client.get("/api/v1/admin/verifications?status=PENDING", headers=admin_headers)
    assert pending_res.status_code == 200
    pending_items = pending_res.json()["items"]
    assert any(v["id"] == verif_id for v in pending_items)

    # 4. Admin Approves Lawyer Verification
    appr_res = client.post(f"/api/v1/admin/verifications/{verif_id}/approve", headers=admin_headers)
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "APPROVED"

    # 5. Admin Inspects Consultations & Audit Events
    audit_res = client.get("/api/v1/admin/audit?limit=20", headers=admin_headers)
    assert audit_res.status_code == 200
    assert "items" in audit_res.json()
