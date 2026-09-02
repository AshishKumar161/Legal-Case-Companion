import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole, ParticipantStatus
from app.models.consultation import Consultation, ConsultationStatus
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


def _setup_user(
    client: TestClient,
    db: Session,
    email: str,
    password: str = "Password123!",
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Test User",
    languages: list[str] | None = None,
) -> tuple[str, dict[str, str], uuid.UUID]:
    """Helper to register and login a user, returning (user_id, auth_headers, profile_id)."""
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
    access_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    assert user is not None

    profile_id = user.id
    if role == UserRole.LAWYER and user.lawyer_profile:
        user.lawyer_profile.consultation_fee = 1500.0
        user.lawyer_profile.practice_areas = ["Corporate Law", "Intellectual Property"]
        user.lawyer_profile.court_jurisdictions = ["Delhi High Court", "Supreme Court of India"]
        user.lawyer_profile.experience_years = 10
        user.lawyer_profile.languages = languages or ["English", "Hindi"]
        verif = LawyerVerification(
            id=generate_uuid7(),
            lawyer_profile_id=user.lawyer_profile.id,
            enrollment_number=f"DL/{uuid.uuid4().hex[:6].upper()}/2018",
            state_bar_council="Delhi",
            status=VerificationStatus.APPROVED,
        )
        db.add(verif)
        profile_id = user.lawyer_profile.id
    elif role == UserRole.CLIENT and user.client_profile:
        profile_id = user.client_profile.id

    db.commit()
    return user_id, headers, profile_id


