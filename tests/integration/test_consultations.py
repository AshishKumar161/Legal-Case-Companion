from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


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


def test_consultation_flow(client: TestClient, db: Session):
    # Setup client and lawyer
    _client_id, h_client = _setup_user(
        client, "client.c@example.com", "Pass123!", "CLIENT"
    )
    lawyer_id, h_lawyer = _setup_user(
        client, "lawyer.c@example.com", "Pass123!", "LAWYER"
    )

    # Verify lawyer
    from uuid import UUID

    from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus

    l_prof = (
        db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    )
    assert l_prof is not None
    l_prof.consultation_fee = 0

    # Create verification record
    from app.core.identifiers import generate_uuid7

    ver = LawyerVerification(
        id=generate_uuid7(),
        lawyer_profile_id=l_prof.id,
        enrollment_number="ABC/123/2020",
        state_bar_council="Test",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()
    db.refresh(l_prof)

    # Create case and assign lawyer
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Consult Case", "description": "D"},
        headers=h_client,
    )
    case_id = res_case.json()["id"]
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_client,
    )

    # Request consultation (10:00 UTC = 15:30 IST)
    fut = datetime.now(UTC).replace(year=2030, month=6, day=15, hour=10, minute=0, second=0, microsecond=0).isoformat()
    payload = {
        "lawyer_id": lawyer_id,
        "case_id": case_id,
        "scheduled_at": fut,
        "duration_minutes": 60,
    }
    res_req = client.post("/api/v1/consultations", json=payload, headers=h_client)
    assert res_req.status_code == 201
    c_id = res_req.json()["id"]
    assert res_req.json()["status"] == "REQUESTED"

    # Verify timeline
    res_time = client.get(f"/api/v1/cases/{case_id}/timeline", headers=h_client)
    assert "CONSULTATION_REQUESTED" in [
        e["event_type"] for e in res_time.json()["items"]
    ]

    # Reject BOLA (unauthorized user trying to access consultation)
    _other_id, h_other = _setup_user(
        client, "other.c@example.com", "Pass123!", "CLIENT"
    )
    res_bola = client.get(f"/api/v1/consultations/{c_id}", headers=h_other)
    assert res_bola.status_code == 404

    # Confirm as lawyer
    res_conf = client.post(f"/api/v1/consultations/{c_id}/confirm", headers=h_lawyer)
    assert res_conf.status_code == 200
    assert res_conf.json()["status"] == "SCHEDULED"

    # Cancel as client
    res_canc = client.post(f"/api/v1/consultations/{c_id}/cancel", headers=h_client)
    assert res_canc.status_code == 200
    assert res_canc.json()["status"] == "CANCELLED"


def test_consultation_booking_business_hours_and_self_booking(client: TestClient, db: Session):
    _client_id, h_client = _setup_user(client, "bh_client@test.com", "Pass123!", "CLIENT")
    lawyer_id, _h_lawyer = _setup_user(client, "bh_lawyer@test.com", "Pass123!", "LAWYER")

    # Approve lawyer
    from uuid import UUID

    from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus

    lp = db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    assert lp is not None
    db.add(
        LawyerVerification(
            lawyer_profile_id=lp.id,
            enrollment_number="BH/123/2020",
            state_bar_council="Delhi",
            status=VerificationStatus.APPROVED,
        )
    )
    db.commit()

    # 1. Self-booking rejection
    # Client attempting to book consultation with their own ID when passed as lawyer_id
    res_self = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": _client_id,
            "scheduled_at": datetime.now(UTC).replace(year=2030, month=6, day=15, hour=10, minute=0, second=0).isoformat(),
            "duration_minutes": 30,
        },
        headers=h_client,
    )
    assert res_self.status_code == 404  # Client is not a lawyer profile

    # 2. Outside business hours rejection (02:00 UTC = 07:30 IST, which is before 08:00 IST)
    early_slot = datetime.now(UTC).replace(year=2030, month=6, day=15, hour=2, minute=0, second=0).isoformat()
    res_early = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "scheduled_at": early_slot,
            "duration_minutes": 30,
        },
        headers=h_client,
    )
    assert res_early.status_code == 422
    assert "business hours" in res_early.json()["error"]["message"]

    # 3. Late night outside business hours (17:00 UTC = 22:30 IST, which is after 21:00 IST)
    late_slot = datetime.now(UTC).replace(year=2030, month=6, day=15, hour=17, minute=0, second=0).isoformat()
    res_late = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "scheduled_at": late_slot,
            "duration_minutes": 30,
        },
        headers=h_client,
    )
    assert res_late.status_code == 422
    assert "business hours" in res_late.json()["error"]["message"]


