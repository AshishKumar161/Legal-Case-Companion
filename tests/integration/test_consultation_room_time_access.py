import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.consultation import Consultation, ConsultationStatus
from app.models.user import (
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.models.video_meeting import VideoMeetingStatus
from app.domain.consultations.video_meeting_service import VideoMeetingService


def _create_user(
    client: TestClient,
    db: Session,
    email: str,
    role: UserRole = UserRole.CLIENT,
    full_name: str = "User",
) -> tuple[dict[str, str], UUID, User]:
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": full_name, "role": role.value},
    )
    assert reg_res.status_code == 201, reg_res.text
    user_id = UUID(reg_res.json()["id"])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == 200, login_res.text
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    user = db.query(User).filter(User.id == user_id).first()
    assert user is not None

    if role == UserRole.LAWYER and user.lawyer_profile:
        user.lawyer_profile.consultation_fee = 1500.0
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

    return headers, user_id, user


def test_room_access_status_blocked_before_window(client: TestClient, db: Session):
    """Room access status must be blocked when current time is earlier than 15 mins before scheduled time."""
    client_headers, client_id, client_user = _create_user(client, db, f"client_{uuid.uuid4().hex[:6]}@example.com", UserRole.CLIENT)
    lawyer_headers, lawyer_id, lawyer_user = _create_user(client, db, f"lawyer_{uuid.uuid4().hex[:6]}@example.com", UserRole.LAWYER)

    # Scheduled 2 hours in the future
    sched_time = datetime.now(UTC) + timedelta(hours=2)
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_user.client_profile.id,
        lawyer_id=lawyer_user.lawyer_profile.id,
        scheduled_at=sched_time,
        duration_minutes=30,
        status=ConsultationStatus.SCHEDULED,
        fee_amount=1500.0,
        currency="INR",
    )
    db.add(consultation)
    db.commit()

    # Call access-status endpoint
    res = client.get(
        f"/api/v1/consultations/{consultation.id}/video/access-status",
        headers=client_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["can_join"] is False
    assert data["is_authorized"] is True
    assert data["time_until_open_seconds"] is not None
    assert data["time_until_open_seconds"] > 0
    assert "Meeting room opens 15 minutes before" in data["reason_blocked"]
    assert "IST" in data["scheduled_at_ist"]
    assert "IST" in data["earliest_join_ist"]

    # Calling join directly before window should fail cleanly with 422
    join_res = client.get(
        f"/api/v1/consultations/{consultation.id}/video/join",
        headers=client_headers,
    )
    assert join_res.status_code == 422
    assert "Meeting room opens 15 minutes before" in str(join_res.json())


def test_room_access_status_allowed_within_window(client: TestClient, db: Session):
    """Room access status must be allowed when current time is within 15 minutes before scheduled start."""
    client_headers, client_id, client_user = _create_user(client, db, f"client_{uuid.uuid4().hex[:6]}@example.com", UserRole.CLIENT)
    lawyer_headers, lawyer_id, lawyer_user = _create_user(client, db, f"lawyer_{uuid.uuid4().hex[:6]}@example.com", UserRole.LAWYER)

    # Scheduled 10 minutes in the future (within 15 min window)
    sched_time = datetime.now(UTC) + timedelta(minutes=10)
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_user.client_profile.id,
        lawyer_id=lawyer_user.lawyer_profile.id,
        scheduled_at=sched_time,
        duration_minutes=30,
        status=ConsultationStatus.SCHEDULED,
        fee_amount=1500.0,
        currency="INR",
    )
    db.add(consultation)
    db.commit()

    res = client.get(
        f"/api/v1/consultations/{consultation.id}/video/access-status",
        headers=client_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["can_join"] is True
    assert data["is_authorized"] is True
    assert data["reason_blocked"] is None

    # Join endpoint must succeed
    join_res = client.get(
        f"/api/v1/consultations/{consultation.id}/video/join",
        headers=client_headers,
    )
    assert join_res.status_code == 200, join_res.text
    join_data = join_res.json()
    assert "token" in join_data
    assert join_data["participant_role"] == "CLIENT"


def test_room_access_status_unauthorized_user_blocked(client: TestClient, db: Session):
    """An unrelated user cannot query access status or join room (BOLA/IDOR defense)."""
    _, _, client_user = _create_user(client, db, f"client_{uuid.uuid4().hex[:6]}@example.com", UserRole.CLIENT)
    _, _, lawyer_user = _create_user(client, db, f"lawyer_{uuid.uuid4().hex[:6]}@example.com", UserRole.LAWYER)
    unrelated_headers, _, _ = _create_user(client, db, f"unrelated_{uuid.uuid4().hex[:6]}@example.com", UserRole.CLIENT)

    sched_time = datetime.now(UTC) + timedelta(minutes=5)
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_user.client_profile.id,
        lawyer_id=lawyer_user.lawyer_profile.id,
        scheduled_at=sched_time,
        duration_minutes=30,
        status=ConsultationStatus.SCHEDULED,
        fee_amount=1500.0,
        currency="INR",
    )
    db.add(consultation)
    db.commit()

    res = client.get(
        f"/api/v1/consultations/{consultation.id}/video/access-status",
        headers=unrelated_headers,
    )
    assert res.status_code == 404

    join_res = client.get(
        f"/api/v1/consultations/{consultation.id}/video/join",
        headers=unrelated_headers,
    )
    assert join_res.status_code == 404


