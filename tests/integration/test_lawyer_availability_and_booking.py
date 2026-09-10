from datetime import UTC, date, datetime
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.consultation import Consultation
from app.models.user import (
    LawyerProfile,
    LawyerVerification,
    VerificationStatus,
)


def _setup_user(
    client: TestClient,
    email: str,
    password: str = "Pass123!",
    role: str = "CLIENT",
    full_name: str = "Test User",
) -> tuple[str, dict[str, str]]:
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
    return str(user_id), {"Authorization": f"Bearer {token}"}


def _verify_lawyer(db: Session, lawyer_user_id: str):
    lp = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == UUID(lawyer_user_id))
        .first()
    )
    assert lp is not None
    lp.consultation_fee = 1500.0
    ver = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number="KAR/999/2020",
        state_bar_council="Karnataka",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()
    db.refresh(lp)
    return lp


def test_lawyer_availability_crud_and_rbac(client: TestClient, db: Session):
    lawyer_id, h_lawyer = _setup_user(client, "av_lawyer1@test.com", role="LAWYER")
    _client_id, h_client = _setup_user(client, "av_client1@test.com", role="CLIENT")
    _verify_lawyer(db, lawyer_id)

    # 1. Non-lawyer cannot access lawyer availability configuration -> 403
    res_unauth = client.get("/api/v1/profiles/lawyer/availability", headers=h_client)
    assert res_unauth.status_code == 403

    res_unauth_create = client.post(
        "/api/v1/profiles/lawyer/availability",
        json={
            "day_of_week": 0,
            "start_time": "09:00:00",
            "end_time": "12:00:00",
            "slot_duration_minutes": 30,
        },
        headers=h_client,
    )
    assert res_unauth_create.status_code == 403

    # 2. Invalid time range (end <= start) -> 422
    res_inv = client.post(
        "/api/v1/profiles/lawyer/availability",
        json={
            "day_of_week": 0,
            "start_time": "14:00:00",
            "end_time": "10:00:00",
            "slot_duration_minutes": 30,
        },
        headers=h_lawyer,
    )
    assert res_inv.status_code == 422

    # 3. Create valid availability windows (e.g. Monday morning 09:00-12:00)
    res_create1 = client.post(
        "/api/v1/profiles/lawyer/availability",
        json={
            "day_of_week": 0,
            "start_time": "09:00:00",
            "end_time": "12:00:00",
            "slot_duration_minutes": 30,
            "is_active": True,
        },
        headers=h_lawyer,
    )
    assert res_create1.status_code == 201
    av1_id = res_create1.json()["id"]
    assert res_create1.json()["day_of_week"] == 0

    # 4. Overlapping window on the same day -> 422
    res_overlap = client.post(
        "/api/v1/profiles/lawyer/availability",
        json={
            "day_of_week": 0,
            "start_time": "11:00:00",
            "end_time": "14:00:00",
            "slot_duration_minutes": 30,
        },
        headers=h_lawyer,
    )
    assert res_overlap.status_code == 422
    assert "overlaps" in res_overlap.json()["error"]["message"]

    # 5. Non-overlapping afternoon window on the same day -> 201
    res_create2 = client.post(
        "/api/v1/profiles/lawyer/availability",
        json={
            "day_of_week": 0,
            "start_time": "14:00:00",
            "end_time": "17:00:00",
            "slot_duration_minutes": 30,
        },
        headers=h_lawyer,
    )
    assert res_create2.status_code == 201
    av2_id = res_create2.json()["id"]

    # 6. Read back availability list
    res_list = client.get("/api/v1/profiles/lawyer/availability", headers=h_lawyer)
    assert res_list.status_code == 200
    ids = [item["id"] for item in res_list.json()]
    assert av1_id in ids
    assert av2_id in ids

    # 7. Update window
    res_patch = client.patch(
        f"/api/v1/profiles/lawyer/availability/{av2_id}",
        json={"start_time": "14:30:00", "end_time": "17:30:00"},
        headers=h_lawyer,
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["start_time"] == "14:30:00"

    # 8. Delete window
    res_del = client.delete(
        f"/api/v1/profiles/lawyer/availability/{av2_id}", headers=h_lawyer
    )
    assert res_del.status_code == 204


def test_public_slots_generation_and_consultation_booking(
    client: TestClient, db: Session
):
    lawyer_id, h_lawyer = _setup_user(client, "slots_lawyer@test.com", role="LAWYER")
    _client_id, h_client = _setup_user(client, "slots_client@test.com", role="CLIENT")
    _verify_lawyer(db, lawyer_id)

    # Configure Monday availability: 10:00 to 12:00 IST (slot_duration = 30 min)
    # 10:00 - 10:30, 10:30 - 11:00, 11:00 - 11:30, 11:30 - 12:00 -> 4 slots
    res_av = client.post(
        "/api/v1/profiles/lawyer/availability",
        json={
            "day_of_week": 0,  # Monday
            "start_time": "10:00:00",
            "end_time": "12:00:00",
            "slot_duration_minutes": 30,
        },
        headers=h_lawyer,
    )
    assert res_av.status_code == 201

    # Pick a future Monday in 2030 (2030-06-10 is a Monday)
    target_monday = date(2030, 6, 10)
    assert target_monday.weekday() == 0

    # 1. Query available slots
    res_slots = client.get(
        f"/api/v1/lawyers/{lawyer_id}/slots?date={target_monday.isoformat()}&duration_minutes=30",
        headers=h_client,
    )
    assert res_slots.status_code == 200
    slots = res_slots.json()
    assert len(slots) == 4
    for slot in slots:
        assert slot["is_available"] is True
        assert slot["duration_minutes"] == 30

    # 2. Book the first slot: 10:00 IST (which is 04:30 UTC)
    slot_utc_str = slots[0]["start_time"]
    res_book = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "scheduled_at": slot_utc_str,
            "duration_minutes": 30,
        },
        headers=h_client,
    )
    assert res_book.status_code == 201
    c_id = res_book.json()["id"]

    # 3. Re-query slots: slot 0 should now be marked unavailable
    res_slots_after = client.get(
        f"/api/v1/lawyers/{lawyer_id}/slots?date={target_monday.isoformat()}&duration_minutes=30",
        headers=h_client,
    )
    slots_after = res_slots_after.json()
    assert slots_after[0]["is_available"] is False
    assert slots_after[1]["is_available"] is True

    # 4. Attempt booking a time OUTSIDE configured availability window (e.g. 15:00 IST on that Monday) -> 422
    outside_time = datetime(2030, 6, 10, 9, 30, 0, tzinfo=UTC).isoformat()  # 15:00 IST
    res_out = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "scheduled_at": outside_time,
            "duration_minutes": 30,
        },
        headers=h_client,
    )
    assert res_out.status_code == 422
    assert "outside of the lawyer's configured availability" in res_out.json()["error"]["message"]

    # 5. Cancel the consultation -> slot becomes available again
    res_cancel = client.post(f"/api/v1/consultations/{c_id}/cancel", headers=h_client)
    assert res_cancel.status_code == 200

    res_slots_reopened = client.get(
        f"/api/v1/lawyers/{lawyer_id}/slots?date={target_monday.isoformat()}&duration_minutes=30",
        headers=h_client,
    )
    assert res_slots_reopened.json()[0]["is_available"] is True


