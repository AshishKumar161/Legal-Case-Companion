import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.payment import Payment, PaymentStatus
from app.models.user import (
    LawyerProfile,
    LawyerVerification,
    VerificationStatus,
)


def _make_stripe_sig(
    payload: dict, secret: str = "whsec_test_secret_123", timestamp: int | None = None
) -> tuple[str, bytes]:
    raw_body = json.dumps(payload).encode("utf-8")
    if timestamp is None:
        timestamp = int(datetime.now(UTC).timestamp())
    signed_payload = f"{timestamp}.".encode() + raw_body
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}", raw_body


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


# ============================================================================
# 1. PAYMENT CREATION & AMOUNT INTEGRITY
# ============================================================================


def test_payment_creation_and_amount_integrity(client: TestClient, db: Session):
    _client_a_id, h_client_a = _setup_user(client, "pay_v4_ca@test.com", role="CLIENT")
    _client_b_id, h_client_b = _setup_user(client, "pay_v4_cb@test.com", role="CLIENT")
    lawyer_id, _h_lawyer = _setup_user(client, "pay_v4_l@test.com", role="LAWYER")

    # Configure and verify lawyer
    lp = (
        db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    )
    assert lp is not None
    lp.consultation_fee = 4500.0
    ver = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number="PAY/101/2022",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Pay V4 Case", "description": "Desc"},
        headers=h_client_a,
    )
    case_id = res_case.json()["id"]

    # Request consultation for Client A
    fut = (datetime.now(UTC) + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_req = client.post(
        f"/api/v1/cases/{case_id}/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut, "duration_minutes": 45},
        headers=h_client_a,
    )
    c_id = res_req.json()["id"]

    # 1. Client A creates payment intent -> server calculates amount ₹4500
    res_pay = client.post(f"/api/v1/consultations/{c_id}/payments", headers=h_client_a)
    assert res_pay.status_code == 201
    p_data = res_pay.json()
    assert p_data["amount"] == 4500.0
    assert p_data["currency"] == "INR"
    assert "payment_id" in p_data

    # 2. Client B cannot create payment for Client A's consultation -> 404 / 403
    res_b_pay = client.post(
        f"/api/v1/consultations/{c_id}/payments", headers=h_client_b
    )
    assert res_b_pay.status_code in (403, 404)

    # 3. Unauthenticated request -> 401
    assert client.post(f"/api/v1/consultations/{c_id}/payments").status_code == 401

    # 4. Zero fee consultation payment attempt -> 422
    lp.consultation_fee = 0.0
    db.commit()
    res_zero_req = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "scheduled_at": (datetime.now(UTC) + timedelta(days=4)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
            "duration_minutes": 30,
        },
        headers=h_client_a,
    )
    c_zero_id = res_zero_req.json()["id"]
    res_zero_pay = client.post(
        f"/api/v1/consultations/{c_zero_id}/payments", headers=h_client_a
    )
    assert res_zero_pay.status_code == 422
    assert "zero" in res_zero_pay.json()["error"]["message"]


# ============================================================================
# 2. PAYMENT CREATION IDEMPOTENCY (ACTIVE INTENT REUSE)
# ============================================================================


def test_payment_creation_idempotency(client: TestClient, db: Session):
    _client_id, h_client = _setup_user(client, "idem_client@test.com", role="CLIENT")
    lawyer_id, _h_lawyer = _setup_user(client, "idem_lawyer@test.com", role="LAWYER")

    lp = (
        db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    )
    assert lp is not None
    lp.consultation_fee = 2000.0
    ver = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number="IDEM/202/2021",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()

    fut = (datetime.now(UTC) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_req = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut, "duration_minutes": 30},
        headers=h_client,
    )
    c_id = res_req.json()["id"]

    # Request 1: Create payment
    res_1 = client.post(f"/api/v1/consultations/{c_id}/payments", headers=h_client)
    assert res_1.status_code == 201
    p1 = res_1.json()

    # Request 2: Retry creation for same consultation
    res_2 = client.post(f"/api/v1/consultations/{c_id}/payments", headers=h_client)
    assert res_2.status_code == 201
    p2 = res_2.json()

    # Verify same payment ID and client secret returned (no duplicate payment records)
    assert p1["payment_id"] == p2["payment_id"]
    assert p1["client_secret"] == p2["client_secret"]

    # Database count check: only 1 payment in DB for this consultation
    count = db.query(Payment).filter(Payment.consultation_id == UUID(c_id)).count()
    assert count == 1


# ============================================================================
# 3. WEBHOOK SECURITY, SIGNATURE VALIDATION & FAILED EVENT
# ============================================================================


