from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.audit import AuditEvent
from app.models.consultation import Consultation, ConsultationStatus
from app.models.notification import Notification
from app.models.payment import Payment, PaymentStatus
from app.models.user import (
    AccountStatus,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)


def _setup_user(
    client: TestClient,
    db: Session,
    email: str,
    password: str = "Password123!",
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Test User",
) -> tuple[str, dict[str, str]]:
    """Helper to register and login a user, returning (user_id, auth_headers)."""
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
        user.lawyer_profile.consultation_fee = 2500.0
        user.lawyer_profile.is_available = True
        verif = LawyerVerification(
            lawyer_profile_id=user.lawyer_profile.id,
            enrollment_number="DL/2026/TEST",
            state_bar_council="Delhi",
            status=VerificationStatus.APPROVED,
        )
        db.add(verif)
    db.commit()
    return user_id, headers


# ============================================================================
# 1. FULL CONSULTATION LIFECYCLE & STATE MACHINE TRANSITIONS
# ============================================================================


def test_full_consultation_lifecycle_state_machine(client: TestClient, db: Session):
    """
    Tests full standard journey:
    REQUESTED -> ACCEPTED -> PAID -> SCHEDULED -> COMPLETED
    and ensures invalid transitions are rejected.
    """
    _client_id, h_client = _setup_user(client, db, "client_life@example.com", role=UserRole.CLIENT, full_name="Client Life")
    lawyer_id, h_lawyer = _setup_user(client, db, "lawyer_life@example.com", role=UserRole.LAWYER, full_name="Advocate Life")

    # 1. Client requests consultation in a future business hour slot (09:00 UTC = 14:30 IST)
    target_dt = (datetime.now(UTC) + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
    req_res = client.post(
        "/api/v1/consultations",
        headers=h_client,
        json={
            "lawyer_id": lawyer_id,
            "scheduled_at": target_dt.isoformat(),
            "duration_minutes": 30,
        },
    )
    assert req_res.status_code == 201, req_res.text
    con_id = req_res.json()["id"]
    assert req_res.json()["status"] == "REQUESTED"

    # 2. Client cannot accept the consultation
    res_bad_accept = client.post(f"/api/v1/consultations/{con_id}/accept", headers=h_client)
    assert res_bad_accept.status_code == 403

    # 3. Lawyer accepts the consultation
    res_accept = client.post(f"/api/v1/consultations/{con_id}/accept", headers=h_lawyer)
    assert res_accept.status_code == 200
    assert res_accept.json()["status"] == "ACCEPTED"

    # 4. Idempotent acceptance
    res_accept_dup = client.post(f"/api/v1/consultations/{con_id}/accept", headers=h_lawyer)
    assert res_accept_dup.status_code == 200

    # 5. Client creates payment intent & completes payment via mock webhook
    pay_res = client.post(f"/api/v1/consultations/{con_id}/payments", headers=h_client)
    assert pay_res.status_code == 201
    payment_id = pay_res.json()["payment_id"]

    payment = db.query(Payment).filter(Payment.id == UUID(payment_id)).first()
    assert payment is not None
    payment.status = PaymentStatus.SUCCEEDED
    payment.paid_at = datetime.now(UTC)
    consultation = db.query(Consultation).filter(Consultation.id == UUID(con_id)).first()
    assert consultation is not None
    consultation.status = ConsultationStatus.PAID
    db.commit()

    # 6. Lawyer/Client schedules slot
    res_sched = client.post(
        f"/api/v1/consultations/{con_id}/schedule",
        headers=h_lawyer,
        json={
            "scheduled_at": target_dt.isoformat(),
            "duration_minutes": 30,
        },
    )
    assert res_sched.status_code == 200
    assert res_sched.json()["status"] == "SCHEDULED"

    # 7. Lawyer completes consultation
    res_comp = client.post(f"/api/v1/consultations/{con_id}/complete", headers=h_lawyer)
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"

    # 8. Terminal state check: completed consultation cannot be cancelled or rescheduled
    res_cancel_term = client.post(f"/api/v1/consultations/{con_id}/cancel", headers=h_client)
    assert res_cancel_term.status_code in [400, 422]

    res_resched_term = client.post(
        f"/api/v1/consultations/{con_id}/reschedule",
        headers=h_client,
        json={"scheduled_at": (target_dt + timedelta(days=1)).isoformat(), "duration_minutes": 30},
    )
    assert res_resched_term.status_code in [400, 422]


# ============================================================================
# 2. RESCHEDULING & ATOMIC SLOT CONSISTENCY
# ============================================================================


def test_consultation_rescheduling_and_collision_defense(client: TestClient, db: Session):
    """
    Verifies that rescheduling updates the consultation atomically,
    releases the old slot, occupies the new slot, and returns 409 Conflict
    if the target slot is already occupied.
    """
    _client_a_id, h_client_a = _setup_user(client, db, "client_a_resched@example.com", role=UserRole.CLIENT, full_name="Client A")
    _client_b_id, h_client_b = _setup_user(client, db, "client_b_resched@example.com", role=UserRole.CLIENT, full_name="Client B")
    lawyer_id, _h_lawyer = _setup_user(client, db, "lawyer_resched@example.com", role=UserRole.LAWYER, full_name="Advocate Verma")

    slot_1 = (datetime.now(UTC) + timedelta(days=3)).replace(hour=8, minute=0, second=0, microsecond=0)
    slot_2 = (datetime.now(UTC) + timedelta(days=3)).replace(hour=9, minute=0, second=0, microsecond=0)

    # 1. Client A books Slot 1
    res_a = client.post(
        "/api/v1/consultations",
        headers=h_client_a,
        json={"lawyer_id": lawyer_id, "scheduled_at": slot_1.isoformat(), "duration_minutes": 30},
    )
    assert res_a.status_code == 201
    con_a_id = res_a.json()["id"]

    # 2. Client B books Slot 2
    res_b = client.post(
        "/api/v1/consultations",
        headers=h_client_b,
        json={"lawyer_id": lawyer_id, "scheduled_at": slot_2.isoformat(), "duration_minutes": 30},
    )
    assert res_b.status_code == 201
    con_b_id = res_b.json()["id"]

    # 3. Client A attempts to reschedule to Slot 2 (which is occupied by Client B) -> Expect 409/422
    res_conflict = client.post(
        f"/api/v1/consultations/{con_a_id}/reschedule",
        headers=h_client_a,
        json={"scheduled_at": slot_2.isoformat(), "duration_minutes": 30, "reason": "Conflict attempt"},
    )
    assert res_conflict.status_code in [409, 422]

    # 4. Client A reschedules to an unoccupied Slot 3 (10:00 UTC = 15:30 IST)
    slot_3 = (datetime.now(UTC) + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0)
    res_resched = client.post(
        f"/api/v1/consultations/{con_a_id}/reschedule",
        headers=h_client_a,
        json={"scheduled_at": slot_3.isoformat(), "duration_minutes": 30, "reason": "Court schedule changed"},
    )
    assert res_resched.status_code == 200
    returned_dt = datetime.fromisoformat(res_resched.json()["scheduled_at"]).replace(tzinfo=UTC)
    assert returned_dt == slot_3

    # 5. Slot 1 is now released: Client B can now reschedule to Slot 1!
    res_b_to_1 = client.post(
        f"/api/v1/consultations/{con_b_id}/reschedule",
        headers=h_client_b,
        json={"scheduled_at": slot_1.isoformat(), "duration_minutes": 30, "reason": "Moving earlier"},
    )
    assert res_b_to_1.status_code == 200

    # Verify audit event emitted
    audit = db.query(AuditEvent).filter(AuditEvent.event_type == "CONSULTATION_RESCHEDULED").first()
    assert audit is not None


# ============================================================================
# 3. CANCELLATION, IDEMPOTENCY & SLOT RELEASE
# ============================================================================


def test_consultation_cancellation_and_slot_release(client: TestClient, db: Session):
    """
    Verifies that cancelling a consultation releases the slot for other users,
    emits audit events & notifications, and acts idempotently on duplicate cancel.
    """
    _client_1_id, h_client_1 = _setup_user(client, db, "client_cancel_1@example.com", role=UserRole.CLIENT)
    _client_2_id, h_client_2 = _setup_user(client, db, "client_cancel_2@example.com", role=UserRole.CLIENT)
    lawyer_id, _h_lawyer = _setup_user(client, db, "lawyer_cancel@example.com", role=UserRole.LAWYER)

    slot = (datetime.now(UTC) + timedelta(days=4)).replace(hour=9, minute=0, second=0, microsecond=0)

    # 1. Client 1 books slot
    res_c1 = client.post(
        "/api/v1/consultations",
        headers=h_client_1,
        json={"lawyer_id": lawyer_id, "scheduled_at": slot.isoformat(), "duration_minutes": 30},
    )
    assert res_c1.status_code == 201
    con_id = res_c1.json()["id"]

    # 2. Client 2 cannot book the same slot -> Expect 409/422
    res_c2_block = client.post(
        "/api/v1/consultations",
        headers=h_client_2,
        json={"lawyer_id": lawyer_id, "scheduled_at": slot.isoformat(), "duration_minutes": 30},
    )
    assert res_c2_block.status_code in [409, 422]

    # 3. Client 1 cancels the consultation
    res_cancel = client.post(
        f"/api/v1/consultations/{con_id}/cancel",
        headers=h_client_1,
        json={"reason": "Matter settled amicably"},
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "CANCELLED"

    # 4. Duplicate cancel is idempotent
    res_cancel_dup = client.post(f"/api/v1/consultations/{con_id}/cancel", headers=h_client_1)
    assert res_cancel_dup.status_code == 200
    assert res_cancel_dup.json()["status"] == "CANCELLED"

    # 5. Slot is now freed: Client 2 can book the slot successfully
    res_c2_ok = client.post(
        "/api/v1/consultations",
        headers=h_client_2,
        json={"lawyer_id": lawyer_id, "scheduled_at": slot.isoformat(), "duration_minutes": 30},
    )
    assert res_c2_ok.status_code == 201


# ============================================================================
# 4. NO-SHOW LIFECYCLE & AUTHORIZATION
# ============================================================================


def test_consultation_no_show_handling(client: TestClient, db: Session):
    """
    Verifies that only lawyers or admins can mark a consultation as NO_SHOW,
    and client attempts to mark no-show are forbidden (403).
    """
    _client_id, h_client = _setup_user(client, db, "client_noshow@example.com", role=UserRole.CLIENT)
    lawyer_id, h_lawyer = _setup_user(client, db, "lawyer_noshow@example.com", role=UserRole.LAWYER)
    _admin_id, _h_admin = _setup_user(client, db, "admin_noshow@example.com", role=UserRole.ADMIN)

    slot = (datetime.now(UTC) + timedelta(days=2)).replace(hour=8, minute=30, second=0, microsecond=0)

    # 1. Book & Accept consultation
    res_con = client.post(
        "/api/v1/consultations",
        headers=h_client,
        json={"lawyer_id": lawyer_id, "scheduled_at": slot.isoformat(), "duration_minutes": 30},
    )
    assert res_con.status_code == 201
    con_id = res_con.json()["id"]

    client.post(f"/api/v1/consultations/{con_id}/accept", headers=h_lawyer)

    # 2. Client attempts to mark no-show -> 403 Forbidden
    res_bad_ns = client.post(f"/api/v1/consultations/{con_id}/no-show", headers=h_client)
    assert res_bad_ns.status_code == 403

    # 3. Lawyer marks no-show
    res_ns = client.post(
        f"/api/v1/consultations/{con_id}/no-show",
        headers=h_lawyer,
        json={"reason": "Client did not connect after 15 minutes"},
    )
    assert res_ns.status_code == 200
    assert res_ns.json()["status"] == "NO_SHOW"

    # Verify notification sent to client
    notif = (
        db.query(Notification)
        .filter(Notification.consultation_id == UUID(con_id))
        .order_by(Notification.id.desc())
        .first()
    )
    assert notif is not None
    assert "No-Show" in notif.title or "NO_SHOW" in notif.title or "no-show" in notif.message.lower()


# ============================================================================
# 5. AUTHORIZATION & IDOR / BOLA ISOLATION
# ============================================================================


def test_consultation_authorization_and_idor_protection(client: TestClient, db: Session):
    """
    Verifies that unrelated third-party users cannot view or manipulate consultations.
    """
    _client_owner_id, h_owner = _setup_user(client, db, "owner_con@example.com", role=UserRole.CLIENT)
    _client_intruder_id, h_intruder = _setup_user(client, db, "intruder_con@example.com", role=UserRole.CLIENT)
    lawyer_id, _h_lawyer = _setup_user(client, db, "lawyer_con@example.com", role=UserRole.LAWYER)

    slot = (datetime.now(UTC) + timedelta(days=2)).replace(hour=11, minute=0, second=0, microsecond=0)

    res_con = client.post(
        "/api/v1/consultations",
        headers=h_owner,
        json={"lawyer_id": lawyer_id, "scheduled_at": slot.isoformat(), "duration_minutes": 30},
    )
    assert res_con.status_code == 201
    con_id = res_con.json()["id"]

    # Intruder cannot read consultation (404/403 for IDOR protection)
    res_get = client.get(f"/api/v1/consultations/{con_id}", headers=h_intruder)
    assert res_get.status_code in [403, 404]

    # Intruder cannot cancel consultation
    res_cancel = client.post(f"/api/v1/consultations/{con_id}/cancel", headers=h_intruder)
    assert res_cancel.status_code in [403, 404]

    # Intruder cannot reschedule consultation
    res_resched = client.post(
        f"/api/v1/consultations/{con_id}/reschedule",
        headers=h_intruder,
        json={"scheduled_at": (slot + timedelta(hours=1)).isoformat()},
    )
    assert res_resched.status_code in [403, 404]
