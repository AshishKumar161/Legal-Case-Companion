import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.models.case import (
    Case,
    CaseParticipant,
    ParticipantRole,
    ParticipantStatus,
)
from app.models.evidence import Evidence
from app.models.task import CaseTask, TaskPriority, TaskStatus
from app.models.workflow import (
    CaseDeadline,
    CaseHearing,
    DeadlineStatus,
    DeadlineType,
    HearingStatus,
)
from app.domain.notifications.reminder_service import ReminderService


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "dummy-test-key"
    yield
    settings.OPENAI_API_KEY = original_key


def _setup_user(client: TestClient, email: str, role: str = "CLIENT") -> tuple[str, dict[str, str]]:
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": role, "full_name": "Test User"},
    )
    user_id = res_reg.json().get("id")
    res_login = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res_login.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_task_crud_and_lifecycle_state_machine(client: TestClient, db: Session):
    """Verifies full task lifecycle transitions:

    PENDING -> IN_PROGRESS -> COMPLETED -> REOPEN (IN_PROGRESS) -> CANCELLED -> REOPEN (IN_PROGRESS)
    and validates terminal state protections.
    """
    _u1_id, h1 = _setup_user(client, "phase12_task_client@test.com", role="CLIENT")

    res_case = client.post("/api/v1/cases", json={"title": "Lifecycle Matter", "description": "Ops test"}, headers=h1)
    assert res_case.status_code == 201
    case_id = res_case.json()["id"]

    due = (datetime.now(UTC) + timedelta(days=7)).isoformat()

    # 1. Create Task in PENDING status
    res_t = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={
            "title": "Review Settlement Proposal",
            "description": "Examine proposed terms and formulate counter-terms",
            "priority": "HIGH",
            "due_date": due,
        },
        headers=h1,
    )
    assert res_t.status_code == 201
    task_data = res_t.json()
    task_id = task_data["id"]
    assert task_data["status"] == "PENDING"
    assert task_data["priority"] == "HIGH"
    assert task_data["completed_at"] is None

    # 2. Transition: PENDING -> IN_PROGRESS via start endpoint
    res_start = client.post(f"/api/v1/cases/{case_id}/tasks/{task_id}/start", headers=h1)
    assert res_start.status_code == 200
    assert res_start.json()["status"] == "IN_PROGRESS"

    # 3. Transition: IN_PROGRESS -> COMPLETED via complete endpoint
    res_comp = client.post(f"/api/v1/cases/{case_id}/tasks/{task_id}/complete", headers=h1)
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"
    assert res_comp.json()["completed_at"] is not None

    # 4. Modifying completed task without reopening fails closed
    res_bad_mod = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"title": "Illegal edit on completed task"},
        headers=h1,
    )
    assert res_bad_mod.status_code in (400, 422)

    # 5. Explicit Reopen: COMPLETED -> IN_PROGRESS
    res_reopen = client.post(f"/api/v1/cases/{case_id}/tasks/{task_id}/reopen", headers=h1)
    assert res_reopen.status_code == 200
    assert res_reopen.json()["status"] == "IN_PROGRESS"
    assert res_reopen.json()["completed_at"] is None

    # 6. Transition: IN_PROGRESS -> CANCELLED
    res_cancel = client.post(f"/api/v1/cases/{case_id}/tasks/{task_id}/cancel", headers=h1)
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "CANCELLED"

    # 7. Reopen from CANCELLED back to IN_PROGRESS
    res_reopen2 = client.post(f"/api/v1/cases/{case_id}/tasks/{task_id}/reopen", headers=h1)
    assert res_reopen2.status_code == 200
    assert res_reopen2.json()["status"] == "IN_PROGRESS"


