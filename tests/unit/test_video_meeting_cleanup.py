import uuid
from datetime import UTC, datetime, timedelta
import pytest
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.consultation import Consultation, ConsultationStatus
from app.models.user import ClientProfile, LawyerProfile, User, UserRole
from app.models.video_meeting import VideoMeeting, VideoMeetingStatus
from app.models.video_recording import VideoRecording, VideoRecordingStatus
from app.domain.consultations.video_meeting_service import VideoMeetingService


def _create_consultation_and_meeting(
    db: Session,
    meeting_status: VideoMeetingStatus = VideoMeetingStatus.ACTIVE,
    consultation_status: ConsultationStatus = ConsultationStatus.IN_PROGRESS,
    scheduled_end_offset_hours: float = -3.0,
    has_recording: bool = False,
) -> tuple[Consultation, VideoMeeting, VideoRecording | None]:
    client_user = User(
        id=generate_uuid7(),
        email=f"client_vm_{uuid.uuid4().hex[:6]}@test.com",
        role=UserRole.CLIENT,
    )
    lawyer_user = User(
        id=generate_uuid7(),
        email=f"lawyer_vm_{uuid.uuid4().hex[:6]}@test.com",
        role=UserRole.LAWYER,
    )
    db.add_all([client_user, lawyer_user])
    db.flush()

    c_prof = ClientProfile(user_id=client_user.id, full_name="VM Client")
    l_prof = LawyerProfile(
        id=generate_uuid7(),
        user_id=lawyer_user.id,
        full_name="Adv. VM Lawyer",
        consultation_fee=2000.0,
    )
    db.add_all([c_prof, l_prof])
    db.flush()

    now = datetime.now(UTC)
    scheduled_end = now + timedelta(hours=scheduled_end_offset_hours)
    scheduled_start = scheduled_end - timedelta(minutes=30)

    consultation = Consultation(
        id=generate_uuid7(),
        client_id=c_prof.id,
        lawyer_id=l_prof.id,
        scheduled_at=scheduled_start,
        duration_minutes=30,
        fee_amount=2000.0,
        currency="INR",
        status=consultation_status,
    )
    db.add(consultation)
    db.flush()

    meeting = VideoMeeting(
        id=generate_uuid7(),
        consultation_id=consultation.id,
        room_id=f"room_cleanup_{uuid.uuid4().hex[:8]}",
        status=meeting_status,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
    )
    db.add(meeting)
    db.flush()

    recording = None
    if has_recording:
        recording = VideoRecording(
            id=generate_uuid7(),
            consultation_id=consultation.id,
            status=VideoRecordingStatus.RECORDING,
            storage_path=f"{consultation.id}/rec.webm",
            file_size_bytes=1024,
            started_at=scheduled_start,
        )
        db.add(recording)
        db.flush()

    db.commit()
    db.refresh(consultation)
    db.refresh(meeting)
    if recording:
        db.refresh(recording)

    return consultation, meeting, recording


def test_cleanup_stale_meetings_zero(db: Session):
    """Scenario 1: No stale meetings exist."""
    # Meeting ended hours ago, or meeting scheduled in future
    _create_consultation_and_meeting(
        db,
        meeting_status=VideoMeetingStatus.ENDED,
        consultation_status=ConsultationStatus.COMPLETED,
        scheduled_end_offset_hours=-4.0,
    )
    service = VideoMeetingService(db)
    cleaned = service.cleanup_stale_meetings(max_idle_hours=2)
    assert cleaned == 0


def test_cleanup_stale_meetings_single(db: Session):
    """Scenario 2: One stale meeting is transitioned to ENDED and consultation to COMPLETED."""
    consultation, meeting, recording = _create_consultation_and_meeting(
        db,
        meeting_status=VideoMeetingStatus.ACTIVE,
        consultation_status=ConsultationStatus.IN_PROGRESS,
        scheduled_end_offset_hours=-3.0,
        has_recording=True,
    )
    service = VideoMeetingService(db)
    cleaned = service.cleanup_stale_meetings(max_idle_hours=2)
    assert cleaned == 1

    db.refresh(meeting)
    db.refresh(consultation)
    assert meeting.status == VideoMeetingStatus.ENDED
    assert meeting.ended_at is not None
    assert consultation.status == ConsultationStatus.COMPLETED
    assert consultation.completed_at is not None

    if recording:
        db.refresh(recording)
        assert recording.status == VideoRecordingStatus.UPLOADING
        assert recording.ended_at is not None


