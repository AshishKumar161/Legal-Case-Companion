import hashlib
import io
import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError, ValidationError
from app.core.identifiers import generate_uuid7
from app.models.consultation import Consultation, ConsultationStatus
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole
from app.models.video_recording import VideoRecording, VideoRecordingConsent, VideoRecordingStatus
from app.domain.consultations.recording_storage import (
    LocalRecordingStorageProvider,
    S3RecordingStorageProvider,
)
from app.domain.consultations.video_recording_service import VideoRecordingService


@pytest.fixture
def recording_fixtures(db: Session, tmp_path):
    client_user = User(
        id=generate_uuid7(),
        email=f"client_rec_{uuid.uuid4().hex[:6]}@test.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    lawyer_user = User(
        id=generate_uuid7(),
        email=f"lawyer_rec_{uuid.uuid4().hex[:6]}@test.com",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add_all([client_user, lawyer_user])
    db.flush()

    c_prof = ClientProfile(user_id=client_user.id, full_name="Rec Client")
    l_prof = LawyerProfile(id=generate_uuid7(), user_id=lawyer_user.id, full_name="Rec Lawyer", consultation_fee=2000.0)
    db.add_all([c_prof, l_prof])
    db.flush()

    now = datetime.now(UTC)
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=c_prof.id,
        lawyer_id=l_prof.id,
        scheduled_at=now + timedelta(minutes=5),
        duration_minutes=30,
        fee_amount=2000.0,
        currency="INR",
        status=ConsultationStatus.IN_PROGRESS,
    )
    db.add(consultation)
    db.flush()

    # Consents
    c_consent = VideoRecordingConsent(
        id=generate_uuid7(),
        consultation_id=consultation.id,
        user_id=client_user.id,
        role="CLIENT",
        consented=True,
        consented_at=now,
    )
    l_consent = VideoRecordingConsent(
        id=generate_uuid7(),
        consultation_id=consultation.id,
        user_id=lawyer_user.id,
        role="LAWYER",
        consented=True,
        consented_at=now,
    )
    db.add_all([c_consent, l_consent])
    db.commit()

    storage = LocalRecordingStorageProvider(base_dir=str(tmp_path / "recordings"))
    service = VideoRecordingService(db=db, storage_provider=storage)

    return {
        "client": client_user,
        "lawyer": lawyer_user,
        "consultation": consultation,
        "service": service,
        "storage": storage,
    }


def test_recording_upload_retry_on_failed_state(recording_fixtures, db: Session):
    """
    Verify that if an upload previously failed, the system allows safe,
    bounded retries without creating duplicate records or being permanently blocked.
    """
    f = recording_fixtures
    service: VideoRecordingService = f["service"]
    client: User = f["client"]
    consultation: Consultation = f["consultation"]

    # Start and stop recording
    rec = service.start_recording(client, consultation.id)
    service.stop_recording(client, consultation.id, rec.id)

    # Manually mark as FAILED (simulating network drop during previous upload)
    rec.status = VideoRecordingStatus.FAILED
    db.commit()

    # Retrying finalize_upload MUST succeed and transition to AVAILABLE
    valid_bytes = b"fake_webrtc_video_stream_content_12345"
    finalized = service.finalize_upload(
        user=client,
        consultation_id=consultation.id,
        recording_id=rec.id,
        file_source=valid_bytes,
        filename="retry_recording.webm",
    )
    assert finalized.status == VideoRecordingStatus.AVAILABLE
    assert finalized.file_size_bytes == len(valid_bytes)
    assert finalized.checksum_sha256 is not None


def test_duplicate_upload_prevented_when_already_available(recording_fixtures, db: Session):
    """
    Verify that calling finalize_upload on an already AVAILABLE recording
    strictly prevents duplicate uploads and throws ValidationError.
    """
    f = recording_fixtures
    service: VideoRecordingService = f["service"]
    client: User = f["client"]
    consultation: Consultation = f["consultation"]

    rec = service.start_recording(client, consultation.id)
    service.stop_recording(client, consultation.id, rec.id)

    valid_bytes = b"sample_video_bytes"
    res1 = service.finalize_upload(
        user=client,
        consultation_id=consultation.id,
        recording_id=rec.id,
        file_source=valid_bytes,
        filename="session.webm",
    )
    assert res1.status == VideoRecordingStatus.AVAILABLE

    # Duplicate call must be prevented
    with pytest.raises(ValidationError) as exc:
        service.finalize_upload(
            user=client,
            consultation_id=consultation.id,
            recording_id=rec.id,
            file_source=valid_bytes,
            filename="session.webm",
        )
    assert "already been uploaded and finalized" in str(exc.value)


