import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.consultation import Consultation
from app.models.user import (
    AccountStatus,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
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
# 1. LAWYER DISCOVERY & PROFILE PRIVACY
# ============================================================================


def test_lawyer_discovery_filtering_and_privacy(client: TestClient, db: Session):
    _client_id, h_client = _setup_user(client, "disc_client@test.com", role="CLIENT")
    lawyer1_id, _h_l1 = _setup_user(
        client, "disc_lawyer1@test.com", role="LAWYER", full_name="Arjun Mehta"
    )
    lawyer2_id, _h_l2 = _setup_user(
        client, "disc_lawyer2@test.com", role="LAWYER", full_name="Pooja Sharma"
    )
    suspended_lawyer_id, _h_ls = _setup_user(
        client, "disc_suspended@test.com", role="LAWYER", full_name="Suspended Counsel"
    )

    # Configure lawyer 1
    l1_prof = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == UUID(lawyer1_id))
        .first()
    )
    assert l1_prof is not None
    l1_prof.location = "Mumbai"
    l1_prof.bio = "Senior Corporate and Tax Advocate"
    l1_prof.practice_areas = ["Corporate Law", "Taxation"]
    l1_prof.consultation_fee = 5000.0

    # Configure lawyer 2
    l2_prof = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == UUID(lawyer2_id))
        .first()
    )
    assert l2_prof is not None
    l2_prof.location = "Delhi"
    l2_prof.bio = "Civil Litigation and Family Law Specialist"
    l2_prof.practice_areas = ["Civil Litigation", "Family Law"]
    l2_prof.consultation_fee = 2500.0

    # Verify lawyer 1
    ver1 = LawyerVerification(
        lawyer_profile_id=l1_prof.id,
        enrollment_number="MAH/123/2015",
        state_bar_council="Maharashtra",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver1)

    # Suspend lawyer 3
    sus_user = db.query(User).filter(User.id == UUID(suspended_lawyer_id)).first()
    assert sus_user is not None
    sus_user.account_status = AccountStatus.SUSPENDED
    db.commit()

    # 1. Search by location
    res_mumbai = client.get("/api/v1/lawyers?location=Mumbai", headers=h_client)
    assert res_mumbai.status_code == 200
    mumbai_items = res_mumbai.json()["items"]
    assert len(mumbai_items) == 1
    assert mumbai_items[0]["user_id"] == lawyer1_id

    # 2. Search by keyword
    res_kw = client.get("/api/v1/lawyers?search=Advocate", headers=h_client)
    assert res_kw.status_code == 200
    assert len(res_kw.json()["items"]) == 1
    assert res_kw.json()["items"][0]["full_name"] == "Arjun Mehta"

    # 3. Search by fee range (explicitly requesting unverified for testing)
    res_fee = client.get("/api/v1/lawyers?min_fee=2000&max_fee=3000&verified_only=false", headers=h_client)
    assert res_fee.status_code == 200
    assert len(res_fee.json()["items"]) == 1
    assert res_fee.json()["items"][0]["user_id"] == lawyer2_id

    # 4. Filter verified only
    res_ver = client.get("/api/v1/lawyers?verified_only=true", headers=h_client)
    assert res_ver.status_code == 200
    ver_ids = [item["user_id"] for item in res_ver.json()["items"]]
    assert lawyer1_id in ver_ids
    assert lawyer2_id not in ver_ids

    # 5. Suspended lawyer is hidden from search and returns 404 on direct get
    res_all = client.get("/api/v1/lawyers?verified_only=false", headers=h_client)
    all_ids = [item["user_id"] for item in res_all.json()["items"]]
    assert suspended_lawyer_id not in all_ids

    res_sus_get = client.get(f"/api/v1/lawyers/{suspended_lawyer_id}", headers=h_client)
    assert res_sus_get.status_code == 404

    # 6. Privacy check: verify response does not leak password, email, or token
    sample = res_mumbai.json()["items"][0]
    assert "password" not in sample
    assert "password_hash" not in sample
    assert "email" not in sample
    assert "token" not in sample


# ============================================================================
# 2. LAWYER VERIFICATION LIFECYCLE & ADMIN ACTIONS
# ============================================================================


