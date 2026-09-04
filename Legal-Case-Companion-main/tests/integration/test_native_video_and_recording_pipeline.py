import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConfigurationError, ValidationError
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
from app.models.video_recording import VideoRecording, VideoRecordingStatus
from app.services.video_meeting_service import (
    InternalWebRTCMeetingProvider,
    LiveKitMeetingProvider,
    get_video_provider,
)
from app.services.video_recording_service import VideoRecordingService


def _setup_user(
    client: TestClient,
    db: Session,
    email: str,
    password: str = "SecurePass123!",
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Test Participant",
) -> tuple[str, dict[str, str], str, uuid.UUID]:
    """Helper to create user and return (user_id, auth_headers, raw_token, profile_id)."""
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
        user.lawyer_profile.consultation_fee = 2000.0
        user.lawyer_profile.practice_areas = ["Constitutional Law", "Civil Litigation"]
        user.lawyer_profile.court_jurisdictions = ["Delhi High Court"]
        user.lawyer_profile.experience_years = 8
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
    return user_id, headers, access_token, profile_id


def _create_ready_consultation(
    db: Session,
    client_prof_id: uuid.UUID,
    lawyer_prof_id: uuid.UUID,
) -> str:
    """Creates a consultation ready within the 15-minute video window with status PAID."""
    future_time = datetime.now(UTC) + timedelta(minutes=5)
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_prof_id,
        lawyer_id=lawyer_prof_id,
        scheduled_at=future_time,
        duration_minutes=45,
        fee_amount=2000.0,
        currency="INR",
        status=ConsultationStatus.PAID,
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)
    return str(consultation.id)


def test_dual_consent_enforcement_and_recording_lifecycle(client: TestClient, db: Session):
    """
    Test Phase:
    1. Dual-consent is strictly required before starting recording.
    2. One participant consent is insufficient -> 400/422.
    3. Mutual consent allows recording start.
    4. Stop recording transitions state to UPLOADING.
    5. Binary streaming upload computes SHA-256 and transitions state to AVAILABLE.
    """
    # 1. Setup participants
    client_id, client_headers, client_token, client_prof_id = _setup_user(
        client, db, f"client_rec_{uuid.uuid4().hex[:6]}@test.lcc", role=UserRole.CLIENT, full_name="Rahul Varma"
    )
    lawyer_id, lawyer_headers, lawyer_token, lawyer_prof_id = _setup_user(
        client, db, f"lawyer_rec_{uuid.uuid4().hex[:6]}@test.lcc", role=UserRole.LAWYER, full_name="Adv. Meera Sen"
    )
    con_id = _create_ready_consultation(db, client_prof_id, lawyer_prof_id)

    # 2. Check initial consent status
    c_status = client.get(f"/api/v1/consultations/{con_id}/video/recording/consent-status", headers=client_headers)
    assert c_status.status_code == 200
    assert c_status.json()["can_record"] is False
    assert c_status.json()["client_consented"] is False
    assert c_status.json()["lawyer_consented"] is False

    # 3. Attempt to start recording without consent -> MUST FAIL
    rec_start_fail = client.post(f"/api/v1/consultations/{con_id}/video/recording/start", headers=client_headers)
    assert rec_start_fail.status_code in (400, 422)

    # 4. Client grants consent only
    client_consent_res = client.post(
        f"/api/v1/consultations/{con_id}/video/recording/consent",
        headers=client_headers,
        json={"consented": True},
    )
    assert client_consent_res.status_code == 200
    assert client_consent_res.json()["consented"] is True

    # Check status again -> still cannot record because lawyer hasn't consented
    c_status_2 = client.get(f"/api/v1/consultations/{con_id}/video/recording/consent-status", headers=client_headers)
    assert c_status_2.json()["client_consented"] is True
    assert c_status_2.json()["lawyer_consented"] is False
    assert c_status_2.json()["can_record"] is False

    # Attempt start recording -> MUST FAIL
    rec_start_fail2 = client.post(f"/api/v1/consultations/{con_id}/video/recording/start", headers=client_headers)
    assert rec_start_fail2.status_code in (400, 422)

    # 5. Lawyer grants consent
    lawyer_consent_res = client.post(
        f"/api/v1/consultations/{con_id}/video/recording/consent",
        headers=lawyer_headers,
        json={"consented": True},
    )
    assert lawyer_consent_res.status_code == 200

    # Check status -> now both consented!
    c_status_3 = client.get(f"/api/v1/consultations/{con_id}/video/recording/consent-status", headers=client_headers)
    assert c_status_3.json()["can_record"] is True

    # 6. Start recording -> SUCCEEDS
    rec_start_res = client.post(f"/api/v1/consultations/{con_id}/video/recording/start", headers=lawyer_headers)
    assert rec_start_res.status_code == 200, rec_start_res.text
    rec_data = rec_start_res.json()
    assert rec_data["status"] == "RECORDING"
    recording_id = rec_data["recording_id"]

    # Attempt duplicate start while recording active -> MUST FAIL
    rec_dup = client.post(f"/api/v1/consultations/{con_id}/video/recording/start", headers=client_headers)
    assert rec_dup.status_code in (400, 422)

    # 7. Stop recording -> SUCCEEDS and transitions to UPLOADING
    rec_stop_res = client.post(f"/api/v1/consultations/{con_id}/video/recording/stop", headers=lawyer_headers)
    assert rec_stop_res.status_code == 200, rec_stop_res.text
    assert rec_stop_res.json()["status"] == "UPLOADING"

    # 8. Upload binary video stream
    sample_webm_bytes = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01" + (b"DEMO_WEBM_VIDEO_DATA" * 50)
    expected_sha256 = hashlib.sha256(sample_webm_bytes).hexdigest()

    upload_res = client.post(
        f"/api/v1/consultations/{con_id}/video/recording/upload?recording_id={recording_id}&filename=session_rec.webm",
        headers={
            "Authorization": f"Bearer {client_token}",
            "Content-Type": "video/webm",
        },
        content=sample_webm_bytes,
    )
    assert upload_res.status_code == 200, upload_res.text
    final_rec = upload_res.json()
    assert final_rec["status"] == "AVAILABLE"
    assert final_rec["checksum_sha256"] == expected_sha256
    assert final_rec["file_size_bytes"] == len(sample_webm_bytes)

    # 9. List consultation recordings
    list_res = client.get(f"/api/v1/consultations/{con_id}/recordings", headers=client_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()["items"]) == 1
    assert list_res.json()["items"][0]["id"] == recording_id