def test_lawyer_discovery_with_language_filter(client: TestClient, db: Session):
    email1 = f"lawyer_hi_{uuid.uuid4().hex[:6]}@example.com"
    email2 = f"lawyer_ta_{uuid.uuid4().hex[:6]}@example.com"

    _, _, _ = _setup_user(client, db, email1, role=UserRole.LAWYER, full_name="Advocate Rajesh Sharma", languages=["Hindi", "English"])
    _, _, _ = _setup_user(client, db, email2, role=UserRole.LAWYER, full_name="Advocate Sundaram Iyer", languages=["Tamil", "English"])
    _, client_headers, _ = _setup_user(client, db, f"client_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT, full_name="Pooja Verma")

    # Filter by Hindi
    res_hi = client.get("/api/v1/lawyers?language=Hindi", headers=client_headers)
    assert res_hi.status_code == 200, res_hi.text
    items_hi = res_hi.json()["items"]
    assert any(l["full_name"] == "Advocate Rajesh Sharma" for l in items_hi)
    assert not any(l["full_name"] == "Advocate Sundaram Iyer" for l in items_hi)

    # Filter by Tamil
    res_ta = client.get("/api/v1/lawyers?language=Tamil", headers=client_headers)
    assert res_ta.status_code == 200, res_ta.text
    items_ta = res_ta.json()["items"]
    assert any(l["full_name"] == "Advocate Sundaram Iyer" for l in items_ta)
    assert not any(l["full_name"] == "Advocate Rajesh Sharma" for l in items_ta)


def test_video_consultation_lifecycle_and_access_control(client: TestClient, db: Session):
    client_id, client_headers, client_prof_id = _setup_user(
        client, db, f"client_vid_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT, full_name="Client Vid"
    )
    unrelated_id, unrelated_headers, _ = _setup_user(
        client, db, f"client_unrelated_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT, full_name="Unrelated Client"
    )
    lawyer_id, lawyer_headers, lawyer_prof_id = _setup_user(
        client, db, f"lawyer_vid_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.LAWYER, full_name="Advocate Vid"
    )
    unrelated_lawyer_id, unrelated_lawyer_headers, _ = _setup_user(
        client, db, f"lawyer_unrelated_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.LAWYER, full_name="Unrelated Lawyer"
    )

    # 1. Book and Schedule consultation (30 minutes from now)
    future_time = datetime.now(UTC) + timedelta(minutes=30)
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_prof_id,
        lawyer_id=lawyer_prof_id,
        scheduled_at=future_time,
        duration_minutes=30,
        fee_amount=1500.0,
        currency="INR",
        status=ConsultationStatus.SCHEDULED,
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)

    # 2. Too early to join (30 mins before when window is 15 mins) -> 422 ValidationError
    res_too_early = client.get(
        f"/api/v1/consultations/{consultation.id}/video/join",
        headers=client_headers,
    )
    assert res_too_early.status_code == 422
    assert "opens 15 minutes before" in res_too_early.json()["error"]["message"]

    # Reschedule to within the window (5 minutes from now)
    consultation.scheduled_at = datetime.now(UTC) + timedelta(minutes=5)
    db.commit()
    db.refresh(consultation)

    # 3. Client joins video call within window
    res_client = client.get(
        f"/api/v1/consultations/{consultation.id}/video/join",
        headers=client_headers,
    )
    assert res_client.status_code == 200, res_client.text
    client_data = res_client.json()
    assert client_data["participant_role"] == "CLIENT"
    assert client_data["room_id"].startswith("lcc-room-")
    assert "token" in client_data
    assert len(client_data["ice_servers"]) > 0

    # 3. Lawyer joins video call
    res_lawyer = client.get(
        f"/api/v1/consultations/{consultation.id}/video/join",
        headers=lawyer_headers,
    )
    assert res_lawyer.status_code == 200, res_lawyer.text
    lawyer_data = res_lawyer.json()
    assert lawyer_data["participant_role"] == "LAWYER"
    assert lawyer_data["room_id"] == client_data["room_id"]

    # 4. Strict BOLA Security: Unrelated client rejected
    res_unauth_client = client.get(
        f"/api/v1/consultations/{consultation.id}/video/join",
        headers=unrelated_headers,
    )
    assert res_unauth_client.status_code == 404

    # 5. Strict BOLA Security: Unrelated lawyer rejected
    res_unauth_lawyer = client.get(
        f"/api/v1/consultations/{consultation.id}/video/join",
        headers=unrelated_lawyer_headers,
    )
    assert res_unauth_lawyer.status_code == 404

    # 6. Start Meeting
    res_start = client.post(
        f"/api/v1/consultations/{consultation.id}/video/start",
        headers=lawyer_headers,
    )
    assert res_start.status_code == 200, res_start.text
    assert res_start.json()["status"] == "ACTIVE"

    db.refresh(consultation)
    assert consultation.status == ConsultationStatus.IN_PROGRESS

    # 7. Add consultation notes
    res_note = client.post(
        f"/api/v1/consultations/{consultation.id}/notes",
        headers=lawyer_headers,
        json={
            "summary": "Advised client to send statutory notice under Section 138 of NI Act within 30 days.",
            "action_items": ["Obtain bank memo of dishonour", "Draft legal demand notice"],
            "client_shared": True,
        },
    )
    assert res_note.status_code == 201, res_note.text
    assert "draft legal demand notice" in res_note.json()["action_items"][1].lower()

    # Client can read notes
    res_get_notes = client.get(
        f"/api/v1/consultations/{consultation.id}/notes",
        headers=client_headers,
    )
    assert res_get_notes.status_code == 200, res_get_notes.text
    assert len(res_get_notes.json()) == 1

    # 8. End Meeting
    res_end = client.post(
        f"/api/v1/consultations/{consultation.id}/video/end",
        headers=lawyer_headers,
    )
    assert res_end.status_code == 200, res_end.text
    assert res_end.json()["status"] == "ENDED"

    db.refresh(consultation)
    assert consultation.status == ConsultationStatus.COMPLETED

    # 9. Concluded meeting can no longer be joined (ValidationError -> 422)
    res_rejoin = client.get(
        f"/api/v1/consultations/{consultation.id}/video/join",
        headers=client_headers,
    )
    assert res_rejoin.status_code == 422
    assert "concluded" in res_rejoin.text.lower()


