import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


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


def test_timeline_direct_forgery_prevention(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "t_forgery_owner@test.com", role="CLIENT")

    # 1. Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Civil Suit", "description": "Property dispute"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    # 2. Attempt to POST arbitrary timeline event -> Method Not Allowed / Not Found (404/405)
    res_post = client.post(
        f"/api/v1/cases/{case_id}/timeline",
        json={
            "event_type": "LAWYER_CASE_ACCESS_GRANTED",
            "description": "Injected timeline event",
            "actor_user_id": str(uuid.uuid4()),
        },
        headers=h_owner,
    )
    assert res_post.status_code in (404, 405)

    # 3. Attempt to PUT / PATCH / DELETE timeline event -> 404/405
    fake_event_id = str(uuid.uuid4())
    res_put = client.put(
        f"/api/v1/cases/{case_id}/timeline/{fake_event_id}",
        json={"description": "Tampered description"},
        headers=h_owner,
    )
    assert res_put.status_code in (404, 405)

    res_patch = client.patch(
        f"/api/v1/cases/{case_id}/timeline/{fake_event_id}",
        json={"description": "Tampered description"},
        headers=h_owner,
    )
    assert res_patch.status_code in (404, 405)

    res_delete = client.delete(
        f"/api/v1/cases/{case_id}/timeline/{fake_event_id}",
        headers=h_owner,
    )
    assert res_delete.status_code in (404, 405)


def test_timeline_automatic_domain_event_generation_and_actor_integrity(
    client: TestClient, db: Session
):
    owner_id, h_owner = _setup_user(client, "t_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(
        client, "t_lawyer@test.com", role="LAWYER", full_name="Adv. Mukherjee"
    )
    viewer_id, _h_viewer = _setup_user(client, "t_viewer@test.com", role="CLIENT")

    # 1. Create Case -> CASE_CREATED (Actor: owner)
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "High Court Appeal", "description": "Appellate proceedings"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    # 2. Add Lawyer -> PARTICIPANT_ADDED + LAWYER_SELECTED (Actor: owner)
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )

    # 3. Add Viewer -> PARTICIPANT_ADDED (Actor: owner)
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": viewer_id, "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 4. Upload Document -> DOCUMENT_UPLOADED (Actor: lawyer)
    res_doc = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "appeal_memo.pdf", "mime_type": "application/pdf", "file_size": 2048},
        headers=h_lawyer,
    )
    doc_id = res_doc.json()["document"]["id"]

    # 5. Create Task -> TASK_CREATED (Actor: owner)
    res_task = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "File Vakalatnama", "owner_user_id": lawyer_id},
        headers=h_owner,
    )
    task_id = res_task.json()["id"]

    # 6. Complete Task -> TASK_UPDATED + TASK_COMPLETED (Actor: lawyer)
    client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"status": "COMPLETED"},
        headers=h_lawyer,
    )

    # 7. Delete Document -> DOCUMENT_DELETED (Actor: lawyer)
    res_del_doc = client.delete(f"/api/v1/documents/{doc_id}", headers=h_lawyer)
    assert res_del_doc.status_code == 204

    # 8. Update Case Status -> CASE_STATUS_CHANGED + CASE_UPDATED (Actor: owner)
    client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "IN_PROGRESS"},
        headers=h_owner,
    )

    # Fetch Timeline
    res_timeline = client.get(f"/api/v1/cases/{case_id}/timeline", headers=h_owner)
    assert res_timeline.status_code == 200
    events = res_timeline.json()["items"]
    event_types = [e["event_type"] for e in events]

    # Verify event generation
    assert "CASE_CREATED" in event_types
    assert "PARTICIPANT_ADDED" in event_types
    assert "LAWYER_SELECTED" in event_types
    assert "DOCUMENT_UPLOADED" in event_types
    assert "DOCUMENT_DELETED" in event_types
    assert "TASK_CREATED" in event_types
    assert "TASK_COMPLETED" in event_types
    assert "STATUS_CHANGED" in event_types

    # Verify Actor Integrity:
    # Document upload actor must be Lawyer
    doc_upload_events = [e for e in events if e["event_type"] == "DOCUMENT_UPLOADED"]
    assert len(doc_upload_events) == 1
    assert doc_upload_events[0]["actor_user_id"] == lawyer_id

    # Case creation actor must be Owner
    case_create_events = [e for e in events if e["event_type"] == "CASE_CREATED"]
    assert len(case_create_events) == 1
    assert case_create_events[0]["actor_user_id"] == owner_id

    # Task completion actor must be Lawyer
    task_comp_events = [e for e in events if e["event_type"] == "TASK_COMPLETED"]
    assert len(task_comp_events) == 1
    assert task_comp_events[0]["actor_user_id"] == lawyer_id