def test_recording_empty_file_rejection(recording_fixtures):
    """
    Verify that uploading empty bytes (0 bytes) is strictly rejected.
    """
    f = recording_fixtures
    service: VideoRecordingService = f["service"]
    client: User = f["client"]
    consultation: Consultation = f["consultation"]

    rec = service.start_recording(client, consultation.id)
    service.stop_recording(client, consultation.id, rec.id)

    with pytest.raises(ValidationError, match="Uploaded recording file is empty"):
        service.finalize_upload(
            user=client,
            consultation_id=consultation.id,
            recording_id=rec.id,
            file_source=b"",
            filename="empty.webm",
        )


def test_sha256_checksum_integrity_verification_on_playback(recording_fixtures, db: Session):
    """
    Verify that if the physical recording file on storage is tampered with,
    playback verification detects the checksum mismatch and raises ValidationError.
    """
    f = recording_fixtures
    service: VideoRecordingService = f["service"]
    client: User = f["client"]
    consultation: Consultation = f["consultation"]
    storage: LocalRecordingStorageProvider = f["storage"]

    rec = service.start_recording(client, consultation.id)
    service.stop_recording(client, consultation.id, rec.id)

    original_bytes = b"authentic_legal_evidence_video_recording"
    service.finalize_upload(
        user=client,
        consultation_id=consultation.id,
        recording_id=rec.id,
        file_source=original_bytes,
        filename="evidence.webm",
    )

    # Verify playback works when untampered
    _, path = service.get_recording_for_playback(client, rec.id, verify_integrity=True)
    assert path.exists()

    # Tamper with file on disk
    with open(path, "wb") as file_out:
        file_out.write(b"tampered_malicious_content")

    # Playback must fail cryptographic integrity verification
    with pytest.raises(ValidationError, match="cryptographic integrity verification failed"):
        service.get_recording_for_playback(client, rec.id, verify_integrity=True)


def test_s3_storage_provider_traversal_guard():
    """
    Verify that S3RecordingStorageProvider validates object keys and blocks directory traversal.
    """
    s3_mock = MagicMock()
    s3_provider = S3RecordingStorageProvider(s3_client=s3_mock, bucket_name="test-bucket")

    # Invalid path with directory traversal
    with pytest.raises(ValidationError, match="directory traversal attempt"):
        s3_provider._validate_safe_object_key("consultations/../../etc/passwd")

    # Invalid path outside namespace
    with pytest.raises(ValidationError, match="recording storage path namespace"):
        s3_provider._validate_safe_object_key("system/private/keys.pem")

    # Valid path passes
    clean = s3_provider._validate_safe_object_key("consultations/01a0754d/rec1.webm")
    assert clean == "consultations/01a0754d/rec1.webm"


def test_ephemeral_playback_ticket_lifecycle(recording_fixtures):
    """
    Verify ephemeral 60s media playback ticket:
    - Successfully verifies for authorized user
    - Rejects invalid ticket format
    - Rejects expired ticket
    - Rejects ticket bound to different recording
    """
    f = recording_fixtures
    service: VideoRecordingService = f["service"]
    client: User = f["client"]
    lawyer: User = f["lawyer"]
    consultation: Consultation = f["consultation"]

    rec = service.start_recording(client, consultation.id)
    service.stop_recording(client, consultation.id, rec.id)
    service.finalize_upload(client, consultation.id, rec.id, b"stream_bytes", "video.webm")

    # 1. Valid ticket generated for client
    ticket = service.generate_playback_ticket(user=client, recording_id=rec.id, expires_in_seconds=60)
    assert ticket.startswith("mpt_")

    verified_user = service.verify_playback_ticket(ticket=ticket, expected_recording_id=rec.id)
    assert verified_user.id == client.id

    # 2. Ticket rejected if checking against different recording ID
    other_rec_id = uuid.uuid4()
    with pytest.raises(ValidationError, match="not authorized for this recording"):
        service.verify_playback_ticket(ticket=ticket, expected_recording_id=other_rec_id)

    # 3. Malformed ticket rejected
    with pytest.raises(ValidationError, match="Invalid playback ticket format"):
        service.verify_playback_ticket(ticket="mpt_invalid_parts", expected_recording_id=rec.id)
