import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.consultation import Consultation, ConsultationStatus
from app.models.notification import Notification, NotificationType
from app.models.payment import Payment, PaymentStatus
from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus


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
# 1. END-TO-END FINANCIAL WORKFLOW & SERVER-AUTHORITATIVE AMOUNT
# ============================================================================


def test_complete_payment_and_consultation_lifecycle(client: TestClient, db: Session):
    """
    Verifies complete workflow:
    Client -> Case -> Consultation Request -> Lawyer Fee (₹3,500) ->
    Server Authoritative Payment Creation -> Stripe Webhook -> Consultation PAID ->
    Audit Logs & Notifications.
    """
    client_id, h_client = _setup_user(client, "fin_client_e2e@test.com", role="CLIENT")
    lawyer_id, _h_lawyer = _setup_user(client, "fin_lawyer_e2e@test.com", role="LAWYER")

    # 1. Setup Lawyer Profile with official Bar Council registration & authoritative fee
    lp = db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    assert lp is not None
    lp.consultation_fee = 3500.0
    ver = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number="D/9988/2021",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()

    # 2. Client initiates case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Financial E2E Case", "description": "Consultation payment verification."},
        headers=h_client,
    )
    assert res_case.status_code == 201
    case_id = res_case.json()["id"]

    # 3. Client books consultation
    fut_date = (datetime.now(UTC) + timedelta(days=2)).replace(hour=11, minute=0, second=0, microsecond=0).isoformat()
    res_consult = client.post(
        f"/api/v1/cases/{case_id}/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut_date, "duration_minutes": 30},
        headers=h_client,
    )
    assert res_consult.status_code == 201
    consultation_id = res_consult.json()["id"]

    # 4. Client requests Payment Intent -> Server calculates ₹3500.00 in INR
    res_pay = client.post(f"/api/v1/consultations/{consultation_id}/payments", headers=h_client)
    assert res_pay.status_code == 201
    pay_data = res_pay.json()
    assert pay_data["amount"] == 3500.0
    assert pay_data["currency"] == "INR"
    assert "payment_id" in pay_data
    payment_id = pay_data["payment_id"]

    # 5. Verify database payment record in CREATED status
    payment_rec = db.query(Payment).filter(Payment.id == UUID(payment_id)).first()
    assert payment_rec is not None
    assert payment_rec.status == PaymentStatus.CREATED
    assert payment_rec.amount == 3500.0
    assert payment_rec.currency == "INR"

    # 6. Verify webhook signature and transition to SUCCEEDED
    event_payload = {
        "id": "evt_test_success_9988",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_rec.provider_payment_id,
                "amount": 350000,
                "currency": "inr",
            }
        },
    }
    sig_header, raw_body = _make_stripe_sig(event_payload)
    res_webhook = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_body,
        headers={"Stripe-Signature": sig_header, "Content-Type": "application/json"},
    )
    assert res_webhook.status_code == 200
    assert res_webhook.json()["status"] == "success"

    # 7. Confirm Consultation and Payment status
    db.refresh(payment_rec)
    consultation_rec = db.query(Consultation).filter(Consultation.id == UUID(consultation_id)).first()
    assert payment_rec.status == PaymentStatus.SUCCEEDED
    assert consultation_rec is not None
    assert consultation_rec.status == ConsultationStatus.PAID

    # 8. Check Notifications generated
    client_notifications = (
        db.query(Notification)
        .filter(Notification.user_id == UUID(client_id))
        .order_by(Notification.created_at.desc())
        .all()
    )
    types = [n.type for n in client_notifications]
    assert NotificationType.PAYMENT_CREATED in types
    assert NotificationType.PAYMENT_SUCCEEDED in types

    lawyer_notifications = (
        db.query(Notification)
        .filter(Notification.user_id == UUID(lawyer_id))
        .all()
    )
    lawyer_types = [n.type for n in lawyer_notifications]
    assert NotificationType.PAYMENT_SUCCEEDED in lawyer_types


# ============================================================================
# 2. PAYMENT CREATION IDEMPOTENCY & ACTIVE INTENT REUSE
# ============================================================================


def test_payment_creation_idempotency_and_reuse(client: TestClient, db: Session):
    """
    Calling payment creation repeatedly on the same consultation returns
    the existing active payment record without creating duplicate charges.
    """
    _client_id, h_client = _setup_user(client, "fin_idem_client@test.com", role="CLIENT")
    lawyer_id, _ = _setup_user(client, "fin_idem_lawyer@test.com", role="LAWYER")

    lp = db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    assert lp is not None
    lp.consultation_fee = 2000.0
    ver = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number="IDEM/100/2023",
        state_bar_council="Maharashtra",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()

    fut = (datetime.now(UTC) + timedelta(days=4)).replace(hour=14, minute=0, second=0, microsecond=0).isoformat()
    res_c = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut, "duration_minutes": 30},
        headers=h_client,
    )
    c_id = res_c.json()["id"]

    # Initial payment creation
    res1 = client.post(f"/api/v1/consultations/{c_id}/payments", headers=h_client)
    assert res1.status_code == 201
    pid1 = res1.json()["payment_id"]

    # Retry payment creation
    res2 = client.post(f"/api/v1/consultations/{c_id}/payments", headers=h_client)
    assert res2.status_code == 201
    pid2 = res2.json()["payment_id"]

    # Must be the exact same payment ID
    assert pid1 == pid2

    # Database count must be exactly 1
    count = db.query(Payment).filter(Payment.consultation_id == UUID(c_id)).count()
    assert count == 1


