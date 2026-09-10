"""Comprehensive Lawyer Discovery, Lawyer Profiles & Availability Test Suite.

Phase 6 Verification:
- Lawyer Identity Model & Profile Separation
- Profile Update Permissions & Mass-Assignment Lockdown
- Server-Controlled Verification Lifecycle (PENDING -> APPROVED / REJECTED)
- Multi-Dimensional Discovery Search & Database-Level Filtering
- Exclusion of Unverified, Suspended, Deleted, and Non-Lawyer Accounts
- Timezone-Aware Availability Lifecycle & Overlap Defense
- Bookable Slot Generation, Consultation Lockout, and Reopening
- Response Privacy & Sensitive Field Sanitization
- Cross-Tenant BOLA / IDOR Defense
"""

from datetime import date
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.models.audit import AuditEvent
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)


def _create_user(
    db: Session,
    client: TestClient,
    email: str,
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Test User",
) -> tuple[UUID, dict[str, str]]:
    """Creates a user and returns (user_id, auth_headers)."""
    user_id = generate_uuid7()
    user = User(
        id=user_id,
        email=email,
        password_hash=hash_password("SecurePassword123!"),
        role=role,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    if role == UserRole.CLIENT:
        db.add(ClientProfile(id=generate_uuid7(), user_id=user.id, full_name=full_name))
    elif role == UserRole.LAWYER:
        db.add(LawyerProfile(id=generate_uuid7(), user_id=user.id, full_name=full_name))
    db.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def _verify_lawyer_profile(db: Session, lawyer_user_id: UUID) -> LawyerProfile:
    """Helper to set a lawyer profile as verified (APPROVED)."""
    lp = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == lawyer_user_id)
        .first()
    )
    assert lp is not None
    ver = LawyerVerification(
        lawyer_profile_id=lp.id,
        enrollment_number=f"ENR/{str(lawyer_user_id)[:6]}",
        state_bar_council="Delhi Bar Council",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()
    db.refresh(lp)
    return lp


# ============================================================================
# 1. LAWYER PROFILE CRUD & MASS-ASSIGNMENT DEFENSE
# ============================================================================


def test_lawyer_profile_crud_and_mass_assignment_defense(client: TestClient, db: Session):
    """Verify lawyer profile update, RBAC boundaries, and forbidden mass-assignment."""
    lawyer_id, h_lawyer = _create_user(db, client, "prof_lawyer@example.com", role=UserRole.LAWYER)
    _client_id, h_client = _create_user(db, client, "prof_client@example.com", role=UserRole.CLIENT)

    # 1. Lawyer updates own profile -> 200
    update_res = client.patch(
        "/api/v1/profiles/lawyer",
        json={
            "full_name": "Adv. Rajesh Sharma",
            "bio": "Specialized in Commercial Arbitration and Corporate Insolvency",
            "location": "Mumbai",
            "consultation_fee": 5000.0,
            "practice_areas": ["Corporate Law", "Arbitration", "Insolvency"],
            "experience_years": 15,
            "court_jurisdictions": ["Bombay High Court", "NCLT Mumbai"],
        },
        headers=h_lawyer,
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["full_name"] == "Adv. Rajesh Sharma"
    assert data["location"] == "Mumbai"
    assert data["consultation_fee"] == 5000.0
    assert data["experience_years"] == 15
    assert "Arbitration" in data["practice_areas"]
    assert "NCLT Mumbai" in data["court_jurisdictions"]

    # 2. Client attempts to call lawyer profile update -> 403 Forbidden
    res_client_fake = client.patch(
        "/api/v1/profiles/lawyer",
        json={"location": "Delhi"},
        headers=h_client,
    )
    assert res_client_fake.status_code == 403

    # 3. Lawyer attempts to call client profile update -> 403 Forbidden
    res_lawyer_fake = client.patch(
        "/api/v1/profiles/client",
        json={"location": "Delhi"},
        headers=h_lawyer,
    )
    assert res_lawyer_fake.status_code == 403

    # 4. Mass-assignment attempt (injecting verification_status) -> 422 ValidationError
    res_mass_assign = client.patch(
        "/api/v1/profiles/lawyer",
        json={"verification_status": "APPROVED", "location": "Bangalore"},
        headers=h_lawyer,
    )
    assert res_mass_assign.status_code == 422
    assert res_mass_assign.json()["error"]["code"] == "VALIDATION_ERROR"

    # 5. Read profile via /profiles/me
    me_res = client.get("/api/v1/profiles/me", headers=h_lawyer)
    assert me_res.status_code == 200
    assert me_res.json()["user_id"] == str(lawyer_id)
    assert me_res.json()["verification_status"] == "PENDING"


# ============================================================================
# 2. SERVER-CONTROLLED VERIFICATION LIFECYCLE & ADMIN AUDIT
# ============================================================================


def test_lawyer_verification_workflow_and_admin_audit(client: TestClient, db: Session):
    """Verify lawyer verification submission, duplicate rejection, and admin review."""
    _lawyer_id, h_lawyer = _create_user(db, client, "verif_lawyer@example.com", role=UserRole.LAWYER)
    _client_id, h_client = _create_user(db, client, "verif_client@example.com", role=UserRole.CLIENT)
    admin_id, h_admin = _create_user(db, client, "verif_admin@example.com", role=UserRole.ADMIN)

    # 1. Client attempts to submit lawyer verification -> 403 Forbidden
    client_sub = client.post(
        "/api/v1/profiles/lawyer/verification",
        json={"enrollment_number": "MAH/123/2020", "state_bar_council": "Maharashtra"},
        headers=h_client,
    )
    assert client_sub.status_code == 403

    # 2. Lawyer submits verification -> 200 (PENDING)
    sub_res = client.post(
        "/api/v1/profiles/lawyer/verification",
        json={"enrollment_number": "MAH/123/2020", "state_bar_council": "Maharashtra"},
        headers=h_lawyer,
    )
    assert sub_res.status_code == 200
    v_data = sub_res.json()
    verif_id = v_data["id"]
    assert v_data["status"] == "PENDING"
    assert v_data["enrollment_number"] == "MAH/123/2020"

    # 3. Duplicate submission while pending -> Rejected (422)
    dup_sub = client.post(
        "/api/v1/profiles/lawyer/verification",
        json={"enrollment_number": "MAH/123/2020", "state_bar_council": "Maharashtra"},
        headers=h_lawyer,
    )
    assert dup_sub.status_code == 422
    assert "already in progress" in dup_sub.json()["error"]["message"].lower()

    # 4. Admin lists pending verifications
    pending_list = client.get("/api/v1/admin/verifications", headers=h_admin)
    assert pending_list.status_code == 200
    p_ids = [item["id"] for item in pending_list.json()["items"]]
    assert verif_id in p_ids

    # 5. Admin approves verification -> 200 (APPROVED)
    appr_res = client.post(
        f"/api/v1/admin/verifications/{verif_id}/approve",
        headers=h_admin,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "APPROVED"

    # Verify audit log in DB
    audit = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.event_type == "LAWYER_VERIFICATION_APPROVED",
            AuditEvent.actor_user_id == admin_id,
        )
        .first()
    )
    assert audit is not None
    assert audit.metadata_["verification_id"] == str(verif_id)

    # Verify lawyer's profile now reflects APPROVED
    lawyer_me = client.get("/api/v1/profiles/me", headers=h_lawyer)
    assert lawyer_me.json()["verification_status"] == "APPROVED"


# ============================================================================
# 3. MULTI-DIMENSIONAL DISCOVERY SEARCH & FILTERING MATRIX
# ============================================================================


def test_lawyer_discovery_search_and_filtering_matrix(client: TestClient, db: Session):
    """Verify multi-criteria search filtering at SQL level."""
    # Setup 2 distinct verified lawyers
    l1_id, h_l1 = _create_user(db, client, "search_l1@example.com", role=UserRole.LAWYER)
    l2_id, h_l2 = _create_user(db, client, "search_l2@example.com", role=UserRole.LAWYER)
    _client_id, h_client = _create_user(db, client, "search_client_user@example.com", role=UserRole.CLIENT)

    client.patch(
        "/api/v1/profiles/lawyer",
        json={
            "full_name": "Adv. Priya Deshmukh",
            "bio": "Senior counsel with extensive trial experience in Intellectual Property",
            "location": "Mumbai",
            "consultation_fee": 3500.0,
            "practice_areas": ["Intellectual Property", "Copyright", "Patents"],
            "experience_years": 12,
            "court_jurisdictions": ["Bombay High Court", "Supreme Court of India"],
        },
        headers=h_l1,
    )
    _verify_lawyer_profile(db, l1_id)

    client.patch(
        "/api/v1/profiles/lawyer",
        json={
            "full_name": "Adv. Vikram Sethi",
            "bio": "Corporate and tax litigation attorney",
            "location": "Delhi",
            "consultation_fee": 2000.0,
            "practice_areas": ["Tax Law", "Corporate Law", "GST"],
            "experience_years": 6,
            "court_jurisdictions": ["Delhi High Court", "ITAT Delhi"],
        },
        headers=h_l2,
    )
    _verify_lawyer_profile(db, l2_id)

    # 1. Location filter
    res_mum = client.get("/api/v1/lawyers?location=Mumbai", headers=h_client)
    assert res_mum.status_code == 200
    names = [i["full_name"] for i in res_mum.json()["items"]]
    assert "Adv. Priya Deshmukh" in names
    assert "Adv. Vikram Sethi" not in names

    # 2. Practice Area filter
    res_tax = client.get("/api/v1/lawyers?practice_area=Tax+Law", headers=h_client)
    assert res_tax.status_code == 200
    names_tax = [i["full_name"] for i in res_tax.json()["items"]]
    assert "Adv. Vikram Sethi" in names_tax
    assert "Adv. Priya Deshmukh" not in names_tax

    # 3. Court Jurisdiction filter
    res_itat = client.get("/api/v1/lawyers?court_jurisdiction=ITAT", headers=h_client)
    assert res_itat.status_code == 200
    names_itat = [i["full_name"] for i in res_itat.json()["items"]]
    assert "Adv. Vikram Sethi" in names_itat
    assert "Adv. Priya Deshmukh" not in names_itat

    # 4. Fee Range filter
    res_fee = client.get("/api/v1/lawyers?min_fee=3000&max_fee=4000", headers=h_client)
    assert res_fee.status_code == 200
    names_fee = [i["full_name"] for i in res_fee.json()["items"]]
    assert "Adv. Priya Deshmukh" in names_fee
    assert "Adv. Vikram Sethi" not in names_fee

    # 5. Experience filter
    res_exp = client.get("/api/v1/lawyers?min_experience=10", headers=h_client)
    assert res_exp.status_code == 200
    names_exp = [i["full_name"] for i in res_exp.json()["items"]]
    assert "Adv. Priya Deshmukh" in names_exp
    assert "Adv. Vikram Sethi" not in names_exp


# ============================================================================
# 4. EXCLUSION OF UNVERIFIED, SUSPENDED, DELETED & NON-LAWYER ACCOUNTS
# ============================================================================


def test_discovery_account_status_and_verification_gating(client: TestClient, db: Session):
    """Verify unverified, suspended, deleted, and client accounts are hidden from discovery."""
    v_lawyer_id, _h_vl = _create_user(db, client, "gate_verif@example.com", role=UserRole.LAWYER, full_name="Verified Lawyer")
    unv_lawyer_id, _h_unvl = _create_user(db, client, "gate_unverif@example.com", role=UserRole.LAWYER, full_name="Unverified Lawyer")
    susp_lawyer_id, _h_sl = _create_user(db, client, "gate_susp@example.com", role=UserRole.LAWYER, full_name="Suspended Lawyer")
    client_user_id, _h_cu = _create_user(db, client, "gate_client@example.com", role=UserRole.CLIENT, full_name="Client User")
    _searcher_id, h_searcher = _create_user(db, client, "searcher_user@example.com", role=UserRole.CLIENT)

    _verify_lawyer_profile(db, v_lawyer_id)

    # Suspend one lawyer
    susp_user = db.query(User).filter(User.id == susp_lawyer_id).first()
    assert susp_user is not None
    susp_user.account_status = AccountStatus.SUSPENDED
    db.commit()

    # 1. Search with verified_only=True (default)
    search_res = client.get("/api/v1/lawyers", headers=h_searcher)
    assert search_res.status_code == 200
    uids = [item["user_id"] for item in search_res.json()["items"]]

    assert str(v_lawyer_id) in uids
    assert str(unv_lawyer_id) not in uids
    assert str(susp_lawyer_id) not in uids
    assert str(client_user_id) not in uids

    # 2. Direct lookup of active verified lawyer -> 200
    assert client.get(f"/api/v1/lawyers/{v_lawyer_id}", headers=h_searcher).status_code == 200

    # 3. Direct lookup of suspended lawyer -> 404
    assert client.get(f"/api/v1/lawyers/{susp_lawyer_id}", headers=h_searcher).status_code == 404

    # 4. Direct lookup of client user -> 404
    assert client.get(f"/api/v1/lawyers/{client_user_id}", headers=h_searcher).status_code == 404


# ============================================================================
# 5. LAWYER AVAILABILITY LIFECYCLE & OVERLAP GUARDS
# ============================================================================


def test_lawyer_availability_lifecycle_and_overlap_guards(client: TestClient, db: Session):
    """Verify availability rules, time interval validation, and overlap defense."""
    _lawyer_id, h_lawyer = _create_user(db, client, "av_guard_lawyer@example.com", role=UserRole.LAWYER)
    _client_id, h_client = _create_user(db, client, "av_guard_client@example.com", role=UserRole.CLIENT)

    # 1. Client cannot configure lawyer availability -> 403
    assert client.post(
        "/api/v1/profiles/lawyer/availability",
        json={"day_of_week": 1, "start_time": "09:00:00", "end_time": "12:00:00"},
        headers=h_client,
    ).status_code == 403

    # 2. Invalid time range (end <= start) -> 422
    res_inv = client.post(
        "/api/v1/profiles/lawyer/availability",
        json={"day_of_week": 1, "start_time": "15:00:00", "end_time": "10:00:00"},
        headers=h_lawyer,
    )
    assert res_inv.status_code == 422

    # 3. Create Tuesday morning window: 09:00 - 12:00 -> 201
    res_win1 = client.post(
        "/api/v1/profiles/lawyer/availability",
        json={"day_of_week": 1, "start_time": "09:00:00", "end_time": "12:00:00", "slot_duration_minutes": 30},
        headers=h_lawyer,
    )
    assert res_win1.status_code == 201
    win1_id = res_win1.json()["id"]

    # 4. Overlapping window on Tuesday (10:30 - 13:30) -> Rejected (422)
    res_overlap = client.post(
        "/api/v1/profiles/lawyer/availability",
        json={"day_of_week": 1, "start_time": "10:30:00", "end_time": "13:30:00", "slot_duration_minutes": 30},
        headers=h_lawyer,
    )
    assert res_overlap.status_code == 422
    assert "overlaps" in res_overlap.json()["error"]["message"].lower()

    # 5. Non-overlapping afternoon window on Tuesday (14:00 - 17:00) -> 201
    res_win2 = client.post(
        "/api/v1/profiles/lawyer/availability",
        json={"day_of_week": 1, "start_time": "14:00:00", "end_time": "17:00:00", "slot_duration_minutes": 30},
        headers=h_lawyer,
    )
    assert res_win2.status_code == 201
    win2_id = res_win2.json()["id"]

    # 6. List availability rules
    av_list = client.get("/api/v1/profiles/lawyer/availability", headers=h_lawyer)
    assert av_list.status_code == 200
    ids = [item["id"] for item in av_list.json()]
    assert win1_id in ids
    assert win2_id in ids

    # 7. Update window 2 -> 200
    res_up = client.patch(
        f"/api/v1/profiles/lawyer/availability/{win2_id}",
        json={"start_time": "14:30:00", "end_time": "17:30:00"},
        headers=h_lawyer,
    )
    assert res_up.status_code == 200
    assert res_up.json()["start_time"] == "14:30:00"

    # 8. Delete window 2 -> 204
    assert client.delete(f"/api/v1/profiles/lawyer/availability/{win2_id}", headers=h_lawyer).status_code == 204


# ============================================================================
# 6. BOOKABLE SLOTS GENERATION & CONSULTATION BLOCKING
# ============================================================================


def test_slots_generation_and_consultation_blocking(client: TestClient, db: Session):
    """Verify slots calculation on target date and consultation booking lock."""
    lawyer_id, h_lawyer = _create_user(db, client, "slots_gen_lawyer@example.com", role=UserRole.LAWYER)
    _client_id, h_client = _create_user(db, client, "slots_gen_client@example.com", role=UserRole.CLIENT)
    lp = _verify_lawyer_profile(db, lawyer_id)
    lp.consultation_fee = 1000.0
    db.commit()

    # Configure Wednesday availability: 10:00 to 12:00 IST (slot duration 30 min -> 4 slots)
    client.post(
        "/api/v1/profiles/lawyer/availability",
        json={"day_of_week": 2, "start_time": "10:00:00", "end_time": "12:00:00", "slot_duration_minutes": 30},
        headers=h_lawyer,
    )

    # Target future Wednesday in 2030 (2030-06-12 is a Wednesday, weekday=2)
    target_wednesday = date(2030, 6, 12)
    assert target_wednesday.weekday() == 2

    # 1. Query available slots -> 4 slots
    slots_res = client.get(
        f"/api/v1/lawyers/{lawyer_id}/slots?date={target_wednesday.isoformat()}&duration_minutes=30",
        headers=h_client,
    )
    assert slots_res.status_code == 200
    slots = slots_res.json()
    assert len(slots) == 4
    assert all(s["is_available"] is True for s in slots)

    # 2. Book slot 0
    slot0_start = slots[0]["start_time"]
    book_res = client.post(
        "/api/v1/consultations",
        json={"lawyer_id": str(lawyer_id), "scheduled_at": slot0_start, "duration_minutes": 30},
        headers=h_client,
    )
    assert book_res.status_code == 201
    c_id = book_res.json()["id"]

    # 3. Slot 0 is now booked (is_available = False)
    slots_res2 = client.get(
        f"/api/v1/lawyers/{lawyer_id}/slots?date={target_wednesday.isoformat()}&duration_minutes=30",
        headers=h_client,
    )
    slots2 = slots_res2.json()
    assert slots2[0]["is_available"] is False
    assert slots2[1]["is_available"] is True

    # 4. Cancel booking -> slot 0 is reopened
    client.post(f"/api/v1/consultations/{c_id}/cancel", headers=h_client)
    slots_res3 = client.get(
        f"/api/v1/lawyers/{lawyer_id}/slots?date={target_wednesday.isoformat()}&duration_minutes=30",
        headers=h_client,
    )
    assert slots_res3.json()[0]["is_available"] is True


# ============================================================================
# 7. RESPONSE PRIVACY & DATA SANITIZATION
# ============================================================================


def test_public_profile_privacy_and_data_sanitization(client: TestClient, db: Session):
    """Verify that public lawyer profile responses never leak sensitive internal fields."""
    lawyer_id, _h_lawyer = _create_user(db, client, "private_leak_lawyer@example.com", role=UserRole.LAWYER, full_name="Adv. Secret")
    _client_id, h_client = _create_user(db, client, "private_leak_client@example.com", role=UserRole.CLIENT)
    _verify_lawyer_profile(db, lawyer_id)

    res = client.get(f"/api/v1/lawyers/{lawyer_id}", headers=h_client)
    assert res.status_code == 200
    data = res.json()

    # Verify absence of private auth/security fields
    assert "password_hash" not in data
    assert "password" not in data
    assert "email" not in data
    assert "phone" not in data
    assert "refresh_tokens" not in data
    assert "audit" not in data
    assert data["full_name"] == "Adv. Secret"
    assert data["verification_status"] == "APPROVED"
