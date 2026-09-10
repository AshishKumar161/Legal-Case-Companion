import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def _setup_user(
    client: TestClient,
    email: str,
    password: str = "SecurePass123!",
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


def test_workspace_bola_and_access_isolation(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "ws_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(
        client, "ws_lawyer@test.com", role="LAWYER", full_name="Adv. Banerjee"
    )
    viewer_id, h_viewer = _setup_user(client, "ws_viewer@test.com", role="CLIENT")
    _unrelated_id, h_unrelated = _setup_user(
        client, "ws_unrel@test.com", role="CLIENT"
    )

    # 1. Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Corporate Dispute", "description": "Arbitration proceedings"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

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

    # 2. Active Participants can access workspace
    res_ws_owner = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_owner)
    assert res_ws_owner.status_code == 200
    assert res_ws_owner.json()["case"]["id"] == case_id

    res_ws_lawyer = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_lawyer)
    assert res_ws_lawyer.status_code == 200
    assert res_ws_lawyer.json()["case"]["id"] == case_id

    res_ws_viewer = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_viewer)
    assert res_ws_viewer.status_code == 200
    assert res_ws_viewer.json()["case"]["id"] == case_id

    # 3. Unassigned Client receives 404 (Obscured)
    res_ws_unrel = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_unrelated)
    assert res_ws_unrel.status_code == 404

    # 4. Remove Lawyer -> Immediate 404 access cutoff
    client.delete(f"/api/v1/cases/{case_id}/participants/{lawyer_id}", headers=h_owner)
    res_ws_revoked = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_lawyer)
    assert res_ws_revoked.status_code == 404

    # 5. Non-existent Case UUID -> 404
    fake_uuid = str(uuid.uuid4())
    assert client.get(f"/api/v1/cases/{fake_uuid}/workspace", headers=h_owner).status_code == 404


def test_workspace_effective_permissions_matrix(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "perm_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(
        client, "perm_lawyer@test.com", role="LAWYER", full_name="Adv. Sharma"
    )
    viewer_id, h_viewer = _setup_user(client, "perm_viewer@test.com", role="CLIENT")

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Permission Matrix Case", "description": "Testing permissions"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

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

    # 1. Verify Case Owner Permissions
    ws_owner = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_owner).json()
    owner_perms = set(ws_owner["effective_permissions"])
    assert "UPDATE_CASE" in owner_perms
    assert "DELETE_CASE" in owner_perms
    assert "MANAGE_PARTICIPANTS" in owner_perms
    assert "UPLOAD_DOCUMENT" in owner_perms
    assert "DELETE_DOCUMENT" in owner_perms
    assert "CREATE_TASK" in owner_perms
    assert "UPDATE_TASK" in owner_perms
    assert "DELETE_TASK" in owner_perms
    assert "CREATE_NOTE" in owner_perms
    assert "VIEW_DOCUMENTS" in owner_perms
    assert "VIEW_TASKS" in owner_perms
    assert "VIEW_NOTES" in owner_perms
    assert "VIEW_TIMELINE" in owner_perms

    # 2. Verify Lawyer Permissions
    ws_lawyer = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_lawyer).json()
    lawyer_perms = set(ws_lawyer["effective_permissions"])
    assert "UPLOAD_DOCUMENT" in lawyer_perms
    assert "CREATE_TASK" in lawyer_perms
    assert "UPDATE_TASK" in lawyer_perms
    assert "CREATE_NOTE" in lawyer_perms
    assert "UPDATE_NOTE" in lawyer_perms
    assert "VIEW_DOCUMENTS" in lawyer_perms
    assert "VIEW_TASKS" in lawyer_perms
    assert "VIEW_NOTES" in lawyer_perms
    assert "VIEW_TIMELINE" in lawyer_perms
    # Lawyer must NOT have Owner-only permissions
    assert "DELETE_CASE" not in lawyer_perms
    assert "MANAGE_PARTICIPANTS" not in lawyer_perms
    assert "DELETE_TASK" not in lawyer_perms

    # 3. Verify Viewer Permissions
    ws_viewer = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_viewer).json()
    viewer_perms = set(ws_viewer["effective_permissions"])
    assert viewer_perms == {"VIEW_DOCUMENTS", "VIEW_TASKS", "VIEW_NOTES", "VIEW_TIMELINE"}


