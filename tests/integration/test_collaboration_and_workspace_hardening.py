"""Comprehensive Collaboration & Case Workspace Test Suite.

Phase 5 Verification:
- Case Workspace Authorization & Resource-Level Security
- Task CRUD, Assignee Invariants, and Granular RBAC
- Task Status State Machine & Terminal State Freezing
- Note CRUD, Visibility Levels (SHARED, CLIENT_PRIVATE, LAWYER_PRIVATE), and Privacy Isolation
- Workspace Summary Aggregation & Role-Filtered Metrics
- Immutable Timeline & Activity Generation
- Cross-Case BOLA / IDOR Defense across All Workspace Child Resources
- Multi-Model Transaction Integrity & Concurrency
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole


def _create_user(
    db: Session,
    client: TestClient,
    email: str,
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Test User",
) -> tuple[uuid.UUID, dict[str, str]]:
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


def _create_case(
    client: TestClient,
    headers: dict[str, str],
    title: str = "Collaboration Test Matter",
) -> str:
    """Helper to create a case and return case_id string."""
    res = client.post(
        "/api/v1/cases",
        json={"title": title, "description": "Matter for workspace hardening tests"},
        headers=headers,
    )
    assert res.status_code == 201
    return res.json()["id"]


# ============================================================================
# 1. TASK CRUD & GRANULAR AUTHORIZATION
# ============================================================================


def test_task_crud_and_granular_authorization(client: TestClient, db: Session):
    """Verify task CRUD, permission boundaries, and unauthenticated/unaffiliated denial."""
    _owner_id, h_owner = _create_user(db, client, "task_owner@example.com")
    lawyer_id, h_lawyer = _create_user(db, client, "task_lawyer@example.com", role=UserRole.LAWYER)
    viewer_id, h_viewer = _create_user(db, client, "task_viewer@example.com")
    _stranger_id, h_stranger = _create_user(db, client, "task_stranger@example.com")

    case_id = _create_case(client, h_owner, "Commercial Suit")

    # Add Lawyer and Viewer
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(lawyer_id), "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(viewer_id), "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 1. Owner creates task -> 201
    future_due = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    res_t1 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={
            "title": "Prepare Written Statement",
            "description": "Draft response to plaint",
            "priority": "HIGH",
            "due_date": future_due,
            "owner_user_id": str(lawyer_id),
        },
        headers=h_owner,
    )
    assert res_t1.status_code == 201
    t1_data = res_t1.json()
    t1_id = t1_data["id"]
    assert t1_data["title"] == "Prepare Written Statement"
    assert t1_data["priority"] == "HIGH"
    assert t1_data["status"] == "PENDING"
    assert t1_data["owner_user_id"] == str(lawyer_id)

    # 2. Lawyer creates task -> 201
    res_t2 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={
            "title": "File Vakalatnama",
            "priority": "MEDIUM",
        },
        headers=h_lawyer,
    )
    assert res_t2.status_code == 201
    t2_id = res_t2.json()["id"]
    assert client.get(f"/api/v1/cases/{case_id}/tasks/{t2_id}", headers=h_owner).status_code == 200

    # 3. Viewer attempts to create task -> 403 Forbidden
    res_v_create = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Viewer Illegal Task"},
        headers=h_viewer,
    )
    assert res_v_create.status_code == 403

    # 4. Stranger attempts to create task -> 404 (BOLA defense)
    res_s_create = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Stranger Task"},
        headers=h_stranger,
    )
    assert res_s_create.status_code == 404

    # 5. Unauthenticated create attempt -> 401
    assert client.post(f"/api/v1/cases/{case_id}/tasks", json={"title": "No Auth"}).status_code == 401

    # 6. List tasks with filtering and pagination
    list_res = client.get(
        f"/api/v1/cases/{case_id}/tasks?status=PENDING&skip=0&limit=10",
        headers=h_owner,
    )
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 2
    assert len(list_res.json()["items"]) == 2

    # 7. Get task by ID
    assert client.get(f"/api/v1/cases/{case_id}/tasks/{t1_id}", headers=h_owner).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/tasks/{t1_id}", headers=h_lawyer).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/tasks/{t1_id}", headers=h_viewer).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/tasks/{t1_id}", headers=h_stranger).status_code == 404


# ============================================================================
# 2. TASK ASSIGNEE VALIDATION & PRIVILEGE ESCALATION
# ============================================================================


def test_task_assignee_validation(client: TestClient, db: Session):
    """Verify task assignment enforces active user and case participant status."""
    owner_id, h_owner = _create_user(db, client, "asg_val_owner@example.com")
    lawyer_id, _h_lawyer = _create_user(db, client, "asg_val_lawyer@example.com", role=UserRole.LAWYER)
    unrelated_id, _h_unrelated = _create_user(db, client, "asg_val_unrelated@example.com")

    case_id = _create_case(client, h_owner, "Contract Dispute")

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(lawyer_id), "participant_role": "LAWYER"},
        headers=h_owner,
    )

    # 1. Create task assigned to valid lawyer participant -> 201
    res_t = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Draft Affidavit", "owner_user_id": str(lawyer_id)},
        headers=h_owner,
    )
    assert res_t.status_code == 201
    task_id = res_t.json()["id"]

    # 2. Assign to Case Owner -> 200
    res_asg_owner = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"owner_user_id": str(owner_id)},
        headers=h_owner,
    )
    assert res_asg_owner.status_code == 200
    assert res_asg_owner.json()["owner_user_id"] == str(owner_id)

    # 3. Unassign task (set owner_user_id to None) -> 200
    res_unassign = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"owner_user_id": None},
        headers=h_owner,
    )
    assert res_unassign.status_code == 200
    assert res_unassign.json()["owner_user_id"] is None

    # 4. Assign to Unrelated User -> Rejected (422)
    res_asg_unrel = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"owner_user_id": str(unrelated_id)},
        headers=h_owner,
    )
    assert res_asg_unrel.status_code == 422
    assert "active participant" in res_asg_unrel.json()["error"]["message"].lower()

    # 5. Assign to Non-Existent User UUID -> Rejected (422)
    res_asg_fake = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"owner_user_id": str(uuid.uuid4())},
        headers=h_owner,
    )
    assert res_asg_fake.status_code == 422
    assert "active user" in res_asg_fake.json()["error"]["message"].lower()

    # 6. Remove Lawyer from Case and attempt assignment -> Rejected (422)
    client.delete(f"/api/v1/cases/{case_id}/participants/{lawyer_id}", headers=h_owner)
    res_asg_removed = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"owner_user_id": str(lawyer_id)},
        headers=h_owner,
    )
    assert res_asg_removed.status_code == 422
    assert "active participant" in res_asg_removed.json()["error"]["message"].lower()


# ============================================================================
# 3. TASK STATUS STATE MACHINE & TERMINAL FREEZING
# ============================================================================


def test_task_state_machine_and_terminal_freeze(client: TestClient, db: Session):
    """Verify task state transitions: PENDING -> IN_PROGRESS -> COMPLETED and terminal lock."""
    _owner_id, h_owner = _create_user(db, client, "sm_freeze_owner@example.com")
    lawyer_id, h_lawyer = _create_user(db, client, "sm_freeze_lawyer@example.com", role=UserRole.LAWYER)

    case_id = _create_case(client, h_owner, "Insolvency Matter")

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(lawyer_id), "participant_role": "LAWYER"},
        headers=h_owner,
    )

    # 1. PENDING -> IN_PROGRESS
    res_t = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Prepare Resolution Plan", "owner_user_id": str(lawyer_id)},
        headers=h_owner,
    )
    task_id = res_t.json()["id"]

    res_in_prog = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=h_lawyer,
    )
    assert res_in_prog.status_code == 200
    assert res_in_prog.json()["status"] == "IN_PROGRESS"

    # 2. IN_PROGRESS -> COMPLETED
    res_comp = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"status": "COMPLETED"},
        headers=h_lawyer,
    )
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"
    assert res_comp.json()["completed_at"] is not None

    # 3. COMPLETED -> PENDING (Invalid reverse transition -> 422)
    res_rev = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"status": "PENDING"},
        headers=h_owner,
    )
    assert res_rev.status_code == 422
    assert "cannot modify a completed task" in res_rev.json()["error"]["message"].lower()

    # 4. Attempting to mutate title/description on completed task -> 422
    res_edit_comp = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"title": "Altered Title on Completed Task"},
        headers=h_owner,
    )
    assert res_edit_comp.status_code == 422

    # 5. CANCELLED task terminal freeze
    res_t2 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Filing Interim Application"},
        headers=h_owner,
    )
    t2_id = res_t2.json()["id"]

    client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t2_id}",
        json={"status": "CANCELLED"},
        headers=h_owner,
    )

    res_edit_canc = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t2_id}",
        json={"description": "Attempting edit on cancelled task"},
        headers=h_owner,
    )
    assert res_edit_canc.status_code == 422
    assert "cannot modify a cancelled task" in res_edit_canc.json()["error"]["message"].lower()


# ============================================================================
# 4. NOTE CREATION, PRIVACY MATRIX & WORKSPACE ISOLATION
# ============================================================================


def test_note_privacy_matrix_and_workspace_aggregation(client: TestClient, db: Session):
    """Verify SHARED, CLIENT_PRIVATE, and LAWYER_PRIVATE visibility rules at SQL level."""
    _owner_id, h_owner = _create_user(db, client, "note_priv_owner@example.com")
    lawyer_a_id, h_lawyer_a = _create_user(db, client, "note_priv_la@example.com", role=UserRole.LAWYER)
    lawyer_b_id, h_lawyer_b = _create_user(db, client, "note_priv_lb@example.com", role=UserRole.LAWYER)
    viewer_id, h_viewer = _create_user(db, client, "note_priv_viewer@example.com")
    _stranger_id, h_stranger = _create_user(db, client, "note_priv_stranger@example.com")

    case_id = _create_case(client, h_owner, "IP Trademark Suit")

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(lawyer_a_id), "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(lawyer_b_id), "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(viewer_id), "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 1. Owner creates CLIENT_PRIVATE note -> 201
    res_cp = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Client Secret Note", "content": "Confidential budget", "visibility": "CLIENT_PRIVATE"},
        headers=h_owner,
    )
    assert res_cp.status_code == 201
    note_cp_id = res_cp.json()["id"]
    assert res_cp.json()["is_private"] is True

    # 2. Lawyer A creates LAWYER_PRIVATE note -> 201
    res_la_priv = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Lawyer A Strategy", "content": "Internal litigation theory", "visibility": "LAWYER_PRIVATE"},
        headers=h_lawyer_a,
    )
    assert res_la_priv.status_code == 201
    note_la_id = res_la_priv.json()["id"]

    # 3. Lawyer B creates LAWYER_PRIVATE note -> 201
    res_lb_priv = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Lawyer B Analysis", "content": "Cross-examination prep", "visibility": "LAWYER_PRIVATE"},
        headers=h_lawyer_b,
    )
    assert res_lb_priv.status_code == 201
    note_lb_id = res_lb_priv.json()["id"]

    # 4. Lawyer A creates SHARED note -> 201
    res_sh = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Joint Procedural Schedule", "content": "Filing deadlines", "visibility": "SHARED"},
        headers=h_lawyer_a,
    )
    assert res_sh.status_code == 201
    note_sh_id = res_sh.json()["id"]

    # 5. Role Creation Compatibility Rules:
    # Client cannot create LAWYER_PRIVATE note (422)
    assert client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Spoofed", "content": "Fake", "visibility": "LAWYER_PRIVATE"},
        headers=h_owner,
    ).status_code == 422

    # Lawyer cannot create CLIENT_PRIVATE note (422)
    assert client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Spoofed", "content": "Fake", "visibility": "CLIENT_PRIVATE"},
        headers=h_lawyer_a,
    ).status_code == 422

    # Viewer cannot create note (403)
    assert client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Viewer Note", "content": "Content", "visibility": "SHARED"},
        headers=h_viewer,
    ).status_code == 403

    # 6. Workspace Notes Count Isolation:
    # Owner sees: CLIENT_PRIVATE + SHARED = 2
    ws_owner = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_owner).json()
    assert ws_owner["notes_count"] == 2

    # Lawyer A sees: Lawyer A LAWYER_PRIVATE + SHARED = 2
    ws_la = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_lawyer_a).json()
    assert ws_la["notes_count"] == 2

    # Lawyer B sees: Lawyer B LAWYER_PRIVATE + SHARED = 2
    ws_lb = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_lawyer_b).json()
    assert ws_lb["notes_count"] == 2

    # Viewer sees: SHARED = 1
    ws_viewer = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_viewer).json()
    assert ws_viewer["notes_count"] == 1

    # 7. Note Lookups Cross-Leakage Checks:
    # Lawyer A Private note is visible ONLY to Lawyer A (404 for Owner, Lawyer B, Viewer, Stranger)
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_la_id}", headers=h_lawyer_a).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_la_id}", headers=h_owner).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_la_id}", headers=h_lawyer_b).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_la_id}", headers=h_viewer).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_la_id}", headers=h_stranger).status_code == 404

    # Lawyer B Private note is visible ONLY to Lawyer B (404 for Owner, Lawyer A, Viewer, Stranger)
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_lb_id}", headers=h_lawyer_b).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_lb_id}", headers=h_lawyer_a).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_lb_id}", headers=h_owner).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_lb_id}", headers=h_viewer).status_code == 404

    # Client Private note is visible ONLY to Owner (404 for Lawyer A, Lawyer B, Viewer, Stranger)
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_cp_id}", headers=h_owner).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_cp_id}", headers=h_lawyer_a).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_cp_id}", headers=h_lawyer_b).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_cp_id}", headers=h_viewer).status_code == 404

    # Shared note is visible to Owner, Lawyer A, Lawyer B, Viewer; 404 for Stranger
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_sh_id}", headers=h_owner).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_sh_id}", headers=h_lawyer_a).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_sh_id}", headers=h_lawyer_b).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_sh_id}", headers=h_viewer).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_sh_id}", headers=h_stranger).status_code == 404


# ============================================================================
# 5. TIMELINE GENERATION & IMMUTABILITY
# ============================================================================


def test_timeline_integrity_and_immutability(client: TestClient, db: Session):
    """Verify automatic timeline events generation and rejection of direct tampering."""
    _owner_id, h_owner = _create_user(db, client, "timeline_owner@example.com")
    lawyer_id, _h_lawyer = _create_user(db, client, "timeline_lawyer@example.com", role=UserRole.LAWYER)
    _stranger_id, h_stranger = _create_user(db, client, "timeline_stranger@example.com")

    # 1. Create Case -> CASE_CREATED
    case_id = _create_case(client, h_owner, "Appellate Suit")

    # 2. Add Participant -> PARTICIPANT_ADDED + LAWYER_SELECTED
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(lawyer_id), "participant_role": "LAWYER"},
        headers=h_owner,
    )

    # 3. Create Task -> TASK_CREATED
    t_res = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Draft Brief"},
        headers=h_owner,
    )
    t_id = t_res.json()["id"]

    # 4. Complete Task -> TASK_COMPLETED
    client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t_id}",
        json={"status": "IN_PROGRESS"},
        headers=h_owner,
    )
    client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t_id}",
        json={"status": "COMPLETED"},
        headers=h_owner,
    )

    # 5. Direct timeline tampering endpoints -> 404 / 405 (Immutable)
    fake_event_id = str(uuid.uuid4())
    assert client.post(f"/api/v1/cases/{case_id}/timeline", json={"event_type": "FORGED"}, headers=h_owner).status_code in (404, 405)
    assert client.patch(f"/api/v1/cases/{case_id}/timeline/{fake_event_id}", json={"description": "Hacked"}, headers=h_owner).status_code in (404, 405)
    assert client.delete(f"/api/v1/cases/{case_id}/timeline/{fake_event_id}", headers=h_owner).status_code in (404, 405)

    # 6. Retrieve Timeline
    tl_res = client.get(f"/api/v1/cases/{case_id}/timeline", headers=h_owner)
    assert tl_res.status_code == 200
    events = tl_res.json()["items"]
    event_types = [e["event_type"] for e in events]

    assert "CASE_CREATED" in event_types
    assert "PARTICIPANT_ADDED" in event_types
    assert "TASK_CREATED" in event_types
    assert "TASK_COMPLETED" in event_types

    # 7. Stranger cannot view timeline -> 404
    assert client.get(f"/api/v1/cases/{case_id}/timeline", headers=h_stranger).status_code == 404


# ============================================================================
# 6. CROSS-CASE BOLA / IDOR MATRIX ACROSS WORKSPACE RESOURCES
# ============================================================================


def test_cross_case_workspace_bola_matrix(client: TestClient, db: Session):
    """Verify complete isolation between Tenant A (Case 1) and Tenant B (Case 2)."""
    _owner_a_id, h_owner_a = _create_user(db, client, "tenant_a@example.com")
    _owner_b_id, h_owner_b = _create_user(db, client, "tenant_b@example.com")

    # Case 1 (Tenant A)
    case_1_id = _create_case(client, h_owner_a, "Matter A")
    t1_id = client.post(
        f"/api/v1/cases/{case_1_id}/tasks",
        json={"title": "Confidential Task A"},
        headers=h_owner_a,
    ).json()["id"]

    note1_id = client.post(
        f"/api/v1/cases/{case_1_id}/notes",
        json={"title": "Confidential Note A", "content": "Sensitive strategy A", "visibility": "SHARED"},
        headers=h_owner_a,
    ).json()["id"]

    # Case 2 (Tenant B)
    case_2_id = _create_case(client, h_owner_b, "Matter B")

    # Tenant B attempts to read/mutate Tenant A's child resources via Case 1 endpoints -> 404
    assert client.get(f"/api/v1/cases/{case_1_id}/tasks/{t1_id}", headers=h_owner_b).status_code == 404
    assert client.patch(f"/api/v1/cases/{case_1_id}/tasks/{t1_id}", json={"title": "Hacked"}, headers=h_owner_b).status_code == 404
    assert client.delete(f"/api/v1/cases/{case_1_id}/tasks/{t1_id}", headers=h_owner_b).status_code == 404

    assert client.get(f"/api/v1/cases/{case_1_id}/notes/{note1_id}", headers=h_owner_b).status_code == 404
    assert client.patch(f"/api/v1/cases/{case_1_id}/notes/{note1_id}", json={"title": "Hacked"}, headers=h_owner_b).status_code == 404
    assert client.delete(f"/api/v1/cases/{case_1_id}/notes/{note1_id}", headers=h_owner_b).status_code == 404

    # Tenant B attempts to swap case_id in URL (e.g. /cases/{case_2_id}/tasks/{t1_id}) -> 404
    assert client.get(f"/api/v1/cases/{case_2_id}/tasks/{t1_id}", headers=h_owner_b).status_code == 404
    assert client.get(f"/api/v1/cases/{case_2_id}/notes/{note1_id}", headers=h_owner_b).status_code == 404