def test_consultation_slot_overlap_comprehensive_matrix(client: TestClient, db: Session):
    _c1_id, h_c1 = _setup_user(client, "client1_ov@test.com", "Pass123!", "CLIENT")
    _c2_id, h_c2 = _setup_user(client, "client2_ov@test.com", "Pass123!", "CLIENT")
    lawyer_id, _h_l = _setup_user(client, "lawyer_ov@test.com", "Pass123!", "LAWYER")

    from uuid import UUID

    from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus

    lp = db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    assert lp is not None
    db.add(
        LawyerVerification(
            lawyer_profile_id=lp.id,
            enrollment_number="OV/777/2021",
            state_bar_council="Maharashtra",
            status=VerificationStatus.APPROVED,
        )
    )
    db.commit()

    # Base booked consultation: 10:00 UTC to 11:00 UTC (15:30 to 16:30 IST)
    base_time = datetime.now(UTC).replace(year=2030, month=5, day=20, hour=10, minute=0, second=0, microsecond=0)
    res_base = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "scheduled_at": base_time.isoformat(),
            "duration_minutes": 60,
        },
        headers=h_c1,
    )
    assert res_base.status_code == 201

    # 1. Exact same start and end: 10:00 - 11:00 (Client 2) -> 422 Overlap
    res_exact = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "scheduled_at": base_time.isoformat(),
            "duration_minutes": 60,
        },
        headers=h_c2,
    )
    assert res_exact.status_code == 422
    assert "overlaps" in res_exact.json()["error"]["message"]

    # 2. Partial overlap at beginning: 09:30 - 10:30 -> 422 Overlap
    res_start_ov = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "scheduled_at": (base_time.replace(minute=30) - datetime.resolution).replace(hour=9, minute=30).isoformat(),
            "duration_minutes": 60,
        },
        headers=h_c2,
    )
    assert res_start_ov.status_code == 422
    assert "overlaps" in res_start_ov.json()["error"]["message"]

    # 3. Partial overlap at end: 10:30 - 11:30 -> 422 Overlap
    res_end_ov = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "scheduled_at": base_time.replace(minute=30).isoformat(),
            "duration_minutes": 60,
        },
        headers=h_c2,
    )
    assert res_end_ov.status_code == 422
    assert "overlaps" in res_end_ov.json()["error"]["message"]

    # 4. Enclosing interval: 09:30 - 11:30 -> 422 Overlap
    res_enclosing = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "scheduled_at": base_time.replace(hour=9, minute=30).isoformat(),
            "duration_minutes": 120,
        },
        headers=h_c2,
    )
    assert res_enclosing.status_code == 422
    assert "overlaps" in res_enclosing.json()["error"]["message"]

    # 5. Inside interval: 10:15 - 10:45 -> 422 Overlap
    res_inside = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "scheduled_at": base_time.replace(hour=10, minute=15).isoformat(),
            "duration_minutes": 30,
        },
        headers=h_c2,
    )
    assert res_inside.status_code == 422
    assert "overlaps" in res_inside.json()["error"]["message"]

    # 6. Adjacent non-overlapping slot BEFORE: 09:00 - 10:00 -> 201 Success
    res_adj_before = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "scheduled_at": base_time.replace(hour=9, minute=0).isoformat(),
            "duration_minutes": 60,
        },
        headers=h_c2,
    )
    assert res_adj_before.status_code == 201

    # 7. Adjacent non-overlapping slot AFTER: 11:00 - 12:00 -> 201 Success
    res_adj_after = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "scheduled_at": base_time.replace(hour=11, minute=0).isoformat(),
            "duration_minutes": 60,
        },
        headers=h_c2,
    )
    assert res_adj_after.status_code == 201


def test_consultation_booking_without_scheduled_time(client: TestClient, db: Session):
    """Verify that clients can book a consultation without specifying a time."""
    import uuid
    from uuid import UUID
    from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus
    from app.core.identifiers import generate_uuid7

    client_id, h_client = _setup_user(
        client, f"client_flex_{uuid.uuid4().hex[:6]}@example.com", "Pass123!", "CLIENT"
    )
    lawyer_id, h_lawyer = _setup_user(
        client, f"lawyer_flex_{uuid.uuid4().hex[:6]}@example.com", "Pass123!", "LAWYER"
    )

    l_prof = db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    assert l_prof is not None
    l_prof.consultation_fee = 0
    ver = LawyerVerification(
        id=generate_uuid7(),
        lawyer_profile_id=l_prof.id,
        enrollment_number=f"FLEX/{uuid.uuid4().hex[:4]}/2026",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()
    db.refresh(l_prof)

    # Book consultation with scheduled_at completely omitted
    res = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": str(l_prof.id),
            "duration_minutes": 30,
        },
        headers=h_client,
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["status"] == "REQUESTED"
    assert data["scheduled_at"] is not None