def test_consultation_booking_concurrency_race_condition(
    client: TestClient, db: Session
):
    """
    Test that competing concurrent requests attempting to book the exact same slot
    for the same lawyer cannot both succeed (one succeeds with 201, other fails with 422 conflict),
    and database IntegrityError is translated to a clean 422 error.
    """
    from unittest import mock

    from sqlalchemy.exc import IntegrityError

    lawyer_id, _h_lawyer = _setup_user(client, "conc_lawyer@test.com", role="LAWYER")
    _c1_id, h_c1 = _setup_user(client, "conc_c1@test.com", role="CLIENT")
    _c2_id, h_c2 = _setup_user(client, "conc_c2@test.com", role="CLIENT")
    _verify_lawyer(db, lawyer_id)

    target_slot = datetime(2030, 7, 15, 10, 0, 0, tzinfo=UTC).isoformat()
    payload = {
        "lawyer_id": lawyer_id,
        "scheduled_at": target_slot,
        "duration_minutes": 30,
    }

    # 1. First booking succeeds
    res1 = client.post("/api/v1/consultations", json=payload, headers=h_c1)
    assert res1.status_code == 201
    assert res1.json()["status"] == "REQUESTED"

    # 2. Second competing booking for same slot fails with 422 overlap
    res2 = client.post("/api/v1/consultations", json=payload, headers=h_c2)
    assert res2.status_code == 422
    assert "overlaps" in res2.json()["error"]["message"]

    # 3. Simulate database-level concurrent collision (e.g. PostgreSQL exclusion constraint violation)
    target_slot_future = datetime(2030, 7, 16, 10, 0, 0, tzinfo=UTC).isoformat()
    payload_future = {
        "lawyer_id": lawyer_id,
        "scheduled_at": target_slot_future,
        "duration_minutes": 30,
    }

    with mock.patch("sqlalchemy.orm.Session.commit") as mock_commit:
        mock_commit.side_effect = IntegrityError(
            "mock constraint violation", params={}, orig=Exception()
        )
        res_conflict = client.post(
            "/api/v1/consultations", json=payload_future, headers=h_c1
        )

    assert res_conflict.status_code == 422
    assert "overlaps" in res_conflict.json()["error"]["message"]

    # Verify that exactly ONE consultation was saved in the database
    consultations = (
        db.query(Consultation)
        .filter(
            Consultation.lawyer_id == UUID(res1.json()["lawyer_id"]),
            Consultation.deleted_at.is_(None),
        )
        .all()
    )
    assert len(consultations) == 1

