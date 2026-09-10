import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError, ValidationError
from app.core.identifiers import generate_uuid7
from app.models.consultation import Consultation, ConsultationStatus
from app.models.user import (
    AccountStatus,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.models.video_meeting import VideoMeeting, VideoMeetingStatus
from app.domain.consultations.video_meeting_service import (
    VideoMeetingService,
    get_video_provider,
)
from app.domain.consultations.video_telemetry_service import VideoTelemetryEvent, metrics_registry


def _setup_participant(
    client: TestClient,
    db: Session,
    email: str,
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Test User",
) -> tuple[str, dict[str, str], UUID]:
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": full_name, "role": role.value},
    )
    assert reg_res.status_code == 201, reg_res.text
    user_id = reg_res.json()["id"]

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    assert user is not None

    profile_id = user.id
    if role == UserRole.LAWYER and user.lawyer_profile:
        user.lawyer_profile.consultation_fee = 2000.0
        verif = LawyerVerification(
            id=generate_uuid7(),
            lawyer_profile_id=user.lawyer_profile.id,
            enrollment_number=f"DL/{uuid.uuid4().hex[:6].upper()}/2020",
            state_bar_council="Delhi",
            status=VerificationStatus.APPROVED,
        )
        db.add(verif)
        profile_id = user.lawyer_profile.id
    elif role == UserRole.CLIENT and user.client_profile:
        profile_id = user.client_profile.id

    db.commit()
    return user_id, headers, profile_id


def _create_consultation(
    db: Session,
    client_prof_id: UUID,
    lawyer_prof_id: UUID,
    status: ConsultationStatus = ConsultationStatus.PAID,
) -> Consultation:
    now = datetime.now(UTC)
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_prof_id,
        lawyer_id=lawyer_prof_id,
        scheduled_at=now + timedelta(minutes=5),
        duration_minutes=30,
        fee_amount=2000.0,
        currency="INR",
        status=status,
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)
    return consultation


def test_session_restoration_on_reconnect_and_browser_refresh(client: TestClient, db: Session):
    """
    Verify that when a client refreshes their page or loses connection,
    calling reconnect reissues a fresh, cryptographically valid token
    bound to the authoritative room without creating duplicate rooms.
    """
    c_uid, c_hdr, c_pid = _setup_participant(client, db, f"client_rec_{uuid.uuid4().hex[:6]}@test.com", UserRole.CLIENT)
    l_uid, l_hdr, l_pid = _setup_participant(client, db, f"lawyer_rec_{uuid.uuid4().hex[:6]}@test.com", UserRole.LAWYER)
    consultation = _create_consultation(db, c_pid, l_pid)

    # 1. Initial join request
    res_join = client.get(f"/api/v1/consultations/{consultation.id}/video/join", headers=c_hdr)
    assert res_join.status_code == 200, res_join.text
    join_data1 = res_join.json()
    room_id_1 = join_data1["room_id"]
    token_1 = join_data1["token"]

    # Verify token 1 is cryptographically valid
    provider = get_video_provider()
    payload_1 = provider.verify_access_token(token_1, expected_room_id=room_id_1, expected_consultation_id=consultation.id)
    assert payload_1["user_id"] == c_uid

    # 2. Client browser refreshes / network reconnects -> calls /video/reconnect
    res_reconnect = client.post(f"/api/v1/consultations/{consultation.id}/video/reconnect", headers=c_hdr)
    assert res_reconnect.status_code == 200, res_reconnect.text
    reconn_data = res_reconnect.json()
    room_id_2 = reconn_data["room_id"]
    token_2 = reconn_data["token"]

    # Invariant: Must use the exact same room, never create a duplicate room
    assert room_id_1 == room_id_2
    assert reconn_data["meeting_id"] == join_data1["meeting_id"]

    # Invariant: Token 2 is fresh and cryptographically valid
    payload_2 = provider.verify_access_token(token_2, expected_room_id=room_id_1, expected_consultation_id=consultation.id)
    assert payload_2["user_id"] == c_uid

    # Check DB meeting count for this consultation: strictly 1 record
    meetings = db.query(VideoMeeting).filter(VideoMeeting.consultation_id == consultation.id).all()
    assert len(meetings) == 1


def test_multi_tab_concurrency_safe_association(client: TestClient, db: Session):
    """
    Verify that when the same participant opens two browser tabs,
    both tabs are safely associated with the same room without session corruption.
    """
    c_uid, c_hdr, c_pid = _setup_participant(client, db, f"client_tab_{uuid.uuid4().hex[:6]}@test.com", UserRole.CLIENT)
    l_uid, l_hdr, l_pid = _setup_participant(client, db, f"lawyer_tab_{uuid.uuid4().hex[:6]}@test.com", UserRole.LAWYER)
    consultation = _create_consultation(db, c_pid, l_pid)

    # Tab 1 joins
    res_tab1 = client.get(f"/api/v1/consultations/{consultation.id}/video/join", headers=c_hdr)
    assert res_tab1.status_code == 200

    # Tab 2 joins simultaneously
    res_tab2 = client.get(f"/api/v1/consultations/{consultation.id}/video/join", headers=c_hdr)
    assert res_tab2.status_code == 200

    # Both tabs point to same room
    assert res_tab1.json()["room_id"] == res_tab2.json()["room_id"]
    assert res_tab1.json()["meeting_id"] == res_tab2.json()["meeting_id"]