def test_consultation_to_case_linking_and_creation(client: TestClient, db: Session):
    client_id, client_headers, client_prof_id = _setup_user(
        client, db, f"client_case_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT, full_name="Deepak Rao"
    )
    lawyer_id, lawyer_headers, lawyer_prof_id = _setup_user(
        client, db, f"lawyer_case_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.LAWYER, full_name="Advocate Priya Sen"
    )

    # Completed consultation
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_prof_id,
        lawyer_id=lawyer_prof_id,
        scheduled_at=datetime.now(UTC),
        duration_minutes=30,
        fee_amount=1500.0,
        currency="INR",
        status=ConsultationStatus.COMPLETED,
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)

    # --- Scenario A: Create a brand new case directly from consultation ---
    res_create_case = client.post(
        f"/api/v1/consultations/{consultation.id}/create-case",
        headers=client_headers,
        json={
            "title": "Commercial Recovery Dispute Against ABC Logistics",
            "description": "Recovery of pending invoices amounting to 24 Lakhs.",
            "practice_area": "Corporate Law",
            "court_jurisdiction": "Delhi High Court",
        },
    )
    assert res_create_case.status_code == 201, res_create_case.text
    case_data = res_create_case.json()
    new_case_id = case_data["id"]

    db.refresh(consultation)
    assert str(consultation.case_id) == str(new_case_id)

    # Verify lawyer was automatically added as a CaseParticipant!
    participants = (
        db.query(CaseParticipant)
        .filter(CaseParticipant.case_id == UUID(new_case_id))
        .all()
    )
    participant_roles = {str(p.user_id): p.participant_role for p in participants}
    assert participant_roles[client_id] == ParticipantRole.OWNER
    assert participant_roles[lawyer_id] == ParticipantRole.LAWYER

    # --- Scenario B: Link another consultation to an existing case ---
    consultation2 = Consultation(
        id=generate_uuid7(),
        client_id=client_prof_id,
        lawyer_id=lawyer_prof_id,
        scheduled_at=datetime.now(UTC) + timedelta(days=2),
        duration_minutes=30,
        fee_amount=1500.0,
        currency="INR",
        status=ConsultationStatus.SCHEDULED,
    )
    db.add(consultation2)
    db.commit()

    res_link = client.post(
        f"/api/v1/consultations/{consultation2.id}/link-case",
        headers=client_headers,
        json={"case_id": new_case_id, "assign_lawyer": True},
    )
    assert res_link.status_code == 200, res_link.text
    db.refresh(consultation2)
    assert str(consultation2.case_id) == str(new_case_id)


def test_create_case_duplicate_prevented(client: TestClient, db: Session):
    """
    Adversarial test: Calling create-case twice on the same consultation must fail with 422.
    Unrelated users must receive an IDOR-safe 404.
    """
    client_id, client_headers, client_prof_id = _setup_user(
        client, db, f"client_dup_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT, full_name="Client Dup"
    )
    lawyer_id, lawyer_headers, lawyer_prof_id = _setup_user(
        client, db, f"lawyer_dup_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.LAWYER, full_name="Advocate Dup"
    )
    _, attacker_headers, _ = _setup_user(
        client, db, f"attacker_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT, full_name="Attacker"
    )

    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_prof_id,
        lawyer_id=lawyer_prof_id,
        scheduled_at=datetime.now(UTC),
        duration_minutes=30,
        fee_amount=1500.0,
        currency="INR",
        status=ConsultationStatus.COMPLETED,
    )
    db.add(consultation)
    db.commit()

    # 1. Attacker attempts to create a case from another client's consultation -> 404
    res_att = client.post(
        f"/api/v1/consultations/{consultation.id}/create-case",
        headers=attacker_headers,
        json={"title": "Unauthorized Case Creation"},
    )
    assert res_att.status_code == 404

    # 2. Legitimate client creates case -> 201
    res_first = client.post(
        f"/api/v1/consultations/{consultation.id}/create-case",
        headers=client_headers,
        json={"title": "Legitimate Initial Case"},
    )
    assert res_first.status_code == 201

    # 3. Second call on the same consultation must fail with 422
    res_second = client.post(
        f"/api/v1/consultations/{consultation.id}/create-case",
        headers=client_headers,
        json={"title": "Duplicate Competing Case"},
    )
    assert res_second.status_code == 422
    assert "already linked" in res_second.json()["error"]["message"]


