import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
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
from app.schemas.presence import PresenceStatus
from app.services.consultation_service import ConsultationService
from app.services.lawyer_call_channel import incoming_call_channel_manager
from app.services.presence_service import presence_service


def _create_lawyer(db: Session, email_prefix: str) -> tuple[User, LawyerProfile]:
    uid = uuid.uuid4().hex[:6]
    user = User(
        email=f"{email_prefix}_{uid}@lcc.test",
        password_hash="hashed_dummy_password",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    lawyer_profile = LawyerProfile(
        user_id=user.id,
        full_name=f"Advocate {email_prefix.capitalize()}",
        practice_areas=["Corporate Law"],
        court_jurisdictions=["Supreme Court of India"],
        languages=["English", "Hindi"],
        experience_years=10,
        consultation_fee=2000.0,
    )
    db.add(lawyer_profile)
    db.flush()

    verification = LawyerVerification(
        lawyer_profile_id=lawyer_profile.id,
        enrollment_number=f"D/{uuid.uuid4().hex[:4].upper()}/2020",
        state_bar_council="Bar Council of Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(verification)
    db.commit()
    db.refresh(user)
    db.refresh(lawyer_profile)
    return user, lawyer_profile


def _create_client(db: Session, email_prefix: str) -> tuple[User, ClientProfile]:
    uid = uuid.uuid4().hex[:6]
    user = User(
        email=f"{email_prefix}_{uid}@lcc.test",
        password_hash="hashed_dummy_password",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    client_profile = ClientProfile(
        user_id=user.id,
        full_name=f"Client {email_prefix.capitalize()}",
    )
    db.add(client_profile)
    db.commit()
    db.refresh(user)
    db.refresh(client_profile)
    return user, client_profile


def test_presence_heartbeat_and_authoritative_status(client: TestClient, db: Session):
    user, lawyer_profile = _create_lawyer(db, "presence_lawyer")
    token = create_access_token(str(user.id), user.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Heartbeat with available_for_instant=True
    res = client.post(
        "/api/v1/lawyers/heartbeat",
        json={"available_for_instant": True},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_online"] is True
    assert data["is_available"] is True
    assert data["presence_status"] == "AVAILABLE"

    # 2. Query presence endpoint
    res_p = client.get(f"/api/v1/lawyers/{lawyer_profile.id}/presence", headers=headers)
    assert res_p.status_code == 200
    p_data = res_p.json()
    assert p_data["is_online"] is True
    assert p_data["is_available"] is True
    assert p_data["presence_status"] == "AVAILABLE"

    # 3. Heartbeat with available_for_instant=False
    res2 = client.post(
        "/api/v1/lawyers/heartbeat",
        json={"available_for_instant": False},
        headers=headers,
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_online"] is True
    assert data2["is_available"] is False
    assert data2["presence_status"] == "ONLINE"


def test_authoritative_busy_when_consultation_in_progress(client: TestClient, db: Session):
    lawyer_user, lawyer_profile = _create_lawyer(db, "busy_lawyer")
    client_user, client_profile = _create_client(db, "busy_client")
    token = create_access_token(str(lawyer_user.id), lawyer_user.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    # Mark available first
    client.post(
        "/api/v1/lawyers/heartbeat",
        json={"available_for_instant": True},
        headers=headers,
    )

    consultation_service = ConsultationService(db)
    is_avail, _, p_status = consultation_service.is_lawyer_available(lawyer_profile.id)
    assert is_avail is True
    assert p_status == PresenceStatus.AVAILABLE

    # Create an IN_PROGRESS consultation
    con = Consultation(
        client_id=client_profile.id,
        lawyer_id=lawyer_profile.id,
        scheduled_at=datetime.now(UTC),
        duration_minutes=30,
        fee_amount=1000.0,
        currency="INR",
        status=ConsultationStatus.IN_PROGRESS,
    )
    db.add(con)
    db.commit()

    # Authoritative check should now report BUSY
    is_avail_busy, reason, p_status_busy = consultation_service.is_lawyer_available(lawyer_profile.id)
    assert is_avail_busy is False
    assert p_status_busy == PresenceStatus.BUSY
    assert "active in another consultation" in reason

    # Clean up
    con.status = ConsultationStatus.COMPLETED
    db.commit()


def test_authoritative_busy_when_active_video_meeting(client: TestClient, db: Session):
    lawyer_user, lawyer_profile = _create_lawyer(db, "video_busy_lawyer")
    client_user, client_profile = _create_client(db, "video_busy_client")
    token = create_access_token(str(lawyer_user.id), lawyer_user.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    # Mark available
    client.post(
        "/api/v1/lawyers/heartbeat",
        json={"available_for_instant": True},
        headers=headers,
    )

    now = datetime.now(UTC)
    con = Consultation(
        client_id=client_profile.id,
        lawyer_id=lawyer_profile.id,
        scheduled_at=now,
        duration_minutes=30,
        fee_amount=1500.0,
        currency="INR",
        status=ConsultationStatus.SCHEDULED,
    )
    db.add(con)
    db.flush()

    meeting = VideoMeeting(
        consultation_id=con.id,
        room_id=f"test-room-{uuid.uuid4().hex[:8]}",
        provider="mock",
        status=VideoMeetingStatus.ACTIVE,
        scheduled_start=now,
        scheduled_end=now + timedelta(minutes=30),
    )
    db.add(meeting)
    db.commit()

    consultation_service = ConsultationService(db)
    is_avail, reason, p_status = consultation_service.is_lawyer_available(lawyer_profile.id)
    assert is_avail is False
    assert p_status == PresenceStatus.BUSY
    assert "active video meeting" in reason

    # End meeting -> availability restored
    meeting.status = VideoMeetingStatus.ENDED
    meeting.ended_at = datetime.now(UTC)
    db.commit()

    is_avail_after, _, p_status_after = consultation_service.is_lawyer_available(lawyer_profile.id)
    assert is_avail_after is True
    assert p_status_after == PresenceStatus.AVAILABLE


def test_stale_incoming_call_expiration(client: TestClient, db: Session):
    from sqlalchemy import update

    lawyer_user, lawyer_profile = _create_lawyer(db, "stale_call_lawyer")
    client_user, client_profile = _create_client(db, "stale_call_client")

    past_time = datetime.now(UTC) - timedelta(seconds=settings.INSTANT_CALL_RING_TIMEOUT_SECONDS + 30)
    con = Consultation(
        client_id=client_profile.id,
        lawyer_id=lawyer_profile.id,
        scheduled_at=past_time,
        duration_minutes=30,
        fee_amount=2000.0,
        currency="INR",
        status=ConsultationStatus.REQUESTED,
    )
    db.add(con)
    db.commit()
    db.refresh(con)

    # Force created_at to past timestamp
    db.execute(
        update(Consultation).where(Consultation.id == con.id).values(created_at=past_time)
    )
    db.commit()
    db.refresh(con)

    consultation_service = ConsultationService(db)
    expired_list = consultation_service.expire_stale_incoming_calls(lawyer_profile.id)
    assert len(expired_list) == 1

    db.refresh(con)
    assert con.status == ConsultationStatus.CANCELLED
    assert "timed out" in (con.rejection_reason or "").lower()


def test_websocket_incoming_calls_connection_and_auth(client: TestClient, db: Session):
    lawyer_user, lawyer_profile = _create_lawyer(db, "ws_lawyer")
    client_user, _client_profile = _create_client(db, "ws_client")

    lawyer_token = create_access_token(str(lawyer_user.id), lawyer_user.role.value)
    client_token = create_access_token(str(client_user.id), client_user.role.value)

    # Non-lawyer connection should be rejected with 1008 policy violation
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/consultations/ws/incoming-calls?token={client_token}") as ws:
            ws.receive_text()

    # Valid lawyer connection succeeds, handles ping/pong and heartbeat
    with client.websocket_connect(f"/api/v1/consultations/ws/incoming-calls?token={lawyer_token}") as ws:
        # Test ping/pong
        ws.send_text("ping")
        resp = ws.receive_text()
        assert resp == "pong"

        # Test heartbeat message
        ws.send_text("heartbeat")
        hb_resp = ws.receive_json()
        assert hb_resp["type"] == "heartbeat_ack"
        assert hb_resp["status"] == "AVAILABLE"

    # Presence should be recorded
    assert presence_service.is_online(lawyer_user.id) is True


def test_multitab_incoming_call_broadcasting(client: TestClient, db: Session):
    lawyer_user, lawyer_profile = _create_lawyer(db, "ws_multitab_lawyer")
    lawyer_token = create_access_token(str(lawyer_user.id), lawyer_user.role.value)

    # Open Tab 1 and Tab 2 concurrently for the same lawyer
    with client.websocket_connect(f"/api/v1/consultations/ws/incoming-calls?token={lawyer_token}") as tab1:
        with client.websocket_connect(f"/api/v1/consultations/ws/incoming-calls?token={lawyer_token}") as tab2:
            # 1. Trigger incoming call broadcast
            call_id = uuid.uuid4()
            call_data = {
                "id": str(call_id),
                "client_name": "Test Client",
                "fee": 2500.0,
                "ring_timeout_seconds": 45,
            }
            asyncio.run(incoming_call_channel_manager.notify_incoming_call(lawyer_profile.id, call_data))

            # Both tabs should receive incoming call notification
            msg1 = tab1.receive_json()
            msg2 = tab2.receive_json()
            assert msg1["type"] == "incoming_consultation"
            assert msg1["consultation_id"] == str(call_id)
            assert msg2["type"] == "incoming_consultation"
            assert msg2["consultation_id"] == str(call_id)

            # 2. Trigger call accepted broadcast
            asyncio.run(incoming_call_channel_manager.notify_call_accepted(lawyer_profile.id, call_id))
            acc1 = tab1.receive_json()
            acc2 = tab2.receive_json()
            assert acc1["type"] == "consultation_accepted"
            assert acc1["consultation_id"] == str(call_id)
            assert acc2["type"] == "consultation_accepted"
            assert acc2["consultation_id"] == str(call_id)

            # 3. Trigger call cancelled broadcast
            asyncio.run(incoming_call_channel_manager.notify_call_cancelled(lawyer_profile.id, call_id, reason="Client hung up"))
            can1 = tab1.receive_json()
            can2 = tab2.receive_json()
            assert can1["type"] == "consultation_cancelled"
            assert can1["reason"] == "Client hung up"
            assert can2["type"] == "consultation_cancelled"
            assert can2["reason"] == "Client hung up"