def test_http_206_partial_content_playback_and_token_query(client: TestClient, db: Session):
    """
    Test Phase:
    1. Full playback request returns HTTP 200, Accept-Ranges, and security headers.
    2. Byte range requests return HTTP 206 Partial Content with precise slices.
    3. Normal bearer access token in query string (?token=...) is strictly REJECTED (HTTP 401) to prevent URL token leakage.
    4. Ephemeral media playback ticket pattern works seamlessly via ?ticket=.
    5. Cache-Control and security headers prevent private legal consultation recording caching.
    """
    # 1. Setup session and recording
    client_id, client_headers, client_token, client_prof_id = _setup_user(
        client, db, f"client_stream_{uuid.uuid4().hex[:6]}@test.lcc", role=UserRole.CLIENT, full_name="Sanjay Rao"
    )
    lawyer_id, lawyer_headers, lawyer_token, lawyer_prof_id = _setup_user(
        client, db, f"lawyer_stream_{uuid.uuid4().hex[:6]}@test.lcc", role=UserRole.LAWYER, full_name="Adv. Kavita Roy"
    )
    con_id = _create_ready_consultation(db, client_prof_id, lawyer_prof_id)

    # Both consent and record
    client.post(f"/api/v1/consultations/{con_id}/video/recording/consent", headers=client_headers, json={"consented": True})
    client.post(f"/api/v1/consultations/{con_id}/video/recording/consent", headers=lawyer_headers, json={"consented": True})

    start_res = client.post(f"/api/v1/consultations/{con_id}/video/recording/start", headers=lawyer_headers)
    recording_id = start_res.json()["recording_id"]
    client.post(f"/api/v1/consultations/{con_id}/video/recording/stop", headers=lawyer_headers)

    # Upload 1920 bytes payload
    payload = b"VIDEO_CHUNK_" * 160
    client.post(
        f"/api/v1/consultations/{con_id}/video/recording/upload?recording_id={recording_id}&filename=stream_test.webm",
        headers={"Authorization": f"Bearer {lawyer_token}", "Content-Type": "video/webm"},
        content=payload,
    )

    # 2. Stream without Range header using Authorization Header (HTTP 200)
    res_full = client.get(f"/api/v1/recordings/{recording_id}/play", headers=client_headers)
    assert res_full.status_code == 200
    assert res_full.headers["Accept-Ranges"] == "bytes"
    assert res_full.headers["Content-Type"] == "video/webm"
    assert "no-store" in res_full.headers["Cache-Control"]
    assert "private" in res_full.headers["Cache-Control"]
    assert res_full.headers["X-Content-Type-Options"] == "nosniff"
    assert res_full.content == payload

    # 3. Stream with Range header: bytes=0-499 (HTTP 206)
    res_partial = client.get(
        f"/api/v1/recordings/{recording_id}/play",
        headers={**client_headers, "Range": "bytes=0-499"},
    )
    assert res_partial.status_code == 206
    assert res_partial.headers["Content-Range"] == f"bytes 0-499/{len(payload)}"
    assert res_partial.headers["Content-Length"] == "500"
    assert res_partial.content == payload[0:500]

    # 4. Phase 5 Security: Normal bearer access token in query string (?token=...) MUST BE REJECTED
    res_raw_token_rejected = client.get(f"/api/v1/recordings/{recording_id}/play?token={client_token}")
    assert res_raw_token_rejected.status_code == 401
    assert "forbidden" in res_raw_token_rejected.text.lower()

    # 5. Phase 5 Ephemeral Ticket: Request ticket with auth header
    ticket_res = client.post(f"/api/v1/recordings/{recording_id}/playback-ticket", headers=client_headers)
    assert ticket_res.status_code == 200, ticket_res.text
    ticket_data = ticket_res.json()
    assert "ticket" in ticket_data
    assert ticket_data["expires_in_seconds"] == 60
    playback_ticket = ticket_data["ticket"]

    # Playback using Ephemeral Ticket (?ticket=...)
    res_ticket_playback = client.get(
        f"/api/v1/recordings/{recording_id}/play?ticket={playback_ticket}",
        headers={"Range": "bytes=0-99"},
    )
    assert res_ticket_playback.status_code == 206
    assert res_ticket_playback.content == payload[0:100]

    # 6. Tampered or expired ticket is rejected
    res_tampered_ticket = client.get(f"/api/v1/recordings/{recording_id}/play?ticket={playback_ticket}tampered")
    assert res_tampered_ticket.status_code == 401

    # 7. Out of bounds range request returns 416
    res_oob = client.get(
        f"/api/v1/recordings/{recording_id}/play",
        headers={**client_headers, "Range": f"bytes={len(payload) + 100}-{len(payload) + 200}"},
    )
    assert res_oob.status_code == 416