def test_timeline_deterministic_ordering_and_workspace_aggregation(
    client: TestClient,
):
    _owner_id, h_owner = _setup_user(client, "t_order_owner@test.com", role="CLIENT")

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Rapid Ordering Case", "description": "Testing timestamp order"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    # Generate 5 tasks rapidly in succession
    created_task_ids = []
    for i in range(5):
        res_t = client.post(
            f"/api/v1/cases/{case_id}/tasks",
            json={"title": f"Sequential Task {i+1}"},
            headers=h_owner,
        )
        assert res_t.status_code == 201
        created_task_ids.append(res_t.json()["id"])

    # Fetch Timeline
    res_timeline = client.get(
        f"/api/v1/cases/{case_id}/timeline?limit=50", headers=h_owner
    )
    assert res_timeline.status_code == 200
    items = res_timeline.json()["items"]

    # Verify descending ordering by created_at and id
    for idx in range(len(items) - 1):
        curr_created = datetime.fromisoformat(items[idx]["created_at"])
        next_created = datetime.fromisoformat(items[idx + 1]["created_at"])
        assert curr_created >= next_created
        if curr_created == next_created:
            # When timestamps match, UUIDv7 string comparison must preserve descending order
            assert str(items[idx]["id"]) >= str(items[idx + 1]["id"])

    # Verify Workspace Top 5 Recent Activities
    res_ws = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_owner)
    assert res_ws.status_code == 200
    ws_activities = res_ws.json()["recent_activities"]
    assert len(ws_activities) <= 5
    # The top workspace activity should match the first item of the timeline
    assert ws_activities[0]["id"] == items[0]["id"]


def test_timeline_visibility_and_bola_isolation(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "t_bola_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(
        client, "t_bola_lawyer@test.com", role="LAWYER", full_name="Adv. Datta"
    )
    viewer_id, h_viewer = _setup_user(client, "t_bola_viewer@test.com", role="CLIENT")
    _unassigned_id, h_unassigned = _setup_user(
        client, "t_bola_unassigned@test.com", role="CLIENT"
    )

    # 1. Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Confidential Litigation", "description": "Desc"},
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

    # 2. Active Participants can view timeline
    assert client.get(f"/api/v1/cases/{case_id}/timeline", headers=h_owner).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/timeline", headers=h_lawyer).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/timeline", headers=h_viewer).status_code == 200

    # 3. Unassigned user receives 404 (Obscured)
    assert client.get(f"/api/v1/cases/{case_id}/timeline", headers=h_unassigned).status_code == 404

    # 4. Remove Lawyer and verify immediate cutoff (404)
    client.delete(f"/api/v1/cases/{case_id}/participants/{lawyer_id}", headers=h_owner)
    assert client.get(f"/api/v1/cases/{case_id}/timeline", headers=h_lawyer).status_code == 404

    # 5. Invalid / Random Case ID returns 404
    random_case_id = str(uuid.uuid4())
    assert client.get(f"/api/v1/cases/{random_case_id}/timeline", headers=h_owner).status_code == 404