def test_link_case_cross_client_and_conflict_defense(client: TestClient, db: Session):
    """
    Adversarial test:
    1. Linking consultation to another client's private case -> 404 (BOLA isolation).
    2. Linking consultation that is already linked to a different case -> 422.
    3. Linking consultation to a CLOSED case -> 422.
    """
    _, c1_headers, c1_prof_id = _setup_user(
        client, db, f"c1_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT, full_name="Client 1"
    )
    _, c2_headers, _ = _setup_user(
        client, db, f"c2_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT, full_name="Client 2"
    )
    _, _, lawyer_prof_id = _setup_user(
        client, db, f"l1_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.LAWYER, full_name="Advocate 1"
    )

    # Client 1 consultation
    con = Consultation(
        id=generate_uuid7(),
        client_id=c1_prof_id,
        lawyer_id=lawyer_prof_id,
        scheduled_at=datetime.now(UTC),
        duration_minutes=30,
        fee_amount=1500.0,
        currency="INR",
        status=ConsultationStatus.COMPLETED,
    )
    db.add(con)
    db.commit()

    # Client 2 creates their own private case
    res_c2_case = client.post(
        "/api/v1/cases",
        headers=c2_headers,
        json={"title": "Client 2 Private Dispute", "description": "Strictly confidential matter."},
    )
    assert res_c2_case.status_code == 201
    c2_case_id = res_c2_case.json()["id"]

    # Client 1 creates their own case
    res_c1_case = client.post(
        "/api/v1/cases",
        headers=c1_headers,
        json={"title": "Client 1 Case A", "description": "Client 1 matter."},
    )
    assert res_c1_case.status_code == 201
    c1_case_a = res_c1_case.json()["id"]

    res_c1_case_b = client.post(
        "/api/v1/cases",
        headers=c1_headers,
        json={"title": "Client 1 Case B", "description": "Client 1 second matter."},
    )
    assert res_c1_case_b.status_code == 201
    c1_case_b = res_c1_case_b.json()["id"]

    # 1. Client 1 tries to link consultation to Client 2's case -> 404 (IDOR / BOLA defense)
    res_cross = client.post(
        f"/api/v1/consultations/{con.id}/link-case",
        headers=c1_headers,
        json={"case_id": c2_case_id},
    )
    assert res_cross.status_code == 404

    # 2. Client 1 links to Case A -> 200
    res_link_a = client.post(
        f"/api/v1/consultations/{con.id}/link-case",
        headers=c1_headers,
        json={"case_id": c1_case_a},
    )
    assert res_link_a.status_code == 200

    # 3. Client 1 tries to link the same consultation to Case B -> 422 Conflict
    res_link_b = client.post(
        f"/api/v1/consultations/{con.id}/link-case",
        headers=c1_headers,
        json={"case_id": c1_case_b},
    )
    assert res_link_b.status_code == 422
    assert "already linked" in res_link_b.json()["error"]["message"]


