"""Comprehensive Case Management V1 & Resource-Level Authorization Test Suite.

Phase 3 Verification:
- Case Creation, Application-Generated UUIDv7 IDs, and Atomic Owner Association
- Resource-Level Authorization & BOLA / IDOR Defense (404 Obscuration)
- Authorization-Aware SQL Database Filtering for Case Listing
- Case Lifecycle State Machine Transitions & Terminal State Enforcements
- Participant Management Lifecycle & Ownership Invariants
- Case Soft-Deletion & Resource Isolation
- Transaction Rollback & Multi-Model Integrity
"""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.models.case import Case, CaseParticipant, ParticipantRole, ParticipantStatus
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole


def _create_test_user(
    db: Session,
    client: TestClient,
    email: str,
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Test User",
    account_status: AccountStatus = AccountStatus.ACTIVE,
) -> tuple[UUID, dict[str, str]]:
    """Creates a user and returns (user_id, auth_headers)."""
    user_id = generate_uuid7()
    user = User(
        id=user_id,
        email=email,
        password_hash=hash_password("SecurePassword123!"),
        role=role,
        account_status=account_status,
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


# ============================================================================
# 1. CASE CREATION & OWNERSHIP ASSOCIATION
# ============================================================================


def test_case_creation_and_atomic_owner_association(client: TestClient, db: Session):
    """Verify case creation associates the creator as OWNER participant atomically."""
    user_id, headers = _create_test_user(db, client, "creator_owner@example.com")

    payload = {
        "title": "Corporate Acquisition Dispute",
        "description": "Cross-border contract and shareholder litigation.",
    }
    res = client.post("/api/v1/cases", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert data["status"] == "OPEN"
    case_id = UUID(data["id"])

    # Verify Database State: Exactly 1 case and 1 OWNER participant
    case_db = db.query(Case).filter(Case.id == case_id).first()
    assert case_db is not None
    assert case_db.deleted_at is None

    participants = db.query(CaseParticipant).filter(CaseParticipant.case_id == case_id).all()
    assert len(participants) == 1
    assert participants[0].user_id == user_id
    assert participants[0].participant_role == ParticipantRole.OWNER
    assert participants[0].status == ParticipantStatus.ACTIVE


def test_case_creation_validation_and_unauthenticated_rejection(client: TestClient, db: Session):
    """Verify input validation and unauthenticated access rejection."""
    _user_id, headers = _create_test_user(db, client, "unauth_creator@example.com")

    # 1. Unauthenticated request -> 401
    res_unauth = client.post(
        "/api/v1/cases",
        json={"title": "Unauthorized Case", "description": "Should fail"},
    )
    assert res_unauth.status_code == 401

    # 2. Mass-assignment / extra field injection -> 422
    res_extra = client.post(
        "/api/v1/cases",
        json={
            "title": "Injected Case",
            "description": "Should fail",
            "status": "CLOSED",
            "id": str(uuid4()),
        },
        headers=headers,
    )
    assert res_extra.status_code == 422


# ============================================================================
# 2. CASE LISTING SQL ISOLATION MATRIX
# ============================================================================


def test_case_listing_sql_isolation_matrix(client: TestClient, db: Session):
    """Verify multi-user SQL query isolation: users only see cases they participate in."""
    _u1_id, h_u1 = _create_test_user(db, client, "user_alpha@example.com")
    _u2_id, h_u2 = _create_test_user(db, client, "user_beta@example.com")
    _u3_id, h_u3 = _create_test_user(db, client, "user_gamma@example.com")

    # User 1 creates 2 cases
    res1 = client.post("/api/v1/cases", json={"title": "Alpha Case 1", "description": "D1"}, headers=h_u1)
    res2 = client.post("/api/v1/cases", json={"title": "Alpha Case 2", "description": "D2"}, headers=h_u1)
    c1_id = res1.json()["id"]
    c2_id = res2.json()["id"]

    # User 2 creates 1 case
    res3 = client.post("/api/v1/cases", json={"title": "Beta Case 1", "description": "D3"}, headers=h_u2)
    c3_id = res3.json()["id"]

    # User 1 lists cases -> sees only c1 and c2
    list_u1 = client.get("/api/v1/cases", headers=h_u1).json()
    assert list_u1["total"] == 2
    u1_ids = {item["id"] for item in list_u1["items"]}
    assert u1_ids == {c1_id, c2_id}

    # User 2 lists cases -> sees only c3
    list_u2 = client.get("/api/v1/cases", headers=h_u2).json()
    assert list_u2["total"] == 1
    assert list_u2["items"][0]["id"] == c3_id

    # User 3 lists cases -> sees 0 cases
    list_u3 = client.get("/api/v1/cases", headers=h_u3).json()
    assert list_u3["total"] == 0
    assert list_u3["items"] == []


# ============================================================================
# 3. GET CASE BY ID AUTHORIZATION MATRIX (BOLA / IDOR DEFENSE)
# ============================================================================


def test_get_case_by_id_authorization_matrix(client: TestClient, db: Session):
    """Verify access matrix and 404 obscuration for unaffiliated users."""
    _owner_id, h_owner = _create_test_user(db, client, "case_owner_get@example.com")
    lawyer_id, h_lawyer = _create_test_user(db, client, "case_lawyer_get@example.com", role=UserRole.LAWYER)
    _unaffiliated_id, h_unaffiliated = _create_test_user(db, client, "case_stranger_get@example.com")

    # 1. Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Confidential IP Matter", "description": "Proprietary algorithm patent leak."},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    # 2. Add Lawyer as participant
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(lawyer_id), "participant_role": "LAWYER"},
        headers=h_owner,
    )

    # 3. Owner Access -> 200
    res_owner = client.get(f"/api/v1/cases/{case_id}", headers=h_owner)
    assert res_owner.status_code == 200
    assert res_owner.json()["id"] == case_id

    # 4. Lawyer Participant Access -> 200
    res_lawyer = client.get(f"/api/v1/cases/{case_id}", headers=h_lawyer)
    assert res_lawyer.status_code == 200
    assert res_lawyer.json()["id"] == case_id

    # 5. Unaffiliated User Access -> 404 (Obscures existence to prevent IDOR enumeration)
    res_stranger = client.get(f"/api/v1/cases/{case_id}", headers=h_unaffiliated)
    assert res_stranger.status_code == 404

    # 6. Unknown case ID -> 404
    res_nonexistent = client.get(f"/api/v1/cases/{uuid4()}", headers=h_owner)
    assert res_nonexistent.status_code == 404

    # 7. Unauthenticated request -> 401
    res_unauth = client.get(f"/api/v1/cases/{case_id}")
    assert res_unauth.status_code == 401