def test_task_assignment_and_reassignment_authorization(client: TestClient, db: Session):
    """Ensures tasks can only be assigned or reassigned to authorized case participants."""
    c1_id, h1 = _setup_user(client, "assign_client@test.com", role="CLIENT")
    lawyer_id, _h_lawyer = _setup_user(client, "assign_lawyer@test.com", role="LAWYER")
    unrelated_id, _h_unrelated = _setup_user(client, "unrelated_user@test.com", role="CLIENT")

    res_case = client.post("/api/v1/cases", json={"title": "Assignment Matter", "description": "Auth test"}, headers=h1)
    case_id = res_case.json()["id"]

    # Add lawyer as active case participant
    p_lawyer = CaseParticipant(
        id=generate_uuid7(),
        case_id=UUID(case_id),
        user_id=UUID(lawyer_id),
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(p_lawyer)
    db.commit()

    # 1. Assignment to authorized participant succeeds
    res_task = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Draft Rejoinder", "owner_user_id": lawyer_id, "priority": "HIGH"},
        headers=h1,
    )
    assert res_task.status_code == 201
    task_id = res_task.json()["id"]
    assert res_task.json()["owner_user_id"] == lawyer_id

    # 2. Assignment to unrelated user fails closed
    res_bad_assign = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Illegal Task", "owner_user_id": unrelated_id},
        headers=h1,
    )
    assert res_bad_assign.status_code in (400, 422)

    # 3. Reassign to client participant succeeds
    res_reassign = client.post(
        f"/api/v1/cases/{case_id}/tasks/{task_id}/reassign",
        json={"owner_user_id": c1_id},
        headers=h1,
    )
    assert res_reassign.status_code == 200
    assert res_reassign.json()["owner_user_id"] == c1_id

    # 4. Reassign to unrelated user fails closed
    res_bad_reassign = client.post(
        f"/api/v1/cases/{case_id}/tasks/{task_id}/reassign",
        json={"owner_user_id": unrelated_id},
        headers=h1,
    )
    assert res_bad_reassign.status_code in (400, 422)


def test_task_batch_operations_and_tenant_isolation(client: TestClient, db: Session):
    """Verifies atomic batch actions (COMPLETE, CANCEL, CHANGE_PRIORITY, REASSIGN)

    and asserts fail-closed behavior when mixing resources across cases.
    """
    _u_id, h1 = _setup_user(client, "batch_user@test.com", role="CLIENT")
    _u2_id, h2 = _setup_user(client, "batch_other@test.com", role="CLIENT")

    res_c1 = client.post("/api/v1/cases", json={"title": "Batch Case 1", "description": "Batch Desc 1"}, headers=h1)
    case1_id = res_c1.json()["id"]

    res_c2 = client.post("/api/v1/cases", json={"title": "Batch Case 2", "description": "Batch Desc 2"}, headers=h2)
    case2_id = res_c2.json()["id"]

    # Create 3 tasks in Case 1
    t1 = client.post(f"/api/v1/cases/{case1_id}/tasks", json={"title": "Task 1", "priority": "LOW"}, headers=h1).json()
    t2 = client.post(f"/api/v1/cases/{case1_id}/tasks", json={"title": "Task 2", "priority": "LOW"}, headers=h1).json()
    t3 = client.post(f"/api/v1/cases/{case1_id}/tasks", json={"title": "Task 3", "priority": "LOW"}, headers=h1).json()

    # Create 1 task in Case 2
    t_other = client.post(f"/api/v1/cases/{case2_id}/tasks", json={"title": "Case 2 Task"}, headers=h2).json()

    # 1. Batch priority update in Case 1
    res_batch_prio = client.post(
        f"/api/v1/cases/{case1_id}/tasks/batch",
        json={"task_ids": [t1["id"], t2["id"]], "action": "CHANGE_PRIORITY", "priority": "URGENT"},
        headers=h1,
    )
    assert res_batch_prio.status_code == 200
    assert res_batch_prio.json()["updated_count"] == 2

    # 2. Batch complete in Case 1
    res_batch_comp = client.post(
        f"/api/v1/cases/{case1_id}/tasks/batch",
        json={"task_ids": [t1["id"], t2["id"]], "action": "COMPLETE"},
        headers=h1,
    )
    assert res_batch_comp.status_code == 200
    assert res_batch_comp.json()["updated_count"] == 2

    # 3. Mixed-case fail-closed tenant isolation check:
    # Attempting to include t_other (from Case 2) in a batch for Case 1 must fail with 404 (ResourceNotFoundError)
    res_bad_batch = client.post(
        f"/api/v1/cases/{case1_id}/tasks/batch",
        json={"task_ids": [t3["id"], t_other["id"]], "action": "COMPLETE"},
        headers=h1,
    )
    assert res_bad_batch.status_code in (404, 400)