def test_lawyer_verification_lifecycle(client: TestClient, db: Session):
    admin_id, _h_dummy = _setup_user(client, "verif_admin@test.com", role="CLIENT")
    # Make sure admin user has role ADMIN in DB
    u_admin = db.query(User).filter(User.id == UUID(admin_id)).first()
    assert u_admin is not None
    u_admin.role = UserRole.ADMIN
    db.commit()
    # Login as admin to get token with ADMIN role
    res_adm_login = client.post(
        "/api/v1/auth/login",
        json={"email": "verif_admin@test.com", "password": "Pass123!"},
    )
    h_admin = {"Authorization": f"Bearer {res_adm_login.json()['access_token']}"}

    lawyer_id, h_lawyer = _setup_user(client, "verif_lawyer@test.com", role="LAWYER")
    _client_id, h_client = _setup_user(client, "verif_client@test.com", role="CLIENT")

    # 1. Lawyer submits verification
    res_sub = client.post(
        "/api/v1/profiles/lawyer/verification",
        json={"enrollment_number": "DEL/999/2021", "state_bar_council": "Delhi"},
        headers=h_lawyer,
    )
    assert res_sub.status_code == 200
    verif_id = res_sub.json()["id"]
    assert res_sub.json()["status"] == "PENDING"

    # 2. Duplicate submission is rejected
    res_dup = client.post(
        "/api/v1/profiles/lawyer/verification",
        json={"enrollment_number": "DEL/999/2021", "state_bar_council": "Delhi"},
        headers=h_lawyer,
    )
    assert res_dup.status_code == 422

    # 3. Non-admin cannot view or review verifications
    res_unauth_q = client.get("/api/v1/admin/verifications", headers=h_client)
    assert res_unauth_q.status_code == 403

    res_unauth_rev = client.post(
        f"/api/v1/admin/verifications/{verif_id}/approve", headers=h_client
    )
    assert res_unauth_rev.status_code == 403

    # 4. Admin views pending queue
    res_q = client.get("/api/v1/admin/verifications", headers=h_admin)
    assert res_q.status_code == 200
    q_ids = [item["id"] for item in res_q.json()["items"]]
    assert verif_id in q_ids

    # 5. Admin approves verification
    res_appr = client.post(
        f"/api/v1/admin/verifications/{verif_id}/approve", headers=h_admin
    )
    assert res_appr.status_code == 200
    assert res_appr.json()["status"] == "APPROVED"

    # 6. Check lawyer profile shows APPROVED
    res_l_prof = client.get(f"/api/v1/lawyers/{lawyer_id}", headers=h_client)
    assert res_l_prof.status_code == 200
    assert res_l_prof.json()["verification_status"] == "APPROVED"


# ============================================================================
# 3. CONSULTATION REQUEST, DUPLICATES & VALIDATIONS
# ============================================================================


def test_consultation_request_and_validations(client: TestClient, db: Session):
    _client_id, h_client = _setup_user(client, "req_client@test.com", role="CLIENT")
    lawyer_id, _h_lawyer = _setup_user(client, "req_lawyer@test.com", role="LAWYER")
    unverif_lawyer_id, _h_unverif = _setup_user(
        client, "req_unverif@test.com", role="LAWYER"
    )

    # Verify lawyer 1
    l_prof = (
        db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    )
    assert l_prof is not None
    l_prof.consultation_fee = 1000.0
    ver = LawyerVerification(
        lawyer_profile_id=l_prof.id,
        enrollment_number="KAR/555/2018",
        state_bar_council="Karnataka",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Contract Review Case", "description": "Desc"},
        headers=h_client,
    )
    case_id = res_case.json()["id"]

    # 1. Attempt consultation with unverified lawyer -> 422
    fut = (datetime.now(UTC) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_unv = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": unverif_lawyer_id,
            "case_id": case_id,
            "scheduled_at": fut,
            "duration_minutes": 30,
        },
        headers=h_client,
    )
    assert res_unv.status_code == 422
    assert "verified lawyers" in res_unv.json()["error"]["message"]

    # 2. Attempt consultation with past scheduled_at -> 422
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    res_past = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "case_id": case_id,
            "scheduled_at": past,
            "duration_minutes": 30,
        },
        headers=h_client,
    )
    assert res_past.status_code == 422
    assert "future time" in res_past.json()["error"]["message"]

    # 3. Successful consultation request
    res_ok = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "case_id": case_id,
            "scheduled_at": fut,
            "duration_minutes": 45,
        },
        headers=h_client,
    )
    assert res_ok.status_code == 201
    c_data = res_ok.json()
    assert c_data["status"] == "REQUESTED"
    assert c_data["fee_amount"] == 1000.0
    assert c_data["duration_minutes"] == 45

    # 4. Duplicate request for exact same slot -> 422
    res_dup = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": lawyer_id,
            "case_id": case_id,
            "scheduled_at": fut,
            "duration_minutes": 45,
        },
        headers=h_client,
    )
    assert res_dup.status_code == 422


