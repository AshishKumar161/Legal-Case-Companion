import hashlib
import hmac
import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient


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


def test_payment_and_confirmation_flow(client: TestClient, db):
    # Setup client and lawyer
    _client_id, h_client = _setup_user(
        client, "pay_client@ex.com", "Pass123!", "CLIENT"
    )
    lawyer_id, h_lawyer = _setup_user(client, "pay_lawyer@ex.com", "Pass123!", "LAWYER")

    # Verify lawyer
    from uuid import UUID

    from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus

    l_prof = (
        db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    )
    l_prof.consultation_fee = 500.0

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

    # Create case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Payment Case", "description": "D"},
        headers=h_client,
    )
    case_id = res_case.json()["id"]
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_client,
    )

    # Request consultation
    fut = datetime.now(UTC).replace(year=2030, month=6, day=15, hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_req = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "case_id": case_id,
            "scheduled_at": fut,
            "duration_minutes": 60,
        },
        headers=h_client,
    )
    c_id = res_req.json()["id"]

    # Lawyer cannot confirm yet because it's not paid
    res_conf_early = client.post(
        f"/api/v1/consultations/{c_id}/confirm", headers=h_lawyer
    )
    assert res_conf_early.status_code == 422
    assert "must be PAID" in res_conf_early.json()["error"]["message"]

    # Client creates payment
    res_pay = client.post(f"/api/v1/consultations/{c_id}/payments", headers=h_client)
    assert res_pay.status_code == 201
    pay_data = res_pay.json()
    assert pay_data["amount"] == 500.0

    # Webhook triggers payment success
    provider_id = pay_data["client_secret"].replace("_secret_test", "")
    webhook_payload = {
        "id": "evt_test",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": provider_id}},
    }
    wh_sig, wh_raw = _make_stripe_sig(webhook_payload)
    res_webhook = client.post(
        "/api/v1/payments/webhooks/stripe",
        headers={"Stripe-Signature": wh_sig, "Content-Type": "application/json"},
        content=wh_raw,
    )
    assert res_webhook.status_code == 200

    # Verify Consultation is PAID
    res_c_paid = client.get(f"/api/v1/consultations/{c_id}", headers=h_client)
    assert res_c_paid.json()["status"] == "PAID"

    # Lawyer can now confirm
    res_conf = client.post(f"/api/v1/consultations/{c_id}/confirm", headers=h_lawyer)
    assert res_conf.status_code == 200
    assert res_conf.json()["status"] == "SCHEDULED"