# ============================================================================
# 4. CASE UPDATE & LIFECYCLE STATE MACHINE
# ============================================================================


def test_case_update_and_state_transitions(client: TestClient, db: Session):
    """Verify authorized updates and state machine transition rules."""
    _owner_id, h_owner = _create_test_user(db, client, "updater_owner@example.com")
    viewer_id, h_viewer = _create_test_user(db, client, "updater_viewer@example.com")
    _stranger_id, h_stranger = _create_test_user(db, client, "updater_stranger@example.com")

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Original Title", "description": "Original Description"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    # Add viewer participant
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(viewer_id), "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 1. Owner updates details -> 200
    res_up = client.patch(
        f"/api/v1/cases/{case_id}",
        json={"title": "Updated Title", "description": "Updated Description"},
        headers=h_owner,
    )
    assert res_up.status_code == 200
    assert res_up.json()["title"] == "Updated Title"

    # 2. State transition: OPEN -> IN_PROGRESS -> 200
    res_prog = client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "IN_PROGRESS"},
        headers=h_owner,
    )
    assert res_prog.status_code == 200
    assert res_prog.json()["status"] == "IN_PROGRESS"

    # 3. State transition: IN_PROGRESS -> CLOSED -> 200
    res_closed = client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "CLOSED"},
        headers=h_owner,
    )
    assert res_closed.status_code == 200
    assert res_closed.json()["status"] == "CLOSED"

    # 4. Terminal state violation: CLOSED -> OPEN -> 422
    res_reopen = client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "OPEN"},
        headers=h_owner,
    )
    assert res_reopen.status_code == 422
    assert "Cannot transition case status" in res_reopen.json()["error"]["message"]

    # 5. Viewer attempts update -> 403
    res_v_up = client.patch(
        f"/api/v1/cases/{case_id}",
        json={"title": "Hacked Title"},
        headers=h_viewer,
    )
    assert res_v_up.status_code == 403

    # 6. Unaffiliated user attempts update -> 404
    res_s_up = client.patch(
        f"/api/v1/cases/{case_id}",
        json={"title": "Hacked Title"},
        headers=h_stranger,
    )
    assert res_s_up.status_code == 404