def test_cleanup_stale_meetings_multiple(db: Session):
    """Scenario 3: Multiple concurrent stale meetings are all cleaned up."""
    c1, m1, _ = _create_consultation_and_meeting(db, scheduled_end_offset_hours=-5.0)
    c2, m2, _ = _create_consultation_and_meeting(db, scheduled_end_offset_hours=-2.5)

    service = VideoMeetingService(db)
    cleaned = service.cleanup_stale_meetings(max_idle_hours=2)
    assert cleaned >= 2

    db.refresh(m1)
    db.refresh(m2)
    assert m1.status == VideoMeetingStatus.ENDED
    assert m2.status == VideoMeetingStatus.ENDED


def test_cleanup_stale_meetings_already_closed(db: Session):
    """Scenario 4: Already-closed / cancelled meetings are not altered."""
    c_ended, m_ended, _ = _create_consultation_and_meeting(
        db,
        meeting_status=VideoMeetingStatus.ENDED,
        consultation_status=ConsultationStatus.COMPLETED,
        scheduled_end_offset_hours=-10.0,
    )
    c_cancelled, m_cancelled, _ = _create_consultation_and_meeting(
        db,
        meeting_status=VideoMeetingStatus.CANCELLED,
        consultation_status=ConsultationStatus.CANCELLED,
        scheduled_end_offset_hours=-10.0,
    )

    service = VideoMeetingService(db)
    cleaned = service.cleanup_stale_meetings(max_idle_hours=2)
    assert cleaned == 0

    db.refresh(m_ended)
    db.refresh(m_cancelled)
    assert m_ended.status == VideoMeetingStatus.ENDED
    assert m_cancelled.status == VideoMeetingStatus.CANCELLED


def test_cleanup_stale_meetings_boundary_timestamp(db: Session):
    """Scenario 5: Boundary timestamp evaluation (exactly on cutoff vs inside active window)."""
    # Active meeting with scheduled_end only 1 hour ago (inside 2h window -> NOT stale)
    c_fresh, m_fresh, _ = _create_consultation_and_meeting(
        db,
        meeting_status=VideoMeetingStatus.ACTIVE,
        scheduled_end_offset_hours=-1.0,
    )
    # Active meeting with scheduled_end 3 hours ago (outside 2h window -> IS stale)
    c_stale, m_stale, _ = _create_consultation_and_meeting(
        db,
        meeting_status=VideoMeetingStatus.ACTIVE,
        scheduled_end_offset_hours=-3.0,
    )

    service = VideoMeetingService(db)
    cleaned = service.cleanup_stale_meetings(max_idle_hours=2)

    db.refresh(m_fresh)
    db.refresh(m_stale)
    assert m_fresh.status == VideoMeetingStatus.ACTIVE
    assert m_stale.status == VideoMeetingStatus.ENDED
    assert cleaned >= 1


def test_cleanup_stale_meetings_repeated_execution_idempotent(db: Session):
    """Scenario 6: Repeated execution produces safe no-op on subsequent calls."""
    c, m, _ = _create_consultation_and_meeting(
        db,
        meeting_status=VideoMeetingStatus.ACTIVE,
        scheduled_end_offset_hours=-4.0,
    )
    service = VideoMeetingService(db)

    # First run cleans it
    cleaned_1 = service.cleanup_stale_meetings(max_idle_hours=2)
    assert cleaned_1 >= 1

    # Second run finds 0
    cleaned_2 = service.cleanup_stale_meetings(max_idle_hours=2)
    assert cleaned_2 == 0