def test_file_tamper_checksum_mismatch_fails_playback(client: TestClient, db: Session):
    """
    Phase 11:
    Verify that if the physical file on disk is modified/tampered after ingestion,
    cryptographic integrity verification detects the mismatch and playback is rejected.
    """
    # 1. Setup session and recording
    _, client_headers, client_token, client_prof_id = _setup_user(
        client, db, f"client_tamper_{uuid.uuid4().hex[:6]}@test.lcc", role=UserRole.CLIENT
    )
    lawyer_id, lawyer_headers, _, lawyer_prof_id = _setup_user(
        client, db, f"lawyer_tamper_{uuid.uuid4().hex[:6]}@test.lcc", role=UserRole.LAWYER
    )
    con_id = _create_ready_consultation(db, client_prof_id, lawyer_prof_id)

    client.post(f"/api/v1/consultations/{con_id}/video/recording/consent", headers=client_headers, json={"consented": True})
    client.post(f"/api/v1/consultations/{con_id}/video/recording/consent", headers=lawyer_headers, json={"consented": True})

    start_res = client.post(f"/api/v1/consultations/{con_id}/video/recording/start", headers=lawyer_headers)
    rec_id = start_res.json()["recording_id"]
    client.post(f"/api/v1/consultations/{con_id}/video/recording/stop", headers=lawyer_headers)

    original_bytes = b"GENUINE_CONSULTATION_AUDIO_VIDEO_DATA"
    client.post(
        f"/api/v1/consultations/{con_id}/video/recording/upload?recording_id={rec_id}&filename=integrity_test.webm",
        headers={"Authorization": f"Bearer {client_token}", "Content-Type": "video/webm"},
        content=original_bytes,
    )

    # Verify initial playback succeeds
    initial_res = client.get(f"/api/v1/recordings/{rec_id}/play", headers=client_headers)
    assert initial_res.status_code == 200
    assert initial_res.content == original_bytes

    # 2. Tamper with the physical file on disk (simulate storage corruption / file modification)
    rec_record = db.query(VideoRecording).filter(VideoRecording.id == UUID(rec_id)).first()
    assert rec_record is not None
    service = VideoRecordingService(db)
    physical_path = service.storage_provider.get_recording_path(rec_record.storage_path)

    with open(physical_path, "ab") as f:
        f.write(b"CORRUPTING_EXTRA_BYTES_FOR_TEST")

    # 3. Playback MUST FAIL due to cryptographic integrity verification mismatch
    tampered_res = client.get(f"/api/v1/recordings/{rec_id}/play", headers=client_headers)
    assert tampered_res.status_code == 400
    assert "integrity verification failed" in tampered_res.text.lower()