def test_room_access_status_terminal_states(client: TestClient, db: Session):
    """Cancelled and completed consultations cannot be joined."""
    client_headers, client_id, client_user = _create_user(client, db, f"client_{uuid.uuid4().hex[:6]}@example.com", UserRole.CLIENT)
    lawyer_headers, lawyer_id, lawyer_user = _create_user(client, db, f"lawyer_{uuid.uuid4().hex[:6]}@example.com", UserRole.LAWYER)

    # Cancelled consultation
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_user.client_profile.id,
        lawyer_id=lawyer_user.lawyer_profile.id,
        scheduled_at=datetime.now(UTC) + timedelta(minutes=5),
        duration_minutes=30,
        status=ConsultationStatus.CANCELLED,
        fee_amount=1500.0,
        currency="INR",
    )
    db.add(consultation)
    db.commit()

    res = client.get(
        f"/api/v1/consultations/{consultation.id}/video/access-status",
        headers=client_headers,
    )
    assert res.status_code == 200
    assert res.json()["can_join"] is False
    assert "cancelled" in res.json()["reason_blocked"].lower()


def test_room_access_lawyer_can_join_early(client: TestClient, db: Session):
    """Advocates/Lawyers can always enter their chambers early to prepare and set up."""
    client_headers, client_id, client_user = _create_user(client, db, f"client_{uuid.uuid4().hex[:6]}@example.com", UserRole.CLIENT)
    lawyer_headers, lawyer_id, lawyer_user = _create_user(client, db, f"lawyer_{uuid.uuid4().hex[:6]}@example.com", UserRole.LAWYER)

    sched_time = datetime.now(UTC) + timedelta(hours=3)
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_user.client_profile.id,
        lawyer_id=lawyer_user.lawyer_profile.id,
        scheduled_at=sched_time,
        duration_minutes=30,
        status=ConsultationStatus.SCHEDULED,
        fee_amount=1500.0,
        currency="INR",
    )
    db.add(consultation)
    db.commit()

    # Lawyer checking access status
    res = client.get(
        f"/api/v1/consultations/{consultation.id}/video/access-status",
        headers=lawyer_headers,
    )
    assert res.status_code == 200
    assert res.json()["can_join"] is True
    assert res.json()["time_bypass_allowed"] is True

    # Lawyer joining directly
    join_res = client.get(
        f"/api/v1/consultations/{consultation.id}/video/join",
        headers=lawyer_headers,
    )
    assert join_res.status_code == 200
    assert "token" in join_res.json()
    assert join_res.json()["participant_role"] == "LAWYER"


def test_room_access_bypass_time_parameter(client: TestClient, db: Session):
    """Clients can bypass scheduled window check when bypass_time=true query parameter is supplied."""
    client_headers, client_id, client_user = _create_user(client, db, f"client_{uuid.uuid4().hex[:6]}@example.com", UserRole.CLIENT)
    lawyer_headers, lawyer_id, lawyer_user = _create_user(client, db, f"lawyer_{uuid.uuid4().hex[:6]}@example.com", UserRole.LAWYER)

    sched_time = datetime.now(UTC) + timedelta(hours=5)
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_user.client_profile.id,
        lawyer_id=lawyer_user.lawyer_profile.id,
        scheduled_at=sched_time,
        duration_minutes=30,
        status=ConsultationStatus.SCHEDULED,
        fee_amount=1500.0,
        currency="INR",
    )
    db.add(consultation)
    db.commit()

    # Access status with bypass_time=true
    res = client.get(
        f"/api/v1/consultations/{consultation.id}/video/access-status?bypass_time=true",
        headers=client_headers,
    )
    assert res.status_code == 200
    assert res.json()["can_join"] is True

    # Join with bypass_time=true
    join_res = client.get(
        f"/api/v1/consultations/{consultation.id}/video/join?bypass_time=true",
        headers=client_headers,
    )
    assert join_res.status_code == 200
    assert "token" in join_res.json()
    assert join_res.json()["participant_role"] == "CLIENT"


def test_room_access_when_lawyer_online(client: TestClient, db: Session):
    """When a lawyer is online (heartbeat active), client can join without waiting for scheduled time."""
    from app.domain.consultations.presence_service import PresenceService

    client_headers, client_id, client_user = _create_user(client, db, f"client_{uuid.uuid4().hex[:6]}@example.com", UserRole.CLIENT)
    lawyer_headers, lawyer_id, lawyer_user = _create_user(client, db, f"lawyer_{uuid.uuid4().hex[:6]}@example.com", UserRole.LAWYER)

    # Record presence heartbeat for lawyer
    presence_svc = PresenceService()
    presence_svc.record_heartbeat(user_id=lawyer_user.id, lawyer_id=lawyer_user.lawyer_profile.id)

    sched_time = datetime.now(UTC) + timedelta(hours=4)
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_user.client_profile.id,
        lawyer_id=lawyer_user.lawyer_profile.id,
        scheduled_at=sched_time,
        duration_minutes=30,
        status=ConsultationStatus.SCHEDULED,
        fee_amount=1500.0,
        currency="INR",
    )
    db.add(consultation)
    db.commit()

    # Client checks access status: lawyer is online so can_join should be True
    res = client.get(
        f"/api/v1/consultations/{consultation.id}/video/access-status",
        headers=client_headers,
    )
    assert res.status_code == 200
    assert res.json()["can_join"] is True
    assert res.json()["lawyer_online"] is True

    # Client can join directly
    join_res = client.get(
        f"/api/v1/consultations/{consultation.id}/video/join",
        headers=client_headers,
    )
    assert join_res.status_code == 200
    assert "token" in join_res.json()