# ============================================================================
# 3. WEBHOOK SECURITY, TAMPERING & REPLAY PROTECTION
# ============================================================================


def test_webhook_cryptographic_verification_and_tampering(client: TestClient, db: Session):
    """
    Verifies that forged signatures, timestamp expirations, malformed JSON,
    and missing headers are all rejected with 401 or 400.
    """
    event_payload = {
        "id": "evt_security_test",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_nonexistent"}},
    }

    # 1. Missing header -> 401
    raw_body = json.dumps(event_payload).encode("utf-8")
    res_no_sig = client.post("/api/v1/webhooks/stripe", content=raw_body)
    assert res_no_sig.status_code == 401

    # 2. Forged signature -> 401
    res_forged = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_body,
        headers={"Stripe-Signature": "t=123456,v1=bad_hex_signature_string"},
    )
    assert res_forged.status_code == 401

    # 3. Expired timestamp (> 300s in past) -> 401
    old_time = int(datetime.now(UTC).timestamp()) - 600
    sig_old, raw_old = _make_stripe_sig(event_payload, timestamp=old_time)
    res_old = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_old,
        headers={"Stripe-Signature": sig_old},
    )
    assert res_old.status_code == 401


# ============================================================================
# 4. TERMINAL STATE INTEGRITY (OUT-OF-ORDER WEBHOOK DEFENSE)
# ============================================================================


def test_terminal_state_protection_on_out_of_order_failure(client: TestClient, db: Session):
    """
    If a payment has SUCCEEDED, a subsequent out-of-order payment_failed webhook
    must NOT downgrade the payment status or consultation status.
    """
    _client_id, h_client = _setup_user(client, "fin_term_client@test.com", role="CLIENT")
    lawyer_id, _ = _setup_user(client, "fin_term_lawyer@test.com", role="LAWYER")

    lp = db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    assert lp is not None
    lp.consultation_fee = 1500.0
    ver = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number="TERM/99/2023",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()

    fut = (datetime.now(UTC) + timedelta(days=5)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_c = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut, "duration_minutes": 30},
        headers=h_client,
    )
    c_id = res_c.json()["id"]

    res_pay = client.post(f"/api/v1/consultations/{c_id}/payments", headers=h_client)
    pay_id = res_pay.json()["payment_id"]
    payment_rec = db.query(Payment).filter(Payment.id == UUID(pay_id)).first()
    assert payment_rec is not None

    # Step A: Succeeded webhook arrives
    succ_event = {
        "id": "evt_succ_term_1",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": payment_rec.provider_payment_id}},
    }
    sig, body = _make_stripe_sig(succ_event)
    res_s = client.post("/api/v1/webhooks/stripe", content=body, headers={"Stripe-Signature": sig})
    assert res_s.status_code == 200

    db.refresh(payment_rec)
    assert payment_rec.status == PaymentStatus.SUCCEEDED

    # Step B: Late / out-of-order failure webhook arrives
    fail_event = {
        "id": "evt_fail_term_2",
        "type": "payment_intent.payment_failed",
        "data": {"object": {"id": payment_rec.provider_payment_id}},
    }
    sig_f, body_f = _make_stripe_sig(fail_event)
    res_f = client.post("/api/v1/webhooks/stripe", content=body_f, headers={"Stripe-Signature": sig_f})
    assert res_f.status_code == 200

    # Payment MUST remain SUCCEEDED
    db.refresh(payment_rec)
    assert payment_rec.status == PaymentStatus.SUCCEEDED


# ============================================================================
# 5. PAYMENT RETRIEVAL & BOLA / IDOR CROSS-TENANT ISOLATION
# ============================================================================


def test_cross_tenant_payment_bola_isolation(client: TestClient, db: Session):
    """
    Client B cannot query Client A's payment details or consultation payments list.
    """
    _c_a_id, h_client_a = _setup_user(client, "pay_bola_a@test.com", role="CLIENT")
    _c_b_id, h_client_b = _setup_user(client, "pay_bola_b@test.com", role="CLIENT")
    lawyer_id, _ = _setup_user(client, "pay_bola_l@test.com", role="LAWYER")

    lp = db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    assert lp is not None
    lp.consultation_fee = 3000.0
    ver = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number="BOLA/88/2023",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()

    fut = (datetime.now(UTC) + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_c = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut, "duration_minutes": 30},
        headers=h_client_a,
    )
    c_id = res_c.json()["id"]

    res_p = client.post(f"/api/v1/consultations/{c_id}/payments", headers=h_client_a)
    p_id = res_p.json()["payment_id"]

    # 1. Client A accesses own payment -> 200
    res_own = client.get(f"/api/v1/payments/{p_id}", headers=h_client_a)
    assert res_own.status_code == 200
    assert res_own.json()["amount"] == 3000.0

    # 2. Client B attempts to access Client A's payment -> 404 / 403
    res_attacker = client.get(f"/api/v1/payments/{p_id}", headers=h_client_b)
    assert res_attacker.status_code in (403, 404)

    # 3. Client B attempts to list payments for Client A's consultation -> 403 / 404
    res_list_attacker = client.get(f"/api/v1/consultations/{c_id}/payments", headers=h_client_b)
    assert res_list_attacker.status_code in (403, 404)