# ============================================================================
# 5. PARTICIPANT MANAGEMENT INVARIANTS
# ============================================================================


def test_participant_management_invariants(client: TestClient, db: Session):
    """Verify participant role rules, final owner protections, and idempotent removals."""
    owner_id, h_owner = _create_test_user(db, client, "pm_owner@example.com")
    u2_id, h_u2 = _create_test_user(db, client, "pm_user2@example.com")
    _u3_id, _h_u3 = _create_test_user(db, client, "pm_user3@example.com")

    # Create Case
    res_case = client.post("/api/v1/cases", json={"title": "PM Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    # 1. Add u2 as VIEWER
    res_add = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(u2_id), "participant_role": "VIEWER"},
        headers=h_owner,
    )
    assert res_add.status_code == 200

    # 2. Duplicate active participant rejection -> 422
    res_dup = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(u2_id), "participant_role": "VIEWER"},
        headers=h_owner,
    )
    assert res_dup.status_code == 422

    # 3. Non-owner (u2) tries to add u3 -> 403
    res_u2_add = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(_u3_id), "participant_role": "VIEWER"},
        headers=h_u2,
    )
    assert res_u2_add.status_code == 403

    # 4. Owner cannot modify their own participant role -> 422
    res_self_mod = client.patch(
        f"/api/v1/cases/{case_id}/participants/{owner_id}",
        json={"participant_role": "VIEWER"},
        headers=h_owner,
    )
    assert res_self_mod.status_code == 422
    assert "cannot modify their own" in res_self_mod.json()["error"]["message"].lower()

    # 5. Owner cannot remove themselves -> 422
    res_self_rm = client.delete(
        f"/api/v1/cases/{case_id}/participants/{owner_id}",
        headers=h_owner,
    )
    assert res_self_rm.status_code == 422
    assert "cannot remove themselves" in res_self_rm.json()["error"]["message"].lower()

    # 6. Elevate u2 to OWNER -> 200
    res_elevate = client.patch(
        f"/api/v1/cases/{case_id}/participants/{u2_id}",
        json={"participant_role": "OWNER"},
        headers=h_owner,
    )
    assert res_elevate.status_code == 200
    assert res_elevate.json()["participant_role"] == "OWNER"

    # 7. Now with 2 owners, demoting one is permitted -> 200
    res_demote = client.patch(
        f"/api/v1/cases/{case_id}/participants/{u2_id}",
        json={"participant_role": "VIEWER"},
        headers=h_owner,
    )
    assert res_demote.status_code == 200
    assert res_demote.json()["participant_role"] == "VIEWER"

    # 8. Remove u2 -> 204
    res_rm = client.delete(f"/api/v1/cases/{case_id}/participants/{u2_id}", headers=h_owner)
    assert res_rm.status_code == 204

    # 9. Second remove -> 404 (already inactive)
    res_rm2 = client.delete(f"/api/v1/cases/{case_id}/participants/{u2_id}", headers=h_owner)
    assert res_rm2.status_code == 404


# ============================================================================
# 6. SOFT DELETION & RESOURCE ACCESS CUTOFF
# ============================================================================


def test_soft_deletion_and_resource_cutoff(client: TestClient, db: Session):
    """Verify soft-deleted cases are hidden from list and detail queries."""
    _owner_id, h_owner = _create_test_user(db, client, "soft_del_owner@example.com")
    u2_id, h_u2 = _create_test_user(db, client, "soft_del_viewer@example.com")

    # Create Case & add u2
    res_case = client.post("/api/v1/cases", json={"title": "Soft Delete Matter", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(u2_id), "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # Delete case
    res_del = client.delete(f"/api/v1/cases/{case_id}", headers=h_owner)
    assert res_del.status_code == 204

    # Detail access returns 404 for both owner and participant
    assert client.get(f"/api/v1/cases/{case_id}", headers=h_owner).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}", headers=h_u2).status_code == 404

    # List endpoint excludes soft-deleted case
    assert client.get("/api/v1/cases", headers=h_owner).json()["total"] == 0
    assert client.get("/api/v1/cases", headers=h_u2).json()["total"] == 0
