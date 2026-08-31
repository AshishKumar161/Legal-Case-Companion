import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


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


def test_task_state_machine_lifecycle_and_freeze(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "sm_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(
        client, "sm_lawyer@test.com", role="LAWYER", full_name="Adv. Bannerjee"
    )

    # 1. Create Case & Participants
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "NCLT Insolvency Case", "description": "Corporate insolvency resolution"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )

    # 2. PENDING -> IN_PROGRESS -> COMPLETED
    res_t1 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Draft Section 7 Application", "owner_user_id": lawyer_id},
        headers=h_owner,
    )
    assert res_t1.status_code == 201
    t1_id = res_t1.json()["id"]
    assert res_t1.json()["status"] == "PENDING"
    assert res_t1.json()["completed_at"] is None

    # Transition to IN_PROGRESS
    res_in_prog = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"status": "IN_PROGRESS"},
        headers=h_lawyer,
    )
    assert res_in_prog.status_code == 200
    assert res_in_prog.json()["status"] == "IN_PROGRESS"

    # Transition to COMPLETED
    res_comp = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"status": "COMPLETED"},
        headers=h_lawyer,
    )
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"
    assert res_comp.json()["completed_at"] is not None

    # Invalid reverse transition: COMPLETED -> PENDING -> 422
    res_rev_pend = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"status": "PENDING"},
        headers=h_owner,
    )
    assert res_rev_pend.status_code == 422
    assert "Cannot modify a completed task" in res_rev_pend.json()["error"]["message"]

    # Invalid reverse transition: COMPLETED -> IN_PROGRESS -> 422
    res_rev_prog = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"status": "IN_PROGRESS"},
        headers=h_owner,
    )
    assert res_rev_prog.status_code == 422

    # Invalid reverse transition: COMPLETED -> CANCELLED -> 422
    res_rev_canc = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"status": "CANCELLED"},
        headers=h_owner,
    )
    assert res_rev_canc.status_code == 422

    # Attempting to edit title/assignee/due_date of COMPLETED task -> 422
    res_edit_comp = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"title": "New Title Attempt"},
        headers=h_owner,
    )
    assert res_edit_comp.status_code == 422

    # 3. PENDING -> CANCELLED
    res_t2 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Filing Interim Injunction", "owner_user_id": lawyer_id},
        headers=h_owner,
    )
    t2_id = res_t2.json()["id"]

    res_canc = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t2_id}",
        json={"status": "CANCELLED"},
        headers=h_owner,
    )
    assert res_canc.status_code == 200
    assert res_canc.json()["status"] == "CANCELLED"

    # Invalid transition: CANCELLED -> IN_PROGRESS -> 422
    res_canc_to_prog = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t2_id}",
        json={"status": "IN_PROGRESS"},
        headers=h_lawyer,
    )
    assert res_canc_to_prog.status_code == 422
    assert "Cannot modify a cancelled task" in res_canc_to_prog.json()["error"]["message"]

    # 4. IN_PROGRESS -> CANCELLED
    res_t3 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Expert Witness Deposition"},
        headers=h_owner,
    )
    t3_id = res_t3.json()["id"]
    client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t3_id}",
        json={"status": "IN_PROGRESS"},
        headers=h_owner,
    )
    res_prog_to_canc = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t3_id}",
        json={"status": "CANCELLED"},
        headers=h_owner,
    )
    assert res_prog_to_canc.status_code == 200
    assert res_prog_to_canc.json()["status"] == "CANCELLED"