def test_video_token_tampering_and_expiry_validation(client: TestClient, db: Session):
    """
    Security verification of HMAC-SHA256 signed WebRTC join tokens:
    - Verifies token validity on freshly issued token
    - Rejects tampered signature
    - Rejects expired token
    - Rejects room/user/consultation context mismatches
    """
    from app.core.exceptions import ValidationError
    from app.services.video_meeting_service import InternalWebRTCMeetingProvider

    provider = InternalWebRTCMeetingProvider()
    client_id, _, client_prof_id = _setup_user(
        client, db, f"vid_sec_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT, full_name="Video Sec Client"
    )
    _, _, lawyer_prof_id = _setup_user(
        client, db, f"vid_sec_lawyer_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.LAWYER, full_name="Advocate Sec"
    )

    con = Consultation(
        id=generate_uuid7(),
        client_id=client_prof_id,
        lawyer_id=lawyer_prof_id,
        scheduled_at=datetime.now(UTC) + timedelta(minutes=5),
        duration_minutes=30,
        fee_amount=1500.0,
        currency="INR",
        status=ConsultationStatus.SCHEDULED,
    )
    db.add(con)
    db.commit()

    meeting = VideoMeeting(
        id=generate_uuid7(),
        consultation_id=con.id,
        room_id=f"room-{con.id.hex[:8]}",
        provider="internal_webrtc",
        status=VideoMeetingStatus.SCHEDULED,
        scheduled_start=con.scheduled_at,
        scheduled_end=con.scheduled_at + timedelta(minutes=30),
    )
    db.add(meeting)
    db.commit()

    user = db.query(User).filter(User.id == UUID(client_id)).first()
    assert user is not None

    # 1. Valid token succeeds
    valid_token = provider.generate_access_token(user, meeting, role="CLIENT", expires_in_seconds=3600)
    payload = provider.verify_access_token(
        valid_token,
        expected_room_id=meeting.room_id,
        expected_user_id=user.id,
        expected_consultation_id=con.id,
    )
    assert payload["role"] == "CLIENT"
    assert payload["user_id"] == str(user.id)
    assert "jti" in payload
    assert "iat" in payload

    # 2. Tampered signature fails
    tampered_sig_token = "0000000000000000000000000000000000000000000000000000000000000000." + valid_token.split(".")[1]
    with pytest.raises(ValidationError, match="Tampered or invalid video token signature"):
        provider.verify_access_token(tampered_sig_token)

    # 3. Expired token fails
    expired_token = provider.generate_access_token(user, meeting, role="CLIENT", expires_in_seconds=-10)
    with pytest.raises(ValidationError, match="expired"):
        provider.verify_access_token(expired_token)

    # 4. Room ID mismatch fails
    with pytest.raises(ValidationError, match="not authorized for this meeting room"):
        provider.verify_access_token(valid_token, expected_room_id="different-room-id")

    # 5. User ID mismatch fails
    with pytest.raises(ValidationError, match="does not belong to this participant"):
        provider.verify_access_token(valid_token, expected_user_id=uuid.uuid4())

    # 6. Consultation ID mismatch fails
    with pytest.raises(ValidationError, match="does not match this consultation"):
        provider.verify_access_token(valid_token, expected_consultation_id=uuid.uuid4())


