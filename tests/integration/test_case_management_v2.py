from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import LawyerProfile


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
# 1. CASE LIFECYCLE & STATE MACHINE TRANSITIONS
# ============================================================================


def test_case_lifecycle_state_machine_and_timeline(client: TestClient):
    _u_id, h_owner = _setup_user(client, "lifecycle_owner@test.com")

    # 1. Create Case -> OPEN
    res_create = client.post(
        "/api/v1/cases",
        json={"title": "Lifecycle Matter", "description": "Testing lifecycle"},
        headers=h_owner,
    )
    assert res_create.status_code == 201
    case_id = res_create.json()["id"]
    assert res_create.json()["status"] == "OPEN"

    # 2. OPEN -> IN_PROGRESS (Allowed)
    res_prog = client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "IN_PROGRESS"},
        headers=h_owner,
    )
    assert res_prog.status_code == 200
    assert res_prog.json()["status"] == "IN_PROGRESS"

    # 3. IN_PROGRESS -> CLOSED (Allowed)
    res_closed = client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "CLOSED"},
        headers=h_owner,
    )
    assert res_closed.status_code == 200
    assert res_closed.json()["status"] == "CLOSED"

    # 4. CLOSED -> OPEN (Forbidden terminal state -> 422)
    res_reopen = client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "OPEN"},
        headers=h_owner,
    )
    assert res_reopen.status_code == 422
    assert "Cannot transition case status" in res_reopen.json()["error"]["message"]

    # 5. CLOSED -> CANCELLED (Forbidden -> 422)
    res_cancel = client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "CANCELLED"},
        headers=h_owner,
    )
    assert res_cancel.status_code == 422

    # Verify Timeline Events for Status Changes
    res_timeline = client.get(f"/api/v1/cases/{case_id}/timeline", headers=h_owner)
    assert res_timeline.status_code == 200
    events = res_timeline.json()["items"]
    status_events = [e for e in events if e["event_type"] == "STATUS_CHANGED"]
    assert len(status_events) == 2
    assert status_events[0]["event_metadata"]["to_status"] == "CLOSED"
    assert status_events[1]["event_metadata"]["to_status"] == "IN_PROGRESS"


# ============================================================================
# 2. CASE SEARCH & DATABASE-LEVEL FILTERING
# ============================================================================


def test_case_search_and_filtering(client: TestClient):
    _u_id, h_user = _setup_user(client, "search_user@test.com")

    # Create multiple distinct cases
    res1 = client.post(
        "/api/v1/cases",
        json={
            "title": "Commercial Lease Dispute",
            "description": "Tenant breaching lease clause 4",
        },
        headers=h_user,
    )
    c1_id = res1.json()["id"]

    res2 = client.post(
        "/api/v1/cases",
        json={
            "title": "Intellectual Property Trademark",
            "description": "Infringement of brand mark",
        },
        headers=h_user,
    )
    c2_id = res2.json()["id"]

    # Transition case 2 to IN_PROGRESS
    client.patch(
        f"/api/v1/cases/{c2_id}", json={"status": "IN_PROGRESS"}, headers=h_user
    )

    # 1. Filter by status=OPEN
    res_open = client.get("/api/v1/cases?status=OPEN", headers=h_user)
    assert res_open.status_code == 200
    open_items = res_open.json()["items"]
    assert len(open_items) == 1
    assert open_items[0]["id"] == c1_id

    # 2. Filter by status=IN_PROGRESS
    res_prog = client.get("/api/v1/cases?status=IN_PROGRESS", headers=h_user)
    assert res_prog.status_code == 200
    prog_items = res_prog.json()["items"]
    assert len(prog_items) == 1
    assert prog_items[0]["id"] == c2_id

    # 3. Search by title substring ("Trademark")
    res_search1 = client.get("/api/v1/cases?search=trademark", headers=h_user)
    assert res_search1.status_code == 200
    assert len(res_search1.json()["items"]) == 1
    assert res_search1.json()["items"][0]["id"] == c2_id

    # 4. Search by description substring ("lease clause")
    res_search2 = client.get("/api/v1/cases?search=lease%20clause", headers=h_user)
    assert res_search2.status_code == 200
    assert len(res_search2.json()["items"]) == 1
    assert res_search2.json()["items"][0]["id"] == c1_id

    # 5. Search with no matches
    res_none = client.get("/api/v1/cases?search=nonexistentterm123", headers=h_user)
    assert res_none.status_code == 200
    assert len(res_none.json()["items"]) == 0