def test_production_provider_policy_no_silent_fallback(monkeypatch):
    """
    Phase 2 & 28:
    Verify that in production mode, missing LiveKit configuration raises ConfigurationError
    rather than silently falling back to Internal WebRTC P2P mesh.
    """
    # 1. In Development without LiveKit: P2P is allowed
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "LIVEKIT_URL", None)
    monkeypatch.setattr(settings, "LIVEKIT_API_KEY", None)
    monkeypatch.setattr(settings, "LIVEKIT_API_SECRET", None)

    dev_provider = get_video_provider()
    assert isinstance(dev_provider, InternalWebRTCMeetingProvider)

    # 2. In Production without LiveKit: Silent fallback is strictly FORBIDDEN
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "LIVEKIT_URL", None)
    monkeypatch.setattr(settings, "LIVEKIT_API_KEY", None)
    monkeypatch.setattr(settings, "LIVEKIT_API_SECRET", None)

    with pytest.raises(ConfigurationError) as excinfo:
        get_video_provider()
    assert "Production environment requires LiveKit SFU configuration" in str(excinfo.value)
    assert "Silent fallback to internal P2P is strictly forbidden" in str(excinfo.value)

    # 3. In Production with LiveKit: LiveKitMeetingProvider returned
    monkeypatch.setattr(settings, "LIVEKIT_URL", "https://sfu.lcc.production:7880")
    monkeypatch.setattr(settings, "LIVEKIT_API_KEY", "prod-key")
    monkeypatch.setattr(settings, "LIVEKIT_API_SECRET", "prod-secret-key-32-characters-min")

    prod_provider = get_video_provider()
    assert isinstance(prod_provider, LiveKitMeetingProvider)