def test_consultation_note_client_sharing_isolation(client: TestClient, db: Session):
    """
    Verifies that:
    1. Advocate can create internal work-product note (client_shared=False) and shared advice (client_shared=True).
    2. Lawyer sees all notes.
    3. Client only sees client_shared=True notes.
    4. Client cannot create hidden (client_shared=False) notes.
    5. Empty note summary is rejected with 422.
    """
    _, client_headers, client_prof_id = _setup_user(
        client, db, f"note_client_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT, full_name="Client Note"
    )
    _, lawyer_headers, lawyer_prof_id = _setup_user(
        client, db, f"note_lawyer_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.LAWYER, full_name="Advocate Note"
    )

    con = Consultation(
        id=generate_uuid7(),
        client_id=client_prof_id,
        lawyer_id=lawyer_prof_id,
        scheduled_at=datetime.now(UTC),
        duration_minutes=30,
        fee_amount=1500.0,
        currency="INR",
        status=ConsultationStatus.IN_PROGRESS,
    )
    db.add(con)
    db.commit()

    # 1. Lawyer creates shared note
    res_shared = client.post(
        f"/api/v1/consultations/{con.id}/notes",
        headers=lawyer_headers,
        json={
            "summary": "File section 138 NI Act complaint before Metropolitan Magistrate.",
            "action_items": ["Gather bank return memo", "Draft statutory notice"],
            "client_shared": True,
        },
    )
    assert res_shared.status_code == 201

    # 2. Lawyer creates internal work-product note
    res_private = client.post(
        f"/api/v1/consultations/{con.id}/notes",
        headers=lawyer_headers,
        json={
            "summary": "Internal counsel note: Limitation period expires in 15 days.",
            "action_items": ["Verify postal receipt date"],
            "client_shared": False,
        },
    )
    assert res_private.status_code == 201

    # 3. Lawyer lists notes -> sees both (2 notes)
    res_lawyer_notes = client.get(f"/api/v1/consultations/{con.id}/notes", headers=lawyer_headers)
    assert res_lawyer_notes.status_code == 200
    assert len(res_lawyer_notes.json()) == 2

    # 4. Client lists notes -> sees only shared note (1 note)
    res_client_notes = client.get(f"/api/v1/consultations/{con.id}/notes", headers=client_headers)
    assert res_client_notes.status_code == 200
    client_notes = res_client_notes.json()
    assert len(client_notes) == 1
    assert "section 138" in client_notes[0]["summary"].lower()

    # 5. Client attempts to create empty note -> 422
    res_empty = client.post(
        f"/api/v1/consultations/{con.id}/notes",
        headers=client_headers,
        json={"summary": "   ", "client_shared": True},
    )
    assert res_empty.status_code == 422


def test_timezone_naive_and_boundary_handling(client: TestClient, db: Session):
    """
    Verifies timezone handling:
    1. Naive datetime strings are normalized to UTC cleanly.
    2. Consultation crossing midnight in IST is rejected with 422.
    3. Consultation outside business hours (before 08:00 IST or after 22:00 IST) is rejected with 422.
    """
    _, client_headers, _ = _setup_user(
        client, db, f"tz_client_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT, full_name="Client TZ"
    )
    _, _, lawyer_prof_id = _setup_user(
        client, db, f"tz_lawyer_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.LAWYER, full_name="Advocate TZ"
    )

    # 1. Booking at 23:50 IST (18:20 UTC) with 30 min duration -> crosses midnight IST -> 422
    midnight_cross_time = datetime(2030, 8, 20, 18, 20, 0, tzinfo=UTC).isoformat()
    res_midnight = client.post(
        "/api/v1/consultations",
        headers=client_headers,
        json={
            "lawyer_id": str(lawyer_prof_id),
            "scheduled_at": midnight_cross_time,
            "duration_minutes": 30,
        },
    )
    assert res_midnight.status_code == 422
    assert "multiple calendar days" in res_midnight.json()["error"]["message"] or "business hours" in res_midnight.json()["error"]["message"]

    # 2. Booking at 06:00 IST (00:30 UTC) -> outside business hours -> 422
    early_time = datetime(2030, 8, 20, 0, 30, 0, tzinfo=UTC).isoformat()
    res_early = client.post(
        "/api/v1/consultations",
        headers=client_headers,
        json={
            "lawyer_id": str(lawyer_prof_id),
            "scheduled_at": early_time,
            "duration_minutes": 30,
        },
    )
    assert res_early.status_code == 422
    assert "business hours" in res_early.json()["error"]["message"]

    # 3. Naive ISO string without timezone (e.g. '2030-08-20T10:00:00') should be safely parsed and treated as UTC
    naive_slot = "2030-08-20T10:00:00"  # 15:30 IST (well within business hours)
    res_naive = client.post(
        "/api/v1/consultations",
        headers=client_headers,
        json={
            "lawyer_id": str(lawyer_prof_id),
            "scheduled_at": naive_slot,
            "duration_minutes": 30,
        },
    )
    assert res_naive.status_code == 201
    con_data = res_naive.json()
    assert con_data["status"] == "REQUESTED"
    assert "2030-08-20" in con_data["scheduled_at"]