# ============================================================================
# 3. PARTICIPANT SAFEGUARDS & LAWYER ASSIGNMENT
# ============================================================================


def test_participant_safeguards_and_lawyer_validation(client: TestClient, db: Session):
    owner1_id, h_owner1 = _setup_user(client, "guard_owner1@test.com")
    owner2_id, _h_owner2 = _setup_user(client, "guard_owner2@test.com")
    client_regular_id, _h_reg = _setup_user(
        client, "guard_regular@test.com", role="CLIENT"
    )
    lawyer_id, _h_lawyer = _setup_user(client, "guard_lawyer@test.com", role="LAWYER")

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Participant Case", "description": "D"},
        headers=h_owner1,
    )
    case_id = res_case.json()["id"]

    # 1. Add valid Lawyer participant
    res_add_l = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_owner1,
    )
    assert res_add_l.status_code == 200

    # 2. Try adding regular client as LAWYER participant -> Rejected (422)
    res_fake_l = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": client_regular_id, "participant_role": "LAWYER"},
        headers=h_owner1,
    )
    assert res_fake_l.status_code == 422
    assert "Only users with the LAWYER role" in res_fake_l.json()["error"]["message"]

    # 3. Add second OWNER participant
    res_add_o2 = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": owner2_id, "participant_role": "OWNER"},
        headers=h_owner1,
    )
    assert res_add_o2.status_code == 200

    # 4. Remove second owner (Allowed because owner 1 remains)
    res_rm_o2 = client.delete(
        f"/api/v1/cases/{case_id}/participants/{owner2_id}",
        headers=h_owner1,
    )
    assert res_rm_o2.status_code == 204

    # 5. Reactivate second owner as VIEWER
    res_reactivate = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": owner2_id, "participant_role": "VIEWER"},
        headers=h_owner1,
    )
    assert res_reactivate.status_code == 200
    assert res_reactivate.json()["participant_role"] == "VIEWER"
    assert res_reactivate.json()["status"] == "ACTIVE"

    # 6. Try demoting the ONLY remaining OWNER -> Rejected (422)
    res_demote_last = client.patch(
        f"/api/v1/cases/{case_id}/participants/{owner1_id}",
        json={"participant_role": "VIEWER"},
        headers=h_owner1,
    )
    assert res_demote_last.status_code == 422


# ============================================================================
# 4. CASE TASKS SUBSYSTEM & PERMISSIONS
# ============================================================================