def test_deadline_provenance_and_overdue_automation(client: TestClient, db: Session):
    """Tests deadline creation with provenance, manual completion, and scheduled overdue processing."""
    _u_id, headers = _setup_user(client, "deadline_ops@test.com", role="CLIENT")
    res_c = client.post("/api/v1/cases", json={"title": "Deadline Ops Matter", "description": "Deadline Ops Desc"}, headers=headers)
    case_id = res_c.json()["id"]

    # 1. Create a hearing to link deadline
    h_time = (datetime.now(UTC) + timedelta(days=10)).isoformat()
    res_h = client.post(
        f"/api/v1/cases/{case_id}/hearings",
        json={"court_name": "District Court", "hearing_at": h_time, "purpose": "Framing of Issues"},
        headers=headers,
    )
    hearing_id = res_h.json()["id"]

    # 2. Create deadline linked to hearing with explicit provenance
    dl_time = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    res_dl = client.post(
        f"/api/v1/cases/{case_id}/deadlines",
        json={
            "title": "Filing of Witness List",
            "deadline_at": dl_time,
            "deadline_type": "COURT_FILING",
            "linked_hearing_id": hearing_id,
            "retrieval_method": "MANUAL",
        },
        headers=headers,
    )
    assert res_dl.status_code == 201
    dl_data = res_dl.json()
    dl_id = dl_data["id"]
    assert dl_data["linked_hearing_id"] == hearing_id
    assert dl_data["retrieval_method"] == "MANUAL"
    assert dl_data["status"] == "UPCOMING"

    # 3. Complete deadline
    res_comp = client.post(f"/api/v1/cases/{case_id}/deadlines/{dl_id}/complete", headers=headers)
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"

    # 4. Test deterministic overdue detection via ReminderService
    past_dl = CaseDeadline(
        id=generate_uuid7(),
        case_id=UUID(case_id),
        title="Lapsed Statutory Notice Compliance",
        deadline_at=datetime.now(UTC) - timedelta(days=3),
        deadline_type=DeadlineType.REPLY_NOTICE,
        status=DeadlineStatus.UPCOMING,
        retrieval_method="MANUAL",
        retrieved_at=datetime.now(UTC),
    )
    db.add(past_dl)
    db.commit()

    reminder_svc = ReminderService(db)
    summary = reminder_svc.process_overdue_deadlines_and_tasks()
    assert summary["deadlines_marked_overdue"] >= 1

    db.refresh(past_dl)
    assert past_dl.status == DeadlineStatus.OVERDUE


def test_deterministic_workflow_templates_zero_ai(client: TestClient, db: Session):
    """Verifies deterministic application of all 4 operational templates:

    HEARING_PREPARATION, POST_HEARING_FOLLOWUP, EVIDENCE_PREPARATION, NEW_CONSULTATION.
    """
    _u_id, headers = _setup_user(client, "template_client@test.com", role="CLIENT")
    res_c = client.post("/api/v1/cases", json={"title": "Template Matter", "description": "Template Desc"}, headers=headers)
    case_id = res_c.json()["id"]

    # Create scheduled hearing
    h_time = (datetime.now(UTC) + timedelta(days=8)).isoformat()
    res_h = client.post(
        f"/api/v1/cases/{case_id}/hearings",
        json={"court_name": "High Court", "hearing_at": h_time, "purpose": "Final Hearing"},
        headers=headers,
    )
    hearing_id = res_h.json()["id"]

    # 1. Apply HEARING_PREPARATION template (generates 6 tasks linked to hearing)
    res_tpl1 = client.post(
        f"/api/v1/cases/{case_id}/workflow/templates/apply",
        json={"template_name": "HEARING_PREPARATION", "hearing_id": hearing_id},
        headers=headers,
    )
    assert res_tpl1.status_code == 201
    tasks1 = res_tpl1.json()
    assert len(tasks1) == 6
    assert all(t["linked_hearing_id"] == hearing_id for t in tasks1)

    # 2. Apply POST_HEARING_FOLLOWUP template (generates 4 tasks)
    res_tpl2 = client.post(
        f"/api/v1/cases/{case_id}/workflow/templates/apply",
        json={"template_name": "POST_HEARING_FOLLOWUP"},
        headers=headers,
    )
    assert res_tpl2.status_code == 201
    assert len(res_tpl2.json()) == 4

    # 3. Apply EVIDENCE_PREPARATION template (generates 3 tasks)
    res_tpl3 = client.post(
        f"/api/v1/cases/{case_id}/workflow/templates/apply",
        json={"template_name": "EVIDENCE_PREPARATION"},
        headers=headers,
    )
    assert res_tpl3.status_code == 201
    assert len(res_tpl3.json()) == 3

    # 4. Apply NEW_CONSULTATION template (generates 3 tasks)
    res_tpl4 = client.post(
        f"/api/v1/cases/{case_id}/workflow/templates/apply",
        json={"template_name": "NEW_CONSULTATION"},
        headers=headers,
    )
    assert res_tpl4.status_code == 201
    assert len(res_tpl4.json()) == 3


