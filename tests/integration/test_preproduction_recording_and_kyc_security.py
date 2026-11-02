import os
import uuid
from datetime import UTC, datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.core.security import create_access_token
from app.domain.consultations.video_recording_service import VideoRecordingService
from app.domain.consultations.recording_storage import LocalRecordingStorageProvider
from app.models.consultation import Consultation, ConsultationStatus
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole
from app.models.video_recording import VideoRecording, VideoRecordingConsent, VideoRecordingStatus
from app.models.audit import AuditEvent
from app.main import app


@pytest.fixture
def test_setup(db: Session, tmp_path):
    # Create Client A
    client_a = User(
        id=generate_uuid7(),
        email=f"client_a_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    # Create Client B (attacker / separate tenant)
    client_b = User(
        id=generate_uuid7(),
        email=f"client_b_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    # Create Lawyer
    lawyer = User(
        id=generate_uuid7(),
        email=f"lawyer_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    # Create Admin
    admin = User(
        id=generate_uuid7(),
        email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add_all([client_a, client_b, lawyer, admin])
    db.flush()

    c_prof_a = ClientProfile(user_id=client_a.id, full_name="Client Alpha")
    c_prof_b = ClientProfile(user_id=client_b.id, full_name="Client Beta")
    l_prof = LawyerProfile(id=generate_uuid7(), user_id=lawyer.id, full_name="Advocate Legal", consultation_fee=2500.0)
    db.add_all([c_prof_a, c_prof_b, l_prof])
    db.flush()

    now = datetime.now(UTC)
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=c_prof_a.id,
        lawyer_id=l_prof.id,
        scheduled_at=now + timedelta(minutes=10),
        duration_minutes=30,
        fee_amount=2500.0,
        currency="INR",
        status=ConsultationStatus.IN_PROGRESS,
    )
    db.add(consultation)
    db.flush()

    # Consents for recording
    db.add_all([
        VideoRecordingConsent(
            id=generate_uuid7(),
            consultation_id=consultation.id,
            user_id=client_a.id,
            role="CLIENT",
            consented=True,
            consented_at=now,
        ),
        VideoRecordingConsent(
            id=generate_uuid7(),
            consultation_id=consultation.id,
            user_id=lawyer.id,
            role="LAWYER",
            consented=True,
            consented_at=now,
        ),
    ])
    db.commit()

    from app.domain.consultations.recording_storage import reset_recording_storage_provider, get_recording_storage_provider
    rec_dir = str(tmp_path / "preprod_recordings")
    settings.LOCAL_RECORDING_STORAGE_PATH = rec_dir
    os.makedirs(rec_dir, exist_ok=True)
    reset_recording_storage_provider()
    storage = get_recording_storage_provider()
    rec_service = VideoRecordingService(db=db, storage_provider=storage)

    # Tokens
    token_client_a = create_access_token(str(client_a.id), "CLIENT")
    token_client_b = create_access_token(str(client_b.id), "CLIENT")
    token_lawyer = create_access_token(str(lawyer.id), "LAWYER")
    token_admin = create_access_token(str(admin.id), "ADMIN")

    return {
        "client_a": client_a,
        "client_b": client_b,
        "lawyer": lawyer,
        "admin": admin,
        "consultation": consultation,
        "rec_service": rec_service,
        "tokens": {
            "client_a": token_client_a,
            "client_b": token_client_b,
            "lawyer": token_lawyer,
            "admin": token_admin,
        },
    }


# =====================================================================
# TASK 3: RECORDING SECURITY VERIFICATION
# =====================================================================

def test_production_recording_disabled_by_default():
    """Verify that video recording remains strictly disabled by default."""
    assert settings.VIDEO_RECORDING_ENABLED is False, "Production recording MUST be disabled by default"


def test_recording_wrong_user_access_blocked(client: TestClient, test_setup, db: Session):
    """Verify Client B cannot request playback tickets or access Client A's recording."""
    f = test_setup
    service: VideoRecordingService = f["rec_service"]
    client_a = f["client_a"]
    consultation = f["consultation"]

    # Create available recording for Consultation
    rec = service.start_recording(client_a, consultation.id)
    service.stop_recording(client_a, consultation.id, rec.id)
    service.finalize_upload(client_a, consultation.id, rec.id, b"confidential_video_stream", "session.webm")

    # Client A can generate ticket
    res_a = client.post(
        f"/api/v1/recordings/{rec.id}/playback-ticket",
        headers={"Authorization": f"Bearer {f['tokens']['client_a']}"},
    )
    assert res_a.status_code == 200
    ticket_a = res_a.json()["ticket"]

    # Client B (attacker) attempts to request a ticket for Client A's recording -> MUST fail (404/403)
    res_b = client.post(
        f"/api/v1/recordings/{rec.id}/playback-ticket",
        headers={"Authorization": f"Bearer {f['tokens']['client_b']}"},
    )
    assert res_b.status_code in (403, 404), f"Expected 403/404 for wrong user, got {res_b.status_code}"

    # Client B attempts to play using Bearer token directly -> 404 IDOR defense
    res_play_b = client.get(
        f"/api/v1/recordings/{rec.id}/play",
        headers={"Authorization": f"Bearer {f['tokens']['client_b']}"},
    )
    assert res_play_b.status_code == 404


def test_recording_ticket_expiration_and_revocation(client: TestClient, test_setup, db: Session):
    """Verify ticket expiration, manual revocation, and replay prevention."""
    f = test_setup
    service: VideoRecordingService = f["rec_service"]
    client_a = f["client_a"]
    consultation = f["consultation"]

    rec = service.start_recording(client_a, consultation.id)
    service.stop_recording(client_a, consultation.id, rec.id)
    service.finalize_upload(client_a, consultation.id, rec.id, b"video_bytes_content_stream", "stream.webm")

    # 1. Valid ticket works
    res_ticket = client.post(
        f"/api/v1/recordings/{rec.id}/playback-ticket",
        headers={"Authorization": f"Bearer {f['tokens']['client_a']}"},
    )
    assert res_ticket.status_code == 200
    ticket = res_ticket.json()["ticket"]

    res_play = client.get(f"/api/v1/recordings/{rec.id}/play?ticket={ticket}")
    assert res_play.status_code == 200
    assert res_play.content == b"video_bytes_content_stream"
    # Verify Cache-Control headers
    assert "no-store" in res_play.headers.get("Cache-Control", "")
    assert "no-cache" in res_play.headers.get("Cache-Control", "")

    # 2. Revoke ticket -> subsequent playback MUST be rejected with 401
    service.revoke_playback_ticket(ticket)
    res_play_revoked = client.get(f"/api/v1/recordings/{rec.id}/play?ticket={ticket}")
    assert res_play_revoked.status_code == 401
    assert "revoked" in str(res_play_revoked.json()).lower()

    # 3. Expired ticket is rejected with 401
    expired_ticket = service.generate_playback_ticket(user=client_a, recording_id=rec.id, expires_in_seconds=-5)
    res_play_expired = client.get(f"/api/v1/recordings/{rec.id}/play?ticket={expired_ticket}")
    assert res_play_expired.status_code == 401
    assert "expired" in str(res_play_expired.json()).lower()


def test_recording_consultation_binding_and_replay_prevention_on_deleted(test_setup, db: Session):
    """Verify consultation binding and deletion invalidation."""
    f = test_setup
    service: VideoRecordingService = f["rec_service"]
    client_a = f["client_a"]
    consultation = f["consultation"]

    rec = service.start_recording(client_a, consultation.id)
    service.stop_recording(client_a, consultation.id, rec.id)
    service.finalize_upload(client_a, consultation.id, rec.id, b"video_data", "file.webm")

    ticket = service.generate_playback_ticket(client_a, rec.id, expires_in_seconds=60)

    # Verification against wrong consultation ID strictly fails
    other_cid = uuid.uuid4()
    with pytest.raises(Exception, match="not authorized for this consultation"):
        service.verify_playback_ticket(ticket=ticket, expected_recording_id=rec.id, expected_consultation_id=other_cid)

    # Delete recording -> ticket verification immediately fails
    service.delete_recording(client_a, rec.id)
    with pytest.raises(Exception):
        service.verify_playback_ticket(ticket=ticket, expected_recording_id=rec.id)


# =====================================================================
# TASK 4: KYC SECURITY & AUTHORIZATION VERIFICATION
# =====================================================================

def test_kyc_manipulated_storage_key_rejected(client: TestClient, test_setup):
    """Verify manipulated storage key (IDOR / traversal) is strictly rejected."""
    f = test_setup
    client_a = f["client_a"]
    client_b = f["client_b"]

    # Client B attempts to submit KYC claiming Client A's storage key
    payload_idor = {
        "full_name": "Client Beta",
        "phone": "+919876543210",
        "id_type": "PAN",
        "id_number": "ABCDE1234F",
        "address": "456 Cyber St",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pincode": "560001",
        "kyc_document_storage_key": f"kyc/{client_a.id}/aadhaar_client_a.pdf",
        "kyc_document_filename": "aadhaar.pdf",
    }
    res_idor = client.post(
        "/api/v1/kyc/client/submit",
        json=payload_idor,
        headers={"Authorization": f"Bearer {f['tokens']['client_b']}"},
    )
    assert res_idor.status_code == 403, f"Expected 403 Forbidden, got {res_idor.status_code}"

    # Path traversal storage key
    payload_traversal = payload_idor.copy()
    payload_traversal["kyc_document_storage_key"] = f"kyc/{client_b.id}/../../etc/passwd"
    res_trav = client.post(
        "/api/v1/kyc/client/submit",
        json=payload_traversal,
        headers={"Authorization": f"Bearer {f['tokens']['client_b']}"},
    )
    assert res_trav.status_code in (400, 403, 422)


def test_kyc_document_ownership_and_cross_user_isolation(client: TestClient, test_setup, db: Session):
    """Verify download authorization matrix and audit logging."""
    f = test_setup
    client_a = f["client_a"]
    client_b = f["client_b"]

    # 1. Client A submits legitimate KYC
    payload_a = {
        "full_name": "Client Alpha",
        "phone": "+919123456789",
        "id_type": "AADHAAR",
        "id_number": "123456789012",
        "address": "123 MG Road",
        "city": "Mumbai",
        "state": "Maharashtra",
        "pincode": "400001",
        "kyc_document_storage_key": f"kyc/{client_a.id}/national_id.pdf",
        "kyc_document_filename": "national_id.pdf",
    }
    res_sub = client.post(
        "/api/v1/kyc/client/submit",
        json=payload_a,
        headers={"Authorization": f"Bearer {f['tokens']['client_a']}"},
    )
    assert res_sub.status_code == 200

    # 2. Client A requests download URL -> 200 OK with short expiration
    res_dl_a = client.get(
        "/api/v1/kyc/client/document/download",
        headers={"Authorization": f"Bearer {f['tokens']['client_a']}"},
    )
    assert res_dl_a.status_code == 200
    data_a = res_dl_a.json()
    assert "download_url" in data_a
    assert data_a["expires_in_seconds"] <= 300

    # 3. Client B attempts to download Client A's document -> 403 Forbidden
    res_dl_b = client.get(
        f"/api/v1/kyc/client/document/download?user_id={client_a.id}",
        headers={"Authorization": f"Bearer {f['tokens']['client_b']}"},
    )
    assert res_dl_b.status_code == 403

    # 4. Lawyer attempts to download Client A's document -> 403 Forbidden
    res_dl_l = client.get(
        f"/api/v1/kyc/client/document/download?user_id={client_a.id}",
        headers={"Authorization": f"Bearer {f['tokens']['lawyer']}"},
    )
    assert res_dl_l.status_code == 403

    # 5. Admin CAN download Client A's document -> 200 OK
    res_dl_admin = client.get(
        f"/api/v1/kyc/client/document/download?user_id={client_a.id}",
        headers={"Authorization": f"Bearer {f['tokens']['admin']}"},
    )
    assert res_dl_admin.status_code == 200

    # 6. Audit Trail Check
    audit_events = db.query(AuditEvent).filter(
        AuditEvent.event_type == "KYC_DOCUMENT_DOWNLOADED",
        AuditEvent.actor_user_id == f["admin"].id,
    ).all()
    assert len(audit_events) >= 1
    assert audit_events[0].metadata_.get("target_user_id") == str(client_a.id)