def test_webhook_security_and_failure_flow(client: TestClient, db: Session):
    _client_id, h_client = _setup_user(client, "wh_sec_client@test.com", role="CLIENT")
    lawyer_id, _h_lawyer = _setup_user(client, "wh_sec_lawyer@test.com", role="LAWYER")

    lp = (
        db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    )
    assert lp is not None
    lp.consultation_fee = 1500.0
    ver = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number="WH/303/2020",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()

    fut = (datetime.now(UTC) + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_req = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut, "duration_minutes": 30},
        headers=h_client,
    )
    c_id = res_req.json()["id"]

    res_pay = client.post(f"/api/v1/consultations/{c_id}/payments", headers=h_client)
    payment_id = res_pay.json()["payment_id"]

    payload = {
        "id": "evt_fail_999",
        "type": "payment_intent.payment_failed",
        "data": {"object": {"id": f"pi_mock_{payment_id}"}},
    }

    # 1. Missing signature -> 401
    res_no_sig = client.post("/api/v1/webhooks/stripe", json=payload)
    assert res_no_sig.status_code == 401

    # 2. Invalid signature header format -> 401
    res_bad_sig = client.post(
        "/api/v1/webhooks/stripe",
        json=payload,
        headers={"Stripe-Signature": "invalid_format_without_t_timestamp"},
    )
    assert res_bad_sig.status_code == 401

    # 3. Valid signature header -> 200, records failure
    sig_fail, raw_body_fail = _make_stripe_sig(payload)
    res_fail = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": sig_fail, "Content-Type": "application/json"},
        content=raw_body_fail,
    )
    assert res_fail.status_code == 200
    assert res_fail.json()["status"] == "failed_recorded"

    # Verify payment status in DB is FAILED
    p_record = db.query(Payment).filter(Payment.id == UUID(payment_id)).first()
    assert p_record is not None
    assert p_record.status == PaymentStatus.FAILED

    # 4. Unhandled webhook event type -> ignored safely
    ignored_payload = {"id": "evt_other_1", "type": "customer.created", "data": {}}
    sig_ign, raw_body_ign = _make_stripe_sig(ignored_payload)
    res_ignored = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": sig_ign, "Content-Type": "application/json"},
        content=raw_body_ign,
    )
    assert res_ignored.status_code == 200
    assert res_ignored.json()["status"] == "ignored"


# ============================================================================
# 4. FULL PAYMENT SUCCESS & CONSULTATION SYNCHRONIZATION
# ============================================================================


def test_payment_success_and_consultation_sync(client: TestClient, db: Session):
    _client_id, h_client = _setup_user(client, "sync_client@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(client, "sync_lawyer@test.com", role="LAWYER")

    lp = (
        db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    )
    assert lp is not None
    lp.consultation_fee = 6000.0
    ver = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number="SYNC/404/2019",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()

    # Case creation
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Sync Case", "description": "D"},
        headers=h_client,
    )
    case_id = res_case.json()["id"]

    # Request consultation
    fut = (datetime.now(UTC) + timedelta(days=5)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_req = client.post(
        f"/api/v1/cases/{case_id}/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut, "duration_minutes": 60},
        headers=h_client,
    )
    c_id = res_req.json()["id"]

    # Lawyer accepts consultation -> ACCEPTED
    res_acc = client.post(f"/api/v1/consultations/{c_id}/accept", headers=h_lawyer)
    assert res_acc.status_code == 200
    assert res_acc.json()["status"] == "ACCEPTED"

    # Client creates payment
    res_pay = client.post(f"/api/v1/consultations/{c_id}/payments", headers=h_client)
    payment_id = res_pay.json()["payment_id"]

    # Webhook payment success
    payload = {
        "id": "evt_success_888",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": f"pi_mock_{payment_id}"}},
    }
    wh_sig, wh_raw = _make_stripe_sig(payload)
    res_wh = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": wh_sig, "Content-Type": "application/json"},
        content=wh_raw,
    )
    assert res_wh.status_code == 200
    assert res_wh.json()["status"] == "success"

    # Duplicate webhook delivers idempotency
    res_wh_dup = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": wh_sig, "Content-Type": "application/json"},
        content=wh_raw,
    )
    assert res_wh_dup.status_code == 200
    assert res_wh_dup.json()["status"] == "already_processed"

    # Consultation transitioned to PAID
    res_c = client.get(f"/api/v1/consultations/{c_id}", headers=h_client)
    assert res_c.status_code == 200
    assert res_c.json()["status"] == "PAID"

    # Lawyer can now confirm/schedule
    res_conf = client.post(f"/api/v1/consultations/{c_id}/confirm", headers=h_lawyer)
    assert res_conf.status_code == 200
    assert res_conf.json()["status"] == "SCHEDULED"


# ============================================================================
# 5. PAYMENT ACCESS CONTROL & BOLA/IDOR MATRIX
# ============================================================================