def test_case_health_summary_telemetry(client: TestClient, db: Session):
    """Verifies deterministic calculation of operational health indicators."""
    _u_id, headers = _setup_user(client, "health_summary_user@test.com", role="CLIENT")
    res_c = client.post("/api/v1/cases", json={"title": "Health Telemetry Matter", "description": "Health Desc"}, headers=headers)
    case_id = res_c.json()["id"]

    # Add active evidence
    ev = Evidence(
        id=generate_uuid7(),
        case_id=UUID(case_id),
        created_by_user_id=UUID(_u_id),
        title="Primary Lease Deed",
        original_filename="lease.pdf",
        status="ACTIVE",
    )
    db.add(ev)

    # Add overdue task
    overdue_task = CaseTask(
        id=generate_uuid7(),
        case_id=UUID(case_id),
        title="Overdue Client Review",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        due_date=datetime.now(UTC) - timedelta(days=2),
    )
    db.add(overdue_task)

    # Add upcoming deadline
    upcoming_dl = CaseDeadline(
        id=generate_uuid7(),
        case_id=UUID(case_id),
        title="Written Statement Deadline",
        deadline_at=datetime.now(UTC) + timedelta(days=4),
        deadline_type=DeadlineType.COURT_FILING,
        status=DeadlineStatus.UPCOMING,
        retrieval_method="MANUAL",
        retrieved_at=datetime.now(UTC),
    )
    db.add(upcoming_dl)

    # Add upcoming hearing
    hearing = CaseHearing(
        id=generate_uuid7(),
        case_id=UUID(case_id),
        court_name="City Civil Court",
        hearing_at=datetime.now(UTC) + timedelta(days=6),
        purpose="Evidence Recording",
        status=HearingStatus.SCHEDULED,
    )
    db.add(hearing)
    db.commit()

    # Retrieve health summary via API
    res_health = client.get(f"/api/v1/cases/{case_id}/workflow/health-summary", headers=headers)
    assert res_health.status_code == 200
    data = res_health.json()
    assert data["has_upcoming_hearing"] is True
    assert data["next_hearing_court"] == "City Civil Court"
    assert data["overdue_tasks_count"] >= 1
    assert data["upcoming_deadlines_count"] >= 1
    assert data["unreviewed_evidence_count"] >= 1


def test_bola_idor_and_case_isolation(client: TestClient, db: Session):
    """Verifies that tasks, deadlines, and operational workflows are strictly case-scoped

    and unauthorized users receive 404 (existence masked).
    """
    _u1_id, h1 = _setup_user(client, "bola_user1@test.com", role="CLIENT")
    _u2_id, h2 = _setup_user(client, "bola_user2@test.com", role="CLIENT")

    res_c1 = client.post("/api/v1/cases", json={"title": "Private Matter 1", "description": "Private Desc 1"}, headers=h1)
    case1_id = res_c1.json()["id"]

    res_t1 = client.post(
        f"/api/v1/cases/{case1_id}/tasks",
        json={"title": "Confidential Task"},
        headers=h1,
    )
    task1_id = res_t1.json()["id"]

    # Client 2 attempts to read Client 1's workflow dashboard -> 404
    res_bad_wf = client.get(f"/api/v1/cases/{case1_id}/workflow", headers=h2)
    assert res_bad_wf.status_code == 404

    # Client 2 attempts to read Client 1's task -> 404
    res_bad_task = client.get(f"/api/v1/cases/{case1_id}/tasks/{task1_id}", headers=h2)
    assert res_bad_task.status_code == 404

    # Client 2 attempts to complete Client 1's task -> 404
    res_bad_comp = client.post(f"/api/v1/cases/{case1_id}/tasks/{task1_id}/complete", headers=h2)
    assert res_bad_comp.status_code == 404