def test_case_tasks_full_lifecycle_and_security(client: TestClient):
    owner_id, h_owner = _setup_user(client, "task_owner_v2@test.com")
    lawyer_id, h_lawyer = _setup_user(client, "task_lawyer_v2@test.com", role="LAWYER")
    viewer_id, h_viewer = _setup_user(client, "task_viewer_v2@test.com")
    unrelated_id, _h_unrelated = _setup_user(client, "task_unrelated_v2@test.com")

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Tasks Matter", "description": "D"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    # Add Lawyer and Viewer
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": viewer_id, "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 1. Try assigning task to unrelated user outside case -> Rejected (422)
    res_invalid_assign = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={
            "title": "Cross Case Task",
            "owner_user_id": unrelated_id,
            "priority": "HIGH",
        },
        headers=h_owner,
    )
    assert res_invalid_assign.status_code == 422
    assert "active participant" in res_invalid_assign.json()["error"]["message"]

    # 2. Viewer attempts to create task -> Forbidden (403)
    res_viewer_create = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Viewer Task", "priority": "LOW"},
        headers=h_viewer,
    )
    assert res_viewer_create.status_code == 403

    # 3. Owner creates valid task assigned to Lawyer with due date
    due = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    res_task = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={
            "title": "Draft Motion for Summary Judgment",
            "description": "Prepare initial draft by Friday",
            "priority": "HIGH",
            "due_date": due,
            "owner_user_id": lawyer_id,
        },
        headers=h_owner,
    )
    assert res_task.status_code == 201
    task_data = res_task.json()
    task_id = task_data["id"]
    assert task_data["priority"] == "HIGH"
    assert task_data["created_by_user_id"] == owner_id
    assert task_data["owner_user_id"] == lawyer_id
    assert task_data["status"] == "PENDING"
    assert task_data["completed_at"] is None

    # 4. Lawyer updates task to IN_PROGRESS
    res_update1 = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=h_lawyer,
    )
    assert res_update1.status_code == 200
    assert res_update1.json()["status"] == "IN_PROGRESS"

    # 5. Lawyer completes task -> completed_at is automatically set
    res_complete = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"status": "COMPLETED"},
        headers=h_lawyer,
    )
    assert res_complete.status_code == 200
    assert res_complete.json()["status"] == "COMPLETED"
    assert res_complete.json()["completed_at"] is not None

    # 6. Read single task
    res_get_t = client.get(f"/api/v1/cases/{case_id}/tasks/{task_id}", headers=h_viewer)
    assert res_get_t.status_code == 200
    assert res_get_t.json()["title"] == "Draft Motion for Summary Judgment"

    # 7. Owner deletes task
    res_del_t = client.delete(
        f"/api/v1/cases/{case_id}/tasks/{task_id}", headers=h_owner
    )
    assert res_del_t.status_code == 204

    # 8. Deleted task returns 404
    res_get_del = client.get(
        f"/api/v1/cases/{case_id}/tasks/{task_id}", headers=h_owner
    )
    assert res_get_del.status_code == 404


# ============================================================================
# 5. CASE NOTES SUBSYSTEM & PRIVACY BOUNDARIES
# ============================================================================


def test_case_notes_privacy_and_permissions(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "note_owner@test.com")
    _lawyer_id, _h_lawyer = _setup_user(client, "note_lawyer@test.com", role="LAWYER")
    viewer_id, h_viewer = _setup_user(client, "note_viewer@test.com")

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Notes Case", "description": "D"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": viewer_id, "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 1. Viewer attempts to create note -> Forbidden (403)
    res_v_create = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "V Note", "content": "C"},
        headers=h_viewer,
    )
    assert res_v_create.status_code == 403

    # 2. Owner creates Public Note
    res_pub = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={
            "title": "Client Overview",
            "content": "Public matter notes",
            "is_private": False,
        },
        headers=h_owner,
    )
    assert res_pub.status_code == 201
    pub_note_id = res_pub.json()["id"]

    # 3. Owner creates Private Note
    res_priv = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={
            "title": "Private Owner Thoughts",
            "content": "Confidential strategy",
            "is_private": True,
        },
        headers=h_owner,
    )
    assert res_priv.status_code == 201
    priv_note_id = res_priv.json()["id"]

    # 4. Viewer lists notes -> Sees only public note (1 note)
    res_v_list = client.get(f"/api/v1/cases/{case_id}/notes", headers=h_viewer)
    assert res_v_list.status_code == 200
    v_notes = res_v_list.json()["items"]
    assert len(v_notes) == 1
    assert v_notes[0]["id"] == pub_note_id

    # 5. Viewer attempts to access private note by ID -> 404 (Obscured existence)
    res_v_get_priv = client.get(
        f"/api/v1/cases/{case_id}/notes/{priv_note_id}", headers=h_viewer
    )
    assert res_v_get_priv.status_code == 404

    # 6. Owner updates public note
    res_update_n = client.patch(
        f"/api/v1/cases/{case_id}/notes/{pub_note_id}",
        json={"title": "Updated Client Overview"},
        headers=h_owner,
    )
    assert res_update_n.status_code == 200
    assert res_update_n.json()["title"] == "Updated Client Overview"

    # 7. Owner deletes private note
    res_del_n = client.delete(
        f"/api/v1/cases/{case_id}/notes/{priv_note_id}", headers=h_owner
    )
    assert res_del_n.status_code == 204


# ============================================================================
# 6. UNIFIED CASE WORKSPACE AGGREGATION
# ============================================================================