def test_payment_access_control_and_query_endpoints(client: TestClient, db: Session):
    _client_a_id, h_client_a = _setup_user(
        client, "pay_bola_ca@test.com", role="CLIENT"
    )
    _client_b_id, h_client_b = _setup_user(
        client, "pay_bola_cb@test.com", role="CLIENT"
    )
    lawyer_a_id, h_lawyer_a = _setup_user(client, "pay_bola_la@test.com", role="LAWYER")
    _lawyer_b_id, h_lawyer_b = _setup_user(
        client, "pay_bola_lb@test.com", role="LAWYER"
    )

    lp_a = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == UUID(lawyer_a_id))
        .first()
    )
    assert lp_a is not None
    lp_a.consultation_fee = 3000.0
    ver = LawyerVerification(
        lawyer_profile_id=lp_a.id,
        enrollment_number="BOLA/505/2021",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()

    fut = (datetime.now(UTC) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_req = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": lawyer_a_id, "scheduled_at": fut, "duration_minutes": 30},
        headers=h_client_a,
    )
    c_id = res_req.json()["id"]

    res_pay = client.post(f"/api/v1/consultations/{c_id}/payments", headers=h_client_a)
    payment_id = res_pay.json()["payment_id"]

    # 1. Payer Client A -> Payment: ALLOW (200)
    assert (
        client.get(f"/api/v1/payments/{payment_id}", headers=h_client_a).status_code
        == 200
    )

    # 2. Unrelated Client B -> Payment: DENY (404)
    assert (
        client.get(f"/api/v1/payments/{payment_id}", headers=h_client_b).status_code
        == 404
    )

    # 3. Assigned Lawyer A -> Payment: ALLOW (200)
    assert (
        client.get(f"/api/v1/payments/{payment_id}", headers=h_lawyer_a).status_code
        == 200
    )

    # 4. Unassigned Lawyer B -> Payment: DENY (404)
    assert (
        client.get(f"/api/v1/payments/{payment_id}", headers=h_lawyer_b).status_code
        == 404
    )

    # 5. List Consultation Payments endpoint
    res_list_a = client.get(
        f"/api/v1/consultations/{c_id}/payments", headers=h_client_a
    )
    assert res_list_a.status_code == 200
    assert len(res_list_a.json()) == 1
    assert res_list_a.json()[0]["id"] == payment_id

    # 6. Unrelated Client B querying Consultation Payments: DENY (404)
    assert (
        client.get(
            f"/api/v1/consultations/{c_id}/payments", headers=h_client_b
        ).status_code
        == 404
    )


# ============================================================================
# 6. FINANCIAL AUDIT TRAIL
# ============================================================================


def test_payment_audit_events_logged(client: TestClient, db: Session):
    _client_id, h_client = _setup_user(client, "audit_client@test.com", role="CLIENT")
    lawyer_id, _h_lawyer = _setup_user(client, "audit_lawyer@test.com", role="LAWYER")

    lp = (
        db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    )
    assert lp is not None
    lp.consultation_fee = 1200.0
    ver = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number="AUD/606/2020",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()

    fut = (datetime.now(UTC) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_req = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut, "duration_minutes": 30},
        headers=h_client,
    )
    c_id = res_req.json()["id"]

    # 1. Create Payment -> PAYMENT_CREATED
    res_pay = client.post(f"/api/v1/consultations/{c_id}/payments", headers=h_client)
    payment_id = res_pay.json()["payment_id"]

    ev_created = (
        db.query(AuditEvent)
        .filter(AuditEvent.event_type == "PAYMENT_CREATED")
        .order_by(AuditEvent.timestamp.desc())
        .first()
    )
    assert ev_created is not None
    assert ev_created.metadata_["payment_id"] == payment_id
    assert ev_created.metadata_["amount"] == 1200.0

    # 2. Webhook Success -> WEBHOOK_RECEIVED, PAYMENT_SUCCEEDED, WEBHOOK_PROCESSED
    payload = {
        "id": "evt_aud_1",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": f"pi_mock_{payment_id}"}},
    }
    sig_aud, raw_aud = _make_stripe_sig(payload)
    client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": sig_aud, "Content-Type": "application/json"},
        content=raw_aud,
    )

    ev_succeeded = (
        db.query(AuditEvent)
        .filter(AuditEvent.event_type == "PAYMENT_SUCCEEDED")
        .order_by(AuditEvent.timestamp.desc())
        .first()
    )
    assert ev_succeeded is not None
    assert ev_succeeded.metadata_["payment_id"] == payment_id


def test_missing_webhook_secret_raises_500_without_static_fallback(client: TestClient, monkeypatch):
    """
    Verify that if STRIPE_WEBHOOK_SECRET is unconfigured (None or empty),
    the webhook handler raises an explicit HTTP 500 configuration error
    and NEVER silently falls back to a static credential (e.g. whsec_test_secret_123).
    """
    from app.core.config import settings
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    payload = {
        "id": "evt_no_sec_test",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_mock_no_secret"}},
    }
    raw_payload = json.dumps(payload).encode("utf-8")
    t = int(datetime.now(UTC).timestamp())
    sig = f"t={t},v1=mock_signature"

    res = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": sig, "Content-Type": "application/json"},
        content=raw_payload,
    )
    assert res.status_code == 500
    assert "STRIPE_WEBHOOK_SECRET not configured" in res.text