# ============================================================================
# 4. CONSULTATION STATE MACHINE: ACCEPT, REJECT, SCHEDULE, CANCEL, COMPLETE
# ============================================================================


def test_consultation_full_state_machine(client: TestClient, db: Session):
    _client_id, h_client = _setup_user(client, "sm_client@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(client, "sm_lawyer@test.com", role="LAWYER")
    other_lawyer_id, h_other_lawyer = _setup_user(
        client, "sm_other_lawyer@test.com", role="LAWYER"
    )

    # Verify both lawyers
    for l_id in (lawyer_id, other_lawyer_id):
        lp = db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(l_id)).first()
        assert lp is not None
        lp.consultation_fee = 0.0
        v = LawyerVerification(
            lawyer_profile_id=lp.id,
            enrollment_number="BAR/777/2020",
            state_bar_council="Delhi",
            status=VerificationStatus.APPROVED,
        )
        db.add(v)
    db.commit()

    # Create Case
    res_case = client.post(
        "/api/v1/cases", json={"title": "SM Case", "description": "D"}, headers=h_client
    )
    case_id = res_case.json()["id"]

    # 1. Request Consultation
    fut = (datetime.now(UTC) + timedelta(days=5)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_req = client.post(
        f"/api/v1/cases/{case_id}/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut, "duration_minutes": 30},
        headers=h_client,
    )
    assert res_req.status_code == 201
    c_id = res_req.json()["id"]

    # 2. Client cannot accept their own consultation -> 403
    assert (
        client.post(
            f"/api/v1/consultations/{c_id}/accept", headers=h_client
        ).status_code
        == 403
    )

    # 3. Unassigned lawyer cannot accept -> 404 (IDOR protection)
    assert (
        client.post(
            f"/api/v1/consultations/{c_id}/accept", headers=h_other_lawyer
        ).status_code
        == 404
    )

    # 4. Assigned lawyer accepts consultation -> ACCEPTED
    res_acc = client.post(f"/api/v1/consultations/{c_id}/accept", headers=h_lawyer)
    assert res_acc.status_code == 200
    assert res_acc.json()["status"] == "ACCEPTED"

    # 5. Schedule consultation to a revised time
    new_fut = (datetime.now(UTC) + timedelta(days=6)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_sched = client.post(
        f"/api/v1/consultations/{c_id}/schedule",
        json={"scheduled_at": new_fut, "duration_minutes": 60},
        headers=h_client,
    )
    assert res_sched.status_code == 200
    assert res_sched.json()["status"] == "SCHEDULED"
    assert res_sched.json()["duration_minutes"] == 60

    # 6. Complete consultation -> COMPLETED
    res_comp = client.post(f"/api/v1/consultations/{c_id}/complete", headers=h_lawyer)
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"
    assert res_comp.json()["completed_at"] is not None

    # 7. Cannot cancel already completed consultation -> 422
    res_canc = client.post(
        f"/api/v1/consultations/{c_id}/cancel",
        json={"reason": "Too late"},
        headers=h_client,
    )
    assert res_canc.status_code == 422


# ============================================================================
# 5. CONSULTATION REJECTION FLOW
# ============================================================================


def test_consultation_rejection_flow(client: TestClient, db: Session):
    _client_id, h_client = _setup_user(client, "rej_client@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(client, "rej_lawyer@test.com", role="LAWYER")

    lp = (
        db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    )
    assert lp is not None
    v = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number="BAR/888/2020",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(v)
    db.commit()

    # Request consultation
    fut = (datetime.now(UTC) + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_req = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut, "duration_minutes": 30},
        headers=h_client,
    )
    c_id = res_req.json()["id"]

    # Lawyer rejects consultation with reason
    res_rej = client.post(
        f"/api/v1/consultations/{c_id}/reject",
        json={"reason": "Conflict of interest with opposing party"},
        headers=h_lawyer,
    )
    assert res_rej.status_code == 200
    assert res_rej.json()["status"] == "REJECTED"
    assert (
        res_rej.json()["rejection_reason"] == "Conflict of interest with opposing party"
    )

    # Cannot accept or schedule rejected consultation
    assert (
        client.post(
            f"/api/v1/consultations/{c_id}/accept", headers=h_lawyer
        ).status_code
        == 422
    )


# ============================================================================
# 6. CONSULTATION PAYMENT FLOW & WEBHOOK INTEGRATION
# ============================================================================


def test_consultation_payment_and_webhook_flow(client: TestClient, db: Session):
    _client_id, h_client = _setup_user(client, "pay_client@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(client, "pay_lawyer@test.com", role="LAWYER")

    lp = (
        db.query(LawyerProfile).filter(LawyerProfile.user_id == UUID(lawyer_id)).first()
    )
    assert lp is not None
    lp.consultation_fee = 3500.0
    v = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number="BAR/333/2019",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(v)
    db.commit()

    # Request paid consultation
    fut = (datetime.now(UTC) + timedelta(days=4)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_req = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": lawyer_id, "scheduled_at": fut, "duration_minutes": 30},
        headers=h_client,
    )
    c_id = res_req.json()["id"]

    # Create payment intent
    res_pi = client.post(f"/api/v1/consultations/{c_id}/payments", headers=h_client)
    assert res_pi.status_code == 201
    pi_data = res_pi.json()
    assert pi_data["amount"] == 3500.0
    assert pi_data["currency"] == "INR"

    # Simulate Webhook payment success
    webhook_payload = {
        "id": "evt_test_123",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": f"pi_mock_{pi_data['payment_id']}"}},
    }
    wh_sig, wh_raw = _make_stripe_sig(webhook_payload)
    res_wh = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": wh_sig, "Content-Type": "application/json"},
        content=wh_raw,
    )
    assert res_wh.status_code == 200
    assert res_wh.json()["status"] == "success"

    # Webhook idempotency check (duplicate webhook)
    res_wh_dup = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": wh_sig, "Content-Type": "application/json"},
        content=wh_raw,
    )
    assert res_wh_dup.status_code == 200
    assert res_wh_dup.json()["status"] == "already_processed"

    # Verify consultation status transitioned to PAID
    res_c = client.get(f"/api/v1/consultations/{c_id}", headers=h_client)
    assert res_c.status_code == 200
    assert res_c.json()["status"] == "PAID"

    # Lawyer confirms consultation now that it is PAID
    res_conf = client.post(f"/api/v1/consultations/{c_id}/confirm", headers=h_lawyer)
    assert res_conf.status_code == 200
    assert res_conf.json()["status"] == "SCHEDULED"


# ============================================================================
# 7. SECURITY & BOLA/IDOR MATRIX
# ============================================================================


def test_consultation_security_bola_idor_matrix(client: TestClient, db: Session):
    _client_a_id, h_client_a = _setup_user(client, "sec_ca@test.com", role="CLIENT")
    _client_b_id, h_client_b = _setup_user(client, "sec_cb@test.com", role="CLIENT")
    lawyer_a_id, h_lawyer_a = _setup_user(client, "sec_la@test.com", role="LAWYER")
    _lawyer_b_id, h_lawyer_b = _setup_user(client, "sec_lb@test.com", role="LAWYER")

    # Verify lawyer A
    lp_a = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == UUID(lawyer_a_id))
        .first()
    )
    assert lp_a is not None
    v = LawyerVerification(
        lawyer_profile_id=lp_a.id,
        enrollment_number="SEC/111/2020",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(v)
    db.commit()

    # Client A requests consultation with Lawyer A
    fut = (datetime.now(UTC) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    res_req = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": lawyer_a_id, "scheduled_at": fut, "duration_minutes": 30},
        headers=h_client_a,
    )
    c_id = res_req.json()["id"]

    # 1. Client A -> Consultation A: ALLOW (200)
    assert (
        client.get(f"/api/v1/consultations/{c_id}", headers=h_client_a).status_code
        == 200
    )

    # 2. Client B -> Consultation A: DENY (404)
    assert (
        client.get(f"/api/v1/consultations/{c_id}", headers=h_client_b).status_code
        == 404
    )

    # 3. Lawyer A -> Assigned Consultation: ALLOW (200)
    assert (
        client.get(f"/api/v1/consultations/{c_id}", headers=h_lawyer_a).status_code
        == 200
    )

    # 4. Lawyer B -> Unassigned Consultation: DENY (404)
    assert (
        client.get(f"/api/v1/consultations/{c_id}", headers=h_lawyer_b).status_code
        == 404
    )

    # 5. Soft-delete consultation
    c_record = db.query(Consultation).filter(Consultation.id == UUID(c_id)).first()
    assert c_record is not None
    c_record.deleted_at = datetime.now(UTC)
    db.commit()

    # 6. Both Client A and Lawyer A receive 404 for deleted consultation
    assert (
        client.get(f"/api/v1/consultations/{c_id}", headers=h_client_a).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/consultations/{c_id}", headers=h_lawyer_a).status_code
        == 404
    )