def test_case_workspace_complete_aggregation(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "ws_owner@test.com")
    lawyer_user_id, _h_lawyer = _setup_user(
        client, "ws_lawyer@test.com", role="LAWYER", full_name="Jane Counsel"
    )

    # Update LawyerProfile
    l_prof = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == UUID(lawyer_user_id))
        .first()
    )
    if l_prof:
        l_prof.bio = "Senior Partner"
        l_prof.location = "New Delhi"
        l_prof.consultation_fee = 5000
        db.commit()

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Workspace Comprehensive Case", "description": "Desc"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    # Add Lawyer
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_user_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )

    # Add Task with due date
    due = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Review Contract", "priority": "URGENT", "due_date": due},
        headers=h_owner,
    )

    # Add Note
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Workspace Note", "content": "Sample content"},
        headers=h_owner,
    )

    # Fetch Workspace
    res_ws = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_owner)
    assert res_ws.status_code == 200
    ws = res_ws.json()

    assert ws["case"]["title"] == "Workspace Comprehensive Case"
    assert "UPDATE_CASE" in ws["effective_permissions"]
    assert len(ws["participants"]) == 2
    assert ws["lawyer"] is not None
    assert ws["lawyer"]["full_name"] == "Jane Counsel"
    assert ws["tasks_summary"]["total"] == 1
    assert ws["tasks_summary"]["pending"] == 1
    assert ws["notes_count"] == 1
    assert len(ws["upcoming_deadlines"]) >= 1
    assert ws["upcoming_deadlines"][0]["title"] == "Review Contract"
    assert len(ws["recent_activities"]) >= 2


# ============================================================================
# 7. SECURITY & BOLA/IDOR ACCESS MATRIX
# ============================================================================


def test_security_access_matrix_and_soft_delete(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "sec_owner@test.com")
    _other_id, h_other = _setup_user(client, "sec_other@test.com")
    _lawyer_unassigned, h_l_unassigned = _setup_user(
        client, "sec_l_unassigned@test.com", role="LAWYER"
    )

    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Secure Case", "description": "D"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    # 1. Unrelated user accessing workspace -> 404
    assert (
        client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_other).status_code
        == 404
    )

    # 2. Unassigned lawyer accessing tasks -> 404
    assert (
        client.get(f"/api/v1/cases/{case_id}/tasks", headers=h_l_unassigned).status_code
        == 404
    )

    # 3. Unrelated user accessing notes -> 404
    assert (
        client.get(f"/api/v1/cases/{case_id}/notes", headers=h_other).status_code == 404
    )

    # 4. Soft-delete Case
    res_del = client.delete(f"/api/v1/cases/{case_id}", headers=h_owner)
    assert res_del.status_code == 204

    # 5. Owner accessing deleted case workspace -> 404
    assert (
        client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_owner).status_code
        == 404
    )
    # 6. Owner accessing deleted case tasks -> 404
    assert (
        client.get(f"/api/v1/cases/{case_id}/tasks", headers=h_owner).status_code == 404
    )
    # 7. Owner accessing deleted case notes -> 404
    assert (
        client.get(f"/api/v1/cases/{case_id}/notes", headers=h_owner).status_code == 404
    )
    # 8. Owner accessing deleted case timeline -> 404
    assert (
        client.get(f"/api/v1/cases/{case_id}/timeline", headers=h_owner).status_code
        == 404
    )


# ============================================================================
# 8. CASE NOTES & TASKS REGRESSION & AUTHORIZATION MATRIX
# ============================================================================


