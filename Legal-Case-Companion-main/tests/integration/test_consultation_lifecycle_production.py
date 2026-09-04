import threading
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.consultation import Consultation, ConsultationStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import (
    AccountStatus,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.models.video_meeting import VideoMeeting, VideoMeetingStatus
from app.models.video_recording import VideoRecording, VideoRecordingStatus


def _setup_user(
    client: TestClient,
    db: Session,
    email: str,
    password: str = "Password123!",
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Test User",
) -> tuple[str, dict[str, str]]:
    """Register and login a test persona, returning (user_id, auth_headers)."""
    if role == UserRole.ADMIN:
        admin = User(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            account_status=AccountStatus.ACTIVE,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        user_id = str(admin.id)
    else:
        reg_res = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": full_name, "role": role.value},
        )
        assert reg_res.status_code == 201, reg_res.text
        user_id = str(reg_res.json()["id"])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200, login_res.text
    access_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    assert user is not None

    if role == UserRole.LAWYER and user.lawyer_profile:
        user.lawyer_profile.consultation_fee = 2000.0
        user.lawyer_profile.is_available = True
        verif = LawyerVerification(
            lawyer_profile_id=user.lawyer_profile.id,
            enrollment_number="DL/2026/PROD",
            state_bar_council="Delhi",
            status=VerificationStatus.APPROVED,
        )
        db.add(verif)
    db.commit()
    if role == UserRole.LAWYER:
        client.post("/api/v1/lawyers/heartbeat", json={"available_for_instant": True}, headers=headers)
    return user_id, headers


def test_terminal_state_transitions_strictly_rejected(client: TestClient, db: Session):
    """Verify that completed or cancelled consultations cannot be restarted or modified."""
    _c_id, h_client = _setup_user(client, db, "client_term@example.com", role=UserRole.CLIENT, full_name="Client Term")
    lawyer_id, h_lawyer = _setup_user(client, db, "lawyer_term@example.com", role=UserRole.LAWYER, full_name="Lawyer Term")

    # 1. Schedule a consultation
    target_dt = (datetime.now(UTC) + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    req_res = client.post(
        "/api/v1/consultations",
        headers=h_client,
        json={"lawyer_id": lawyer_id, "scheduled_at": target_dt.isoformat(), "duration_minutes": 30},
    )
    assert req_res.status_code == 201
    con_id = req_res.json()["id"]

    # 2. Lawyer accepts
    assert client.post(f"/api/v1/consultations/{con_id}/accept", headers=h_lawyer).status_code == 200

    # 3. Complete payment
    pay_res = client.post(f"/api/v1/consultations/{con_id}/payments", headers=h_client)
    assert pay_res.status_code == 201
    payment_id = pay_res.json()["payment_id"]
    payment = db.query(Payment).filter(Payment.id == UUID(payment_id)).first()
    assert payment is not None
    payment.status = PaymentStatus.SUCCEEDED
    consultation = db.query(Consultation).filter(Consultation.id == UUID(con_id)).first()
    assert consultation is not None
    consultation.status = ConsultationStatus.PAID
    db.commit()

    # 4. Schedule meeting
    sched_res = client.post(
        f"/api/v1/consultations/{con_id}/schedule",
        headers=h_lawyer,
        json={"scheduled_at": target_dt.isoformat(), "duration_minutes": 30},
    )
    assert sched_res.status_code == 200
    assert sched_res.json()["status"] == "SCHEDULED"

    # 5. Lawyer concludes consultation
    comp_res = client.post(f"/api/v1/consultations/{con_id}/complete", headers=h_lawyer)
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "COMPLETED"

    # 6. Verify terminal state rejection:
    # Cannot start video meeting
    start_res = client.post(f"/api/v1/consultations/{con_id}/video/start", headers=h_client)
    assert start_res.status_code in (400, 422)

    # Cannot cancel
    cancel_res = client.post(f"/api/v1/consultations/{con_id}/cancel", headers=h_client)
    assert cancel_res.status_code in (400, 422)

    # Cannot reschedule
    resched_res = client.post(
        f"/api/v1/consultations/{con_id}/reschedule",
        headers=h_client,
        json={"scheduled_at": (target_dt + timedelta(hours=2)).isoformat()},
    )
    assert resched_res.status_code in (400, 422)

    # Cannot mark no-show
    noshow_res = client.post(f"/api/v1/consultations/{con_id}/no-show", headers=h_lawyer)
    assert noshow_res.status_code in (400, 422)


def test_concurrency_and_double_start_protection(client: TestClient, db: Session):
    """Simultaneous start calls from Client and Lawyer must be idempotent and concurrency-safe."""
    _c_id, h_client = _setup_user(client, db, "client_race@example.com", role=UserRole.CLIENT, full_name="Client Race")
    lawyer_id, h_lawyer = _setup_user(client, db, "lawyer_race@example.com", role=UserRole.LAWYER, full_name="Lawyer Race")

    # Instant consultation (allows immediate start)
    now_utc = datetime.now(UTC)
    req_res = client.post(
        "/api/v1/consultations",
        headers=h_client,
        json={"lawyer_id": lawyer_id, "scheduled_at": now_utc.isoformat(), "duration_minutes": 30, "is_instant": True},
    )
    assert req_res.status_code == 201
    con_id = req_res.json()["id"]

    # One-click test payment
    pay_res = client.post(f"/api/v1/consultations/{con_id}/pay-test", headers=h_client)
    assert pay_res.status_code == 200

    results = []

    def call_start(headers):
        res = client.post(f"/api/v1/consultations/{con_id}/video/start", headers=headers)
        results.append(res)

    t1 = threading.Thread(target=call_start, args=(h_client,))
    t2 = threading.Thread(target=call_start, args=(h_lawyer,))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Both must succeed without crash or conflict
    for r in results:
        assert r.status_code == 200
        assert r.json()["status"] == "ACTIVE"

    # Verify consultation is now IN_PROGRESS
    con = db.query(Consultation).filter(Consultation.id == UUID(con_id)).first()
    assert con is not None
    assert con.status == ConsultationStatus.IN_PROGRESS

    # Additional repeat call is idempotent
    repeat_res = client.post(f"/api/v1/consultations/{con_id}/video/start", headers=h_client)
    assert repeat_res.status_code == 200
    assert repeat_res.json()["status"] == "ACTIVE"


def test_join_window_and_started_at_preservation(client: TestClient, db: Session):
    """Verify join returns started_at timestamp and authoritative consultation_status."""
    _c_id, h_client = _setup_user(client, db, "client_join@example.com", role=UserRole.CLIENT, full_name="Client Join")
    lawyer_id, _h_lawyer = _setup_user(client, db, "lawyer_join@example.com", role=UserRole.LAWYER, full_name="Lawyer Join")

    now_utc = datetime.now(UTC)
    req_res = client.post(
        "/api/v1/consultations",
        headers=h_client,
        json={"lawyer_id": lawyer_id, "scheduled_at": now_utc.isoformat(), "duration_minutes": 30, "is_instant": True},
    )
    assert req_res.status_code == 201
    con_id = req_res.json()["id"]

    # Mark paid and provision meeting
    client.post(f"/api/v1/consultations/{con_id}/pay-test", headers=h_client)

    # Start meeting
    start_res = client.post(f"/api/v1/consultations/{con_id}/video/start", headers=h_client)
    assert start_res.status_code == 200
    started_at = start_res.json()["started_at"]
    assert started_at is not None

    # Retrieve join info (simulating browser reload)
    join_res = client.get(f"/api/v1/consultations/{con_id}/video/join", headers=h_client)
    assert join_res.status_code == 200
    join_data = join_res.json()

    assert join_data["status"] == "ACTIVE"
    assert join_data["is_live"] is True
    assert join_data["consultation_status"] == "IN_PROGRESS"
    assert join_data["started_at"] is not None


def test_end_call_auto_finalizes_active_recording(client: TestClient, db: Session):
    """Ending a consultation must cleanly auto-stop and finalize active recordings."""
    _c_id, h_client = _setup_user(client, db, "client_rec@example.com", role=UserRole.CLIENT, full_name="Client Rec")
    lawyer_id, h_lawyer = _setup_user(client, db, "lawyer_rec@example.com", role=UserRole.LAWYER, full_name="Lawyer Rec")

    now_utc = datetime.now(UTC)
    req_res = client.post(
        "/api/v1/consultations",
        headers=h_client,
        json={"lawyer_id": lawyer_id, "scheduled_at": now_utc.isoformat(), "duration_minutes": 30, "is_instant": True},
    )
    con_id = req_res.json()["id"]
    client.post(f"/api/v1/consultations/{con_id}/pay-test", headers=h_client)
    client.post(f"/api/v1/consultations/{con_id}/video/start", headers=h_client)

    # Grant mutual consent
    client.post(f"/api/v1/consultations/{con_id}/video/recording/consent", headers=h_client, json={"consented": True})
    client.post(f"/api/v1/consultations/{con_id}/video/recording/consent", headers=h_lawyer, json={"consented": True})

    # Start recording
    rec_res = client.post(f"/api/v1/consultations/{con_id}/video/recording/start", headers=h_client)
    assert rec_res.status_code == 200
    rec_id = rec_res.json()["recording_id"]

    # Verify recording is currently RECORDING
    rec = db.query(VideoRecording).filter(VideoRecording.id == UUID(rec_id)).first()
    assert rec is not None
    assert rec.status == VideoRecordingStatus.RECORDING

    # End the meeting
    end_res = client.post(f"/api/v1/consultations/{con_id}/video/end", headers=h_lawyer)
    assert end_res.status_code == 200
    assert end_res.json()["status"] == "ENDED"

    # Verify recording was safely auto-stopped to UPLOADING (not left stranded)
    db.refresh(rec)
    assert rec.status == VideoRecordingStatus.UPLOADING
    assert rec.ended_at is not None