def test_terminal_state_blocks_reconnect(client: TestClient, db: Session):
    """
    Verify that once a consultation reaches a terminal state (COMPLETED or CANCELLED),
    reconnecting or joining is strictly blocked and cannot reopen the session.
    """
    c_uid, c_hdr, c_pid = _setup_participant(client, db, f"client_term_{uuid.uuid4().hex[:6]}@test.com", UserRole.CLIENT)
    l_uid, l_hdr, l_pid = _setup_participant(client, db, f"lawyer_term_{uuid.uuid4().hex[:6]}@test.com", UserRole.LAWYER)
    consultation = _create_consultation(db, c_pid, l_pid, status=ConsultationStatus.COMPLETED)

    # Attempt reconnect to completed consultation -> rejected
    res_recon = client.post(f"/api/v1/consultations/{consultation.id}/video/reconnect", headers=c_hdr)
    assert res_recon.status_code in (400, 422)
    assert "concluded" in res_recon.text.lower() or "completed" in res_recon.text.lower()

    # Cancelled consultation -> rejected
    consultation.status = ConsultationStatus.CANCELLED
    db.commit()
    res_cancel = client.post(f"/api/v1/consultations/{consultation.id}/video/reconnect", headers=c_hdr)
    assert res_cancel.status_code in (400, 422)


def test_video_authorization_and_bola_isolation(client: TestClient, db: Session):
    """
    Verify that an unauthorized third-party user cannot join or reconnect
    to another user's consultation room (returns 404 BOLA defense).
    """
    c_uid, c_hdr, c_pid = _setup_participant(client, db, f"client_bola_{uuid.uuid4().hex[:6]}@test.com", UserRole.CLIENT)
    l_uid, l_hdr, l_pid = _setup_participant(client, db, f"lawyer_bola_{uuid.uuid4().hex[:6]}@test.com", UserRole.LAWYER)
    consultation = _create_consultation(db, c_pid, l_pid)

    # Attacker user
    _, bad_hdr, _ = _setup_participant(client, db, f"attacker_{uuid.uuid4().hex[:6]}@test.com", UserRole.CLIENT)

    # Attacker tries to join
    res_join = client.get(f"/api/v1/consultations/{consultation.id}/video/join", headers=bad_hdr)
    assert res_join.status_code == 404

    # Attacker tries to reconnect
    res_recon = client.post(f"/api/v1/consultations/{consultation.id}/video/reconnect", headers=bad_hdr)
    assert res_recon.status_code == 404


def test_stale_meeting_cleanup(db: Session):
    """
    Verify that permanently stale active meetings (scheduled_end + 2 hours in the past)
    are cleanly identified and transitioned to ENDED by cleanup_stale_meetings.
    """
    now = datetime.now(UTC)
    old_time = now - timedelta(hours=4)

    c_user = User(id=generate_uuid7(), email="stale_client@test.com", role=UserRole.CLIENT, account_status=AccountStatus.ACTIVE)
    l_user = User(id=generate_uuid7(), email="stale_lawyer@test.com", role=UserRole.LAWYER, account_status=AccountStatus.ACTIVE)
    db.add_all([c_user, l_user])
    db.flush()

    consultation = Consultation(
        id=generate_uuid7(),
        client_id=c_user.id,
        lawyer_id=l_user.id,
        scheduled_at=old_time,
        duration_minutes=30,
        fee_amount=1000.0,
        currency="INR",
        status=ConsultationStatus.IN_PROGRESS,
    )
    db.add(consultation)
    db.flush()

    meeting = VideoMeeting(
        id=generate_uuid7(),
        consultation_id=consultation.id,
        room_id=f"stale-room-{uuid.uuid4().hex[:8]}",
        status=VideoMeetingStatus.ACTIVE,
        scheduled_start=old_time,
        scheduled_end=old_time + timedelta(minutes=30),
        started_at=old_time,
    )
    db.add(meeting)
    db.commit()

    service = VideoMeetingService(db)
    cleaned_count = service.cleanup_stale_meetings(max_idle_hours=2)

    assert cleaned_count >= 1
    db.refresh(meeting)
    assert meeting.status == VideoMeetingStatus.ENDED
    assert meeting.ended_at is not None

    db.refresh(consultation)
    assert consultation.status == ConsultationStatus.COMPLETED