def test_fine_grained_assignment_rules(client: TestClient):
    owner_id, h_owner = _setup_user(client, "asg_owner@test.com", role="CLIENT")
    lawyer_a_id, _h_lawyer_a = _setup_user(
        client, "asg_la@test.com", role="LAWYER", full_name="Adv. Sen"
    )
    viewer_id, _h_viewer = _setup_user(client, "asg_view@test.com", role="CLIENT")
    unrelated_id, _h_unrelated = _setup_user(
        client, "asg_unrel@test.com", role="CLIENT"
    )

    # Create Case & Participants
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Arbitration Proceedings", "description": "Commercial dispute"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_a_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": viewer_id, "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 1. Assign to Active Lawyer -> Success (201)
    res_t1 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Prepare Statement of Claim", "owner_user_id": lawyer_a_id},
        headers=h_owner,
    )
    assert res_t1.status_code == 201
    assert res_t1.json()["owner_user_id"] == lawyer_a_id
    t1_id = res_t1.json()["id"]

    # 2. Assign to Case Owner -> Success (200)
    res_asg_owner = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"owner_user_id": owner_id},
        headers=h_owner,
    )
    assert res_asg_owner.status_code == 200
    assert res_asg_owner.json()["owner_user_id"] == owner_id

    # 3. Unassign task (set to None) -> Success (200)
    res_unassign = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"owner_user_id": None},
        headers=h_owner,
    )
    assert res_unassign.status_code == 200
    assert res_unassign.json()["owner_user_id"] is None

    # 4. Assign to Viewer Participant -> Success (200)
    res_asg_view = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"owner_user_id": viewer_id},
        headers=h_owner,
    )
    assert res_asg_view.status_code == 200
    assert res_asg_view.json()["owner_user_id"] == viewer_id

    # 5. Assign to Unrelated User -> Rejected (422)
    res_asg_unrel = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"owner_user_id": unrelated_id},
        headers=h_owner,
    )
    assert res_asg_unrel.status_code == 422
    assert "active participant" in res_asg_unrel.json()["error"]["message"]

    # 6. Assign to Non-Existent User UUID -> Rejected (422)
    fake_uuid = str(uuid.uuid4())
    res_asg_fake = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"owner_user_id": fake_uuid},
        headers=h_owner,
    )
    assert res_asg_fake.status_code == 422
    assert "active user" in res_asg_fake.json()["error"]["message"]

    # 7. Remove Lawyer and try assigning -> Rejected (422)
    client.delete(f"/api/v1/cases/{case_id}/participants/{lawyer_a_id}", headers=h_owner)
    res_asg_removed = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"owner_user_id": lawyer_a_id},
        headers=h_owner,
    )
    assert res_asg_removed.status_code == 422
    assert "active participant" in res_asg_removed.json()["error"]["message"]


def test_due_date_temporal_validation(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "due_owner@test.com", role="CLIENT")

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Contractual Breach Case", "description": "Damages claim"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    # 1. Valid future due date -> 201
    future_due = (datetime.now(UTC) + timedelta(days=14)).isoformat()
    res_t1 = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Serve Legal Notice", "due_date": future_due},
        headers=h_owner,
    )
    assert res_t1.status_code == 201
    t1_id = res_t1.json()["id"]
    assert res_t1.json()["due_date"] is not None

    # 2. Past due date on creation -> Rejected (422)
    past_due = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    res_past = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Invalid Past Task", "due_date": past_due},
        headers=h_owner,
    )
    assert res_past.status_code == 422
    assert "cannot be in the past" in res_past.json()["error"]["message"]

    # 3. Valid update to future due date -> 200
    new_future_due = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    res_up_due = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{t1_id}",
        json={"due_date": new_future_due},
        headers=h_owner,
    )
    assert res_up_due.status_code == 200


