from datetime import UTC, datetime

from fastapi.testclient import TestClient


def _setup_user(
    client: TestClient,
    email: str,
    password: str,
    role: str = "CLIENT",
    full_name: str = "Test User",
):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": role,
            "full_name": full_name,
        },
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_messaging_flow(client: TestClient, db):
    # Setup client and lawyer
    _client_id, h_client = _setup_user(
        client, "msg_client@ex.com", "Pass123!", "CLIENT"
    )
    lawyer_id, h_lawyer = _setup_user(client, "msg_lawyer@ex.com", "Pass123!", "LAWYER")
    _other_id, h_other = _setup_user(client, "msg_other@ex.com", "Pass123!", "CLIENT")

    # Verify lawyer
    from uuid import UUID

    from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus

    l_prof = (
        db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    )
    l_prof.consultation_fee = 0.0  # Free to simplify test

    from app.core.identifiers import generate_uuid7

    ver = LawyerVerification(
        id=generate_uuid7(),
        lawyer_profile_id=l_prof.id,
        enrollment_number="ABC",
        state_bar_council="Test",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()
    db.refresh(l_prof)

    # Request consultation
    fut = datetime.now(UTC).replace(year=2030, month=6, day=15, hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_req = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut, "duration_minutes": 60},
        headers=h_client,
    )
    c_id = res_req.json()["id"]

    # Client sends message
    res_msg1 = client.post(
        f"/api/v1/consultations/{c_id}/messages",
        json={"content": "Hello lawyer"},
        headers=h_client,
    )
    assert res_msg1.status_code == 201

    # Lawyer sends message
    res_msg2 = client.post(
        f"/api/v1/consultations/{c_id}/messages",
        json={"content": "Hello client"},
        headers=h_lawyer,
    )
    assert res_msg2.status_code == 201

    # Other user tries to read
    res_other = client.get(f"/api/v1/consultations/{c_id}/messages", headers=h_other)
    assert res_other.status_code == 404

    # Client reads messages
    res_msgs = client.get(f"/api/v1/consultations/{c_id}/messages", headers=h_client)
    assert res_msgs.status_code == 200
    items = res_msgs.json()
    assert len(items) == 2
    assert items[0]["content"] == "Hello lawyer"
    assert items[1]["content"] == "Hello client"


def test_messaging_blocked_on_terminal_statuses(client: TestClient, db):
    from uuid import UUID

    from app.core.identifiers import generate_uuid7
    from app.models.consultation import Consultation, ConsultationStatus
    from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus

    _client_id, h_client = _setup_user(
        client, "msg_term_client@ex.com", "Pass123!", "CLIENT"
    )
    lawyer_id, _h_lawyer = _setup_user(
        client, "msg_term_lawyer@ex.com", "Pass123!", "LAWYER"
    )

    l_prof = (
        db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    )
    l_prof.consultation_fee = 0.0

    ver = LawyerVerification(
        id=generate_uuid7(),
        lawyer_profile_id=l_prof.id,
        enrollment_number="ABC999",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()

    fut = datetime.now(UTC).replace(year=2030, month=6, day=15, hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_req = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut, "duration_minutes": 60},
        headers=h_client,
    )
    c_id = res_req.json()["id"]

    terminal_statuses = [
        ConsultationStatus.CANCELLED,
        ConsultationStatus.COMPLETED,
        ConsultationStatus.REJECTED,
        ConsultationStatus.NO_SHOW,
    ]

    for status in terminal_statuses:
        # Set consultation status directly
        consultation = db.query(Consultation).filter(Consultation.id == UUID(c_id)).first()
        consultation.status = status
        db.commit()

        # Attempt to send message
        res_send = client.post(
            f"/api/v1/consultations/{c_id}/messages",
            json={"content": f"Message during {status.value}"},
            headers=h_client,
        )
        assert res_send.status_code == 422
        assert "Cannot send messages" in res_send.json()["error"]["message"]