def test_case_note_comprehensive_authorization_matrix(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "note_mat_owner@test.com")
    lawyer_id, h_lawyer = _setup_user(client, "note_mat_lawyer@test.com", role="LAWYER")
    viewer_id, h_viewer = _setup_user(client, "note_mat_viewer@test.com")
    _other_id, h_other = _setup_user(client, "note_mat_other@test.com")

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Note Matrix Case", "description": "D"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    # Add Lawyer and Viewer
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": viewer_id, "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 1. Lawyer creates a public note
    res_l_note = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Lawyer Note", "content": "Legal analysis", "is_private": False},
        headers=h_lawyer,
    )
    assert res_l_note.status_code == 201
    l_note_id = res_l_note.json()["id"]

    # 2. Viewer attempts to update lawyer note -> Forbidden (403)
    res_v_up = client.patch(
        f"/api/v1/cases/{case_id}/notes/{l_note_id}",
        json={"title": "Hacked Title"},
        headers=h_viewer,
    )
    assert res_v_up.status_code == 403

    # 3. Viewer attempts to delete lawyer note -> Forbidden (403)
    res_v_del = client.delete(
        f"/api/v1/cases/{case_id}/notes/{l_note_id}",
        headers=h_viewer,
    )
    assert res_v_del.status_code == 403

    # 4. Non-member attempts to update lawyer note -> 404 (BOLA protection)
    res_other_up = client.patch(
        f"/api/v1/cases/{case_id}/notes/{l_note_id}",
        json={"title": "Hacked Title"},
        headers=h_other,
    )
    assert res_other_up.status_code == 404

    # 5. Lawyer author updates their own note -> Success (200)
    res_l_up = client.patch(
        f"/api/v1/cases/{case_id}/notes/{l_note_id}",
        json={"title": "Updated Legal Analysis"},
        headers=h_lawyer,
    )
    assert res_l_up.status_code == 200
    assert res_l_up.json()["title"] == "Updated Legal Analysis"

    # 6. Case owner can also update note -> Success (200)
    res_owner_up = client.patch(
        f"/api/v1/cases/{case_id}/notes/{l_note_id}",
        json={"title": "Owner Reviewed Legal Analysis"},
        headers=h_owner,
    )
    assert res_owner_up.status_code == 200
    assert res_owner_up.json()["title"] == "Owner Reviewed Legal Analysis"

    # 7. Inactive participant cannot update or delete notes
    # Remove lawyer from case
    client.delete(
        f"/api/v1/cases/{case_id}/participants/{lawyer_id}",
        headers=h_owner,
    )
    res_inactive_up = client.patch(
        f"/api/v1/cases/{case_id}/notes/{l_note_id}",
        json={"title": "Post-Removal Edit"},
        headers=h_lawyer,
    )
    assert res_inactive_up.status_code == 404  # authorize_case_access rejects inactive participants


def test_task_assignment_and_ordering_regression(client: TestClient):
    owner_id, h_owner = _setup_user(client, "task_mat_owner@test.com")
    lawyer_id, _h_lawyer = _setup_user(client, "task_mat_lawyer@test.com", role="LAWYER")
    other_id, _h_other = _setup_user(client, "task_mat_other@test.com")

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Task Matrix Case", "description": "D"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )

    # 1. Create task assigned to lawyer
    res_t1 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Task 1", "owner_user_id": lawyer_id},
        headers=h_owner,
    )
    assert res_t1.status_code == 201
    t1_id = res_t1.json()["id"]

    # 2. Try reassigning task to non-participant -> Rejected (422)
    res_reassign_invalid = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"owner_user_id": other_id},
        headers=h_owner,
    )
    assert res_reassign_invalid.status_code == 422
    assert "active participant" in res_reassign_invalid.json()["error"]["message"]

    # 3. Reassign task to owner -> Success (200)
    res_reassign_owner = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"owner_user_id": owner_id},
        headers=h_owner,
    )
    assert res_reassign_owner.status_code == 200
    assert res_reassign_owner.json()["owner_user_id"] == owner_id

    # 4. Unassign task (set owner_user_id to null) -> Success (200)
    res_unassign = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"owner_user_id": None},
        headers=h_owner,
    )
    assert res_unassign.status_code == 200
    assert res_unassign.json()["owner_user_id"] is None

    # 5. Create multiple tasks and verify deterministic descending ordering
    res_t2 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Task 2"},
        headers=h_owner,
    )
    res_t3 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Task 3"},
        headers=h_owner,
    )

    res_list = client.get(f"/api/v1/cases/{case_id}/tasks", headers=h_owner)
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert len(items) == 3
    # Task 3 was created last, should appear first
    assert items[0]["id"] == res_t3.json()["id"]
    assert items[1]["id"] == res_t2.json()["id"]
    assert items[2]["id"] == res_t1.json()["id"]