def test_workspace_note_and_document_aggregation_privacy(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "agg_owner@test.com", role="CLIENT")
    lawyer_a_id, h_lawyer_a = _setup_user(
        client, "agg_la@test.com", role="LAWYER", full_name="Adv. Lawyer A"
    )
    lawyer_b_id, h_lawyer_b = _setup_user(
        client, "agg_lb@test.com", role="LAWYER", full_name="Adv. Lawyer B"
    )
    viewer_id, h_viewer = _setup_user(client, "agg_view@test.com", role="CLIENT")

    # Create Case & Participants
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Multi-Counsel Arbitration", "description": "High stakes litigation"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    for uid in (lawyer_a_id, lawyer_b_id):
        client.post(
            f"/api/v1/cases/{case_id}/participants",
            json={"user_id": uid, "participant_role": "LAWYER"},
            headers=h_owner,
        )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": viewer_id, "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 1. Create Notes with different visibilities:
    # Note 1: Client Private (created by owner)
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Client Private Strategy", "content": "Confidential budget", "visibility": "CLIENT_PRIVATE"},
        headers=h_owner,
    )
    # Note 2: Lawyer A Private (created by Lawyer A)
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Lawyer A Draft Opinions", "content": "Confidential assessment", "visibility": "LAWYER_PRIVATE"},
        headers=h_lawyer_a,
    )
    # Note 3: Lawyer B Private (created by Lawyer B)
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Lawyer B Case Notes", "content": "Confidential research", "visibility": "LAWYER_PRIVATE"},
        headers=h_lawyer_b,
    )
    # Note 4: Shared Note (created by owner)
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Joint Procedural Schedule", "content": "Upcoming hearing dates", "visibility": "SHARED"},
        headers=h_owner,
    )

    # Verify Note Counts in Workspace:
    # Owner should see 2 notes (Client Private + Shared)
    ws_owner = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_owner).json()
    assert ws_owner["notes_count"] == 2
    res_notes_owner = client.get(f"/api/v1/cases/{case_id}/notes", headers=h_owner).json()
    assert res_notes_owner["total"] == 2

    # Lawyer A should see 2 notes (Lawyer A Private + Shared)
    ws_la = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_lawyer_a).json()
    assert ws_la["notes_count"] == 2
    res_notes_la = client.get(f"/api/v1/cases/{case_id}/notes", headers=h_lawyer_a).json()
    assert res_notes_la["total"] == 2

    # Lawyer B should see 2 notes (Lawyer B Private + Shared)
    ws_lb = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_lawyer_b).json()
    assert ws_lb["notes_count"] == 2
    res_notes_lb = client.get(f"/api/v1/cases/{case_id}/notes", headers=h_lawyer_b).json()
    assert res_notes_lb["total"] == 2

    # Viewer should see 1 note (Shared only)
    ws_viewer = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_viewer).json()
    assert ws_viewer["notes_count"] == 1
    res_notes_viewer = client.get(f"/api/v1/cases/{case_id}/notes", headers=h_viewer).json()
    assert res_notes_viewer["total"] == 1

    # 2. Upload Documents & verify document_count
    res_doc1 = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "pleading.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=h_owner,
    )
    doc1_id = res_doc1.json()["document"]["id"]

    res_doc2 = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "exhibit.pdf", "mime_type": "application/pdf", "file_size": 2048},
        headers=h_lawyer_a,
    )
    res_doc2.json()["document"]["id"]

    ws_after_docs = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_owner).json()
    assert ws_after_docs["document_count"] == 2

    # Delete 1 Document -> document_count decrements to 1
    client.delete(f"/api/v1/documents/{doc1_id}", headers=h_owner)
    ws_after_del = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_owner).json()
    assert ws_after_del["document_count"] == 1


def test_workspace_tasks_summary_and_deadlines_aggregation(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "task_ws_owner@test.com", role="CLIENT")
    lawyer_id, _h_lawyer = _setup_user(
        client, "task_ws_lawyer@test.com", role="LAWYER", full_name="Adv. Sen"
    )

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Task Aggregation Case", "description": "Testing tasks summary"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )

    now = datetime.now(UTC)
    future_1 = (now + timedelta(days=2)).isoformat()
    future_2 = (now + timedelta(days=5)).isoformat()
    future_3 = (now + timedelta(days=10)).isoformat()

    # Task 1: Pending (Due in 2 days)
    res_t1 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Draft Written Statement", "due_date": future_1, "priority": "HIGH"},
        headers=h_owner,
    )
    t1_id = res_t1.json()["id"]

    # Task 2: In Progress (Due in 5 days)
    res_t2 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Compile Evidence Annexures", "due_date": future_2, "priority": "MEDIUM"},
        headers=h_owner,
    )
    t2_id = res_t2.json()["id"]
    client.patch(f"/api/v1/cases/{case_id}/tasks/{t2_id}", json={"status": "IN_PROGRESS"}, headers=h_owner)

    # Task 3: Completed (Due in 10 days) -> Should NOT appear in upcoming deadlines
    res_t3 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Initial Client Consultation", "due_date": future_3, "priority": "LOW"},
        headers=h_owner,
    )
    t3_id = res_t3.json()["id"]
    client.patch(f"/api/v1/cases/{case_id}/tasks/{t3_id}", json={"status": "COMPLETED"}, headers=h_owner)

    # Task 4: Cancelled Task
    res_t4 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Obsolete Research", "priority": "LOW"},
        headers=h_owner,
    )
    t4_id = res_t4.json()["id"]
    client.patch(f"/api/v1/cases/{case_id}/tasks/{t4_id}", json={"status": "CANCELLED"}, headers=h_owner)

    # Fetch Workspace
    ws = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_owner).json()

    # 1. Verify Tasks Summary Breakdown
    summary = ws["tasks_summary"]
    assert summary["total"] == 4
    assert summary["pending"] == 1
    assert summary["in_progress"] == 1
    assert summary["completed"] == 1
    assert summary["cancelled"] == 1

    # 2. Verify Upcoming Deadlines Aggregation
    deadlines = ws["upcoming_deadlines"]
    task_deadlines = [d for d in deadlines if d["type"] == "TASK_DUE"]
    assert len(task_deadlines) == 2
    # Ordered ascending by due_date: Task 1 (2 days) then Task 2 (5 days)
    assert task_deadlines[0]["id"] == t1_id
    assert task_deadlines[1]["id"] == t2_id