def test_livekit_token_cross_room_and_impersonation_rejection():
    """
    Phase 3:
    Verify that LiveKit tokens are room-scoped and role-scoped:
    - Token for consultation A / room A cannot join room B.
    - Token issued for Client cannot impersonate Lawyer.
    """
    provider = LiveKitMeetingProvider(
        livekit_url="https://sfu.lcc.internal:7880",
        api_key="lcc-key",
        api_secret="lcc-secret-32-characters-long-min",
    )

    client_user = User(
        id=uuid.uuid4(),
        email="client_a@lcc.test",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    meeting_a = VideoMeeting(
        id=generate_uuid7(),
        consultation_id=uuid.uuid4(),
        room_id="room-alpha-123",
        status=VideoMeetingStatus.SCHEDULED,
    )

    # Generate token for meeting A as CLIENT
    token_a = provider.generate_access_token(
        user=client_user,
        meeting=meeting_a,
        role="CLIENT",
        expires_in_seconds=3600,
    )

    # 1. Validation for room A succeeds
    valid_payload = provider.verify_access_token(
        token=token_a,
        expected_room_id="room-alpha-123",
        expected_user_id=client_user.id,
        expected_consultation_id=meeting_a.consultation_id,
        expected_role="CLIENT",
    )
    assert valid_payload["sub"] == str(client_user.id)

    # 2. Token for room A used on room B MUST FAIL
    with pytest.raises(ValidationError) as err_room:
        provider.verify_access_token(
            token=token_a,
            expected_room_id="room-beta-999",
        )
    assert "not authorized for this meeting room" in str(err_room.value)

    # 3. Token for Client attempting to claim Lawyer role MUST FAIL
    with pytest.raises(ValidationError) as err_role:
        provider.verify_access_token(
            token=token_a,
            expected_room_id="room-alpha-123",
            expected_role="LAWYER",
        )
    assert "role does not match" in str(err_role.value)


def test_concurrency_recording_guards(client: TestClient, db: Session):
    """
    Phase 25:
    Test concurrency protections:
    - Two consecutive recording start calls fail on the second attempt.
    - Two consecutive recording stop calls fail on the second attempt.
    - Finalizing an already available recording fails.
    """
    # 1. Setup session
    _, client_headers, client_token, client_prof_id = _setup_user(
        client, db, f"client_conc_{uuid.uuid4().hex[:6]}@test.lcc", role=UserRole.CLIENT
    )
    _, lawyer_headers, _, lawyer_prof_id = _setup_user(
        client, db, f"lawyer_conc_{uuid.uuid4().hex[:6]}@test.lcc", role=UserRole.LAWYER
    )
    con_id = _create_ready_consultation(db, client_prof_id, lawyer_prof_id)

    client.post(f"/api/v1/consultations/{con_id}/video/recording/consent", headers=client_headers, json={"consented": True})
    client.post(f"/api/v1/consultations/{con_id}/video/recording/consent", headers=lawyer_headers, json={"consented": True})

    # 2. First start succeeds
    start_1 = client.post(f"/api/v1/consultations/{con_id}/video/recording/start", headers=lawyer_headers)
    assert start_1.status_code == 200
    rec_id = start_1.json()["recording_id"]

    # Second concurrent start MUST FAIL
    start_2 = client.post(f"/api/v1/consultations/{con_id}/video/recording/start", headers=lawyer_headers)
    assert start_2.status_code in (400, 422)

    # 3. First stop succeeds
    stop_1 = client.post(f"/api/v1/consultations/{con_id}/video/recording/stop", headers=lawyer_headers)
    assert stop_1.status_code == 200

    # Second concurrent stop MUST FAIL
    stop_2 = client.post(f"/api/v1/consultations/{con_id}/video/recording/stop", headers=lawyer_headers)
    assert stop_2.status_code in (400, 404, 422)

    # 4. Upload and finalize
    upload_res = client.post(
        f"/api/v1/consultations/{con_id}/video/recording/upload?recording_id={rec_id}&filename=conc_test.webm",
        headers={"Authorization": f"Bearer {client_token}", "Content-Type": "video/webm"},
        content=b"CONCURRENCY_TEST_RECORDING_PAYLOAD",
    )
    assert upload_res.status_code == 200

    # Second finalize attempt on already finalized recording MUST FAIL
    upload_dup = client.post(
        f"/api/v1/consultations/{con_id}/video/recording/upload?recording_id={rec_id}&filename=conc_test.webm",
        headers={"Authorization": f"Bearer {client_token}", "Content-Type": "video/webm"},
        content=b"EXTRA_PAYLOAD",
    )
    assert upload_dup.status_code in (400, 422)


def test_recording_and_video_bola_unauthorized_isolation(client: TestClient, db: Session):
    """
    Test Phase:
    Verify that an unrelated third party (IDOR/BOLA attacker) is strictly blocked
    with 404 (ResourceNotFoundError) to prevent information enumeration.
    """
    # 1. Genuine consultation participants
    _, client_headers, client_token, client_prof_id = _setup_user(
        client, db, f"legit_client_{uuid.uuid4().hex[:6]}@test.lcc", role=UserRole.CLIENT
    )
    lawyer_id, lawyer_headers, _, lawyer_prof_id = _setup_user(
        client, db, f"legit_lawyer_{uuid.uuid4().hex[:6]}@test.lcc", role=UserRole.LAWYER
    )
    con_id = _create_ready_consultation(db, client_prof_id, lawyer_prof_id)

    # Mutual consent and record
    client.post(f"/api/v1/consultations/{con_id}/video/recording/consent", headers=client_headers, json={"consented": True})
    client.post(f"/api/v1/consultations/{con_id}/video/recording/consent", headers=lawyer_headers, json={"consented": True})
    start_res = client.post(f"/api/v1/consultations/{con_id}/video/recording/start", headers=lawyer_headers)
    rec_id = start_res.json()["recording_id"]
    client.post(f"/api/v1/consultations/{con_id}/video/recording/stop", headers=lawyer_headers)
    client.post(
        f"/api/v1/consultations/{con_id}/video/recording/upload?recording_id={rec_id}&filename=secret.webm",
        headers={"Authorization": f"Bearer {client_token}", "Content-Type": "video/webm"},
        content=b"CONFIDENTIAL_LEGAL_CONSULTATION_DATA",
    )

    # 2. Attacker user
    _, attacker_headers, attacker_token, _ = _setup_user(
        client, db, f"attacker_{uuid.uuid4().hex[:6]}@test.lcc", role=UserRole.CLIENT, full_name="Malicious Actor"
    )

    # BOLA: Attacker cannot access video join info
    att_join = client.get(f"/api/v1/consultations/{con_id}/video/join", headers=attacker_headers)
    assert att_join.status_code == 404

    # BOLA: Attacker cannot list recordings
    att_list = client.get(f"/api/v1/consultations/{con_id}/recordings", headers=attacker_headers)
    assert att_list.status_code == 404

    # BOLA: Attacker cannot stream playback (returns 404 IDOR defense)
    att_play = client.get(f"/api/v1/recordings/{rec_id}/play", headers=attacker_headers)
    assert att_play.status_code == 404

    # BOLA: Attacker cannot obtain playback ticket for unauthorized recording
    att_ticket = client.post(f"/api/v1/recordings/{rec_id}/playback-ticket", headers=attacker_headers)
    assert att_ticket.status_code == 404


def test_websocket_signaling_chat_and_media_status_relay(client: TestClient, db: Session):
    """
    Test Phase:
    Verify that in-meeting chat, media-status updates, and recording-status updates
    are securely relayed across authenticated WebSockets between consultation participants.
    """
    # 1. Setup session
    client_id, client_headers, _, client_prof_id = _setup_user(
        client, db, f"ws_client_{uuid.uuid4().hex[:6]}@test.lcc", role=UserRole.CLIENT, full_name="Arun Nair"
    )
    lawyer_id, lawyer_headers, _, lawyer_prof_id = _setup_user(
        client, db, f"ws_lawyer_{uuid.uuid4().hex[:6]}@test.lcc", role=UserRole.LAWYER, full_name="Adv. Priya Das"
    )
    con_id = _create_ready_consultation(db, client_prof_id, lawyer_prof_id)

    # 2. Obtain HMAC tokens
    c_join = client.get(f"/api/v1/consultations/{con_id}/video/join", headers=client_headers).json()
    l_join = client.get(f"/api/v1/consultations/{con_id}/video/join", headers=lawyer_headers).json()

    c_token = c_join["token"]
    l_token = l_join["token"]

    # 3. Connect both to WebSocket
    with client.websocket_connect(f"/api/v1/consultations/{con_id}/video/ws?token={c_token}") as ws_client:
        with client.websocket_connect(f"/api/v1/consultations/{con_id}/video/ws?token={l_token}") as ws_lawyer:
            # Client should receive peer-joined for lawyer who just connected
            peer_joined = json.loads(ws_client.receive_text())
            assert peer_joined["type"] == "peer-joined"
            assert peer_joined["user_id"] == lawyer_id
            assert peer_joined["role"] == "LAWYER"

            # Lawyer should receive existing-peer for client who was already connected
            existing_peer = json.loads(ws_lawyer.receive_text())
            assert existing_peer["type"] == "existing-peer"
            assert existing_peer["user_id"] == client_id
            assert existing_peer["role"] == "CLIENT"

            # 4. In-meeting scoped Chat message relay
            chat_payload = {
                "type": "chat",
                "content": "Please review Section 9 of the Arbitration Act.",
                "sender_name": "Adv. Priya Das",
                "timestamp": "11:30 AM",
            }
            ws_lawyer.send_text(json.dumps(chat_payload))

            received_chat = json.loads(ws_client.receive_text())
            assert received_chat["type"] == "chat"
            assert received_chat["content"] == "Please review Section 9 of the Arbitration Act."
            assert received_chat["from_user_id"] == lawyer_id
            assert received_chat["from_role"] == "LAWYER"

            # 5. In-meeting media status relay
            media_status_payload = {
                "type": "media-status",
                "is_muted": True,
                "is_video_off": False,
                "is_screen_sharing": True,
            }
            ws_client.send_text(json.dumps(media_status_payload))

            received_status = json.loads(ws_lawyer.receive_text())
            assert received_status["type"] == "media-status"
            assert received_status["is_muted"] is True
            assert received_status["is_screen_sharing"] is True
            assert received_status["from_user_id"] == client_id

            # 6. In-meeting recording status relay
            rec_status_payload = {
                "type": "recording-status",
                "status": "RECORDING",
                "recording_id": "test-rec-uuid",
            }
            ws_lawyer.send_text(json.dumps(rec_status_payload))

            received_rec = json.loads(ws_client.receive_text())
            assert received_rec["type"] == "recording-status"
            assert received_rec["status"] == "RECORDING"