def test_task_authorization_matrix_and_bola(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "auth_t_owner@test.com", role="CLIENT")
    lawyer_creator_id, h_l_creator = _setup_user(
        client, "auth_tl_c@test.com", role="LAWYER", full_name="Adv. Creator"
    )
    lawyer_assignee_id, h_l_assignee = _setup_user(
        client, "auth_tl_a@test.com", role="LAWYER", full_name="Adv. Assignee"
    )
    lawyer_other_id, h_l_other = _setup_user(
        client, "auth_tl_o@test.com", role="LAWYER", full_name="Adv. Other"
    )
    viewer_id, h_viewer = _setup_user(client, "auth_tv@test.com", role="CLIENT")
    _unassigned_id, h_unassigned = _setup_user(
        client, "auth_tun@test.com", role="CLIENT"
    )

    # Create Case 1
    res_case1 = client.post(
        "/api/v1/cases",
        json={"title": "Case 1", "description": "Desc 1"},
        headers=h_owner,
    )
    case1_id = res_case1.json()["id"]

    # Add Participants to Case 1
    client.post(
        f"/api/v1/cases/{case1_id}/participants",
        json={"user_id": lawyer_creator_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case1_id}/participants",
        json={"user_id": lawyer_assignee_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case1_id}/participants",
        json={"user_id": lawyer_other_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case1_id}/participants",
        json={"user_id": viewer_id, "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 1. Lawyer Creator creates a task assigned to Lawyer Assignee
    res_t = client.post(
        f"/api/v1/cases/{case1_id}/tasks",
        json={
            "title": "Draft Evidentiary Affidavit",
            "description": "Initial draft",
            "owner_user_id": lawyer_assignee_id,
        },
        headers=h_l_creator,
    )
    assert res_t.status_code == 201
    task_id = res_t.json()["id"]

    # 2. Read Permissions:
    # All active participants can view the task
    assert client.get(f"/api/v1/cases/{case1_id}/tasks/{task_id}", headers=h_owner).status_code == 200
    assert client.get(f"/api/v1/cases/{case1_id}/tasks/{task_id}", headers=h_l_creator).status_code == 200
    assert client.get(f"/api/v1/cases/{case1_id}/tasks/{task_id}", headers=h_l_assignee).status_code == 200
    assert client.get(f"/api/v1/cases/{case1_id}/tasks/{task_id}", headers=h_l_other).status_code == 200
    assert client.get(f"/api/v1/cases/{case1_id}/tasks/{task_id}", headers=h_viewer).status_code == 200

    # Unassigned user receives 404
    assert client.get(f"/api/v1/cases/{case1_id}/tasks/{task_id}", headers=h_unassigned).status_code == 404

    # 3. Update Permissions:
    # Lawyer Other (assigned lawyer on the case) updates description -> 200
    res_l_other_up = client.patch(
        f"/api/v1/cases/{case1_id}/tasks/{task_id}",
        json={"description": "Updated by co-counsel lawyer"},
        headers=h_l_other,
    )
    assert res_l_other_up.status_code == 200
    assert res_l_other_up.json()["description"] == "Updated by co-counsel lawyer"

    # Viewer tries to edit -> 403 Forbidden
    res_v_up = client.patch(
        f"/api/v1/cases/{case1_id}/tasks/{task_id}",
        json={"title": "Viewer Edit"},
        headers=h_viewer,
    )
    assert res_v_up.status_code == 403

    # Lawyer Assignee updates status to IN_PROGRESS -> 200
    assert client.patch(
        f"/api/v1/cases/{case1_id}/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=h_l_assignee,
    ).status_code == 200

    # Lawyer Creator updates description -> 200
    assert client.patch(
        f"/api/v1/cases/{case1_id}/tasks/{task_id}",
        json={"description": "Updated by creator"},
        headers=h_l_creator,
    ).status_code == 200

    # Case Owner updates title -> 200
    assert client.patch(
        f"/api/v1/cases/{case1_id}/tasks/{task_id}",
        json={"title": "Owner Reviewed Affidavit"},
        headers=h_owner,
    ).status_code == 200

    # 4. Delete Permissions:
    # Lawyer Assignee (assigned but not creator) tries to delete -> 403
    assert client.delete(f"/api/v1/cases/{case1_id}/tasks/{task_id}", headers=h_l_assignee).status_code == 403

    # Lawyer Other tries to delete -> 403
    assert client.delete(f"/api/v1/cases/{case1_id}/tasks/{task_id}", headers=h_l_other).status_code == 403

    # Viewer tries to delete -> 403
    assert client.delete(f"/api/v1/cases/{case1_id}/tasks/{task_id}", headers=h_viewer).status_code == 403

    # 5. BOLA & IDOR:
    # Random Task UUID
    random_task_id = str(uuid.uuid4())
    assert client.get(f"/api/v1/cases/{case1_id}/tasks/{random_task_id}", headers=h_owner).status_code == 404

    # Create Case 2
    res_case2 = client.post(
        "/api/v1/cases",
        json={"title": "Case 2", "description": "Desc 2"},
        headers=h_owner,
    )
    case2_id = res_case2.json()["id"]

    # Substituting Case 2 ID with Task 1 ID -> 404
    assert client.get(f"/api/v1/cases/{case2_id}/tasks/{task_id}", headers=h_owner).status_code == 404

    # 6. Delete Task by Creator -> 204
    assert client.delete(f"/api/v1/cases/{case1_id}/tasks/{task_id}", headers=h_l_creator).status_code == 204
    assert client.get(f"/api/v1/cases/{case1_id}/tasks/{task_id}", headers=h_owner).status_code == 404

    # 7. Verify Audit Events
    audits = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.metadata_json["case_id"].astext == case1_id
            if db.bind.dialect.name == "postgresql"
            else AuditEvent.id.isnot(None)
        )
        .all()
    )
    audit_actions = [a.event_type for a in audits]
    assert "TASK_CREATED" in audit_actions
    assert "TASK_UPDATED" in audit_actions
    assert "TASK_DELETED" in audit_actions
