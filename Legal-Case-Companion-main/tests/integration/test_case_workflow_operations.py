from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.models.case import (
    Case,
    CaseParticipant,
    CaseStatus,
    ParticipantRole,
    ParticipantStatus,
)
from app.models.case_intelligence import (
    CaseChronologyEvent,
    CaseEvidenceGap,
    DatePrecision,
    EvidenceGapStatus,
    EvidenceGapType,
    RiskSeverity,
)
from app.models.workflow import (
    CaseDeadline,
    DeadlineStatus,
    DeadlineType,
    HearingStatus,
)


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "dummy-test-key"
    yield
    settings.OPENAI_API_KEY = original_key


def _setup_user(client: TestClient, email: str, role: str = "LAWYER"):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": role, "full_name": "Workflow User"},
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_task_operations_assignment_and_lifecycle(client: TestClient, db: Session):
    """Verifies task creation, assignment to valid participant, status transitions, and completion."""
    _u1_id, h1 = _setup_user(client, "wf_task1@test.com", role="CLIENT")
    u2_id, _h2 = _setup_user(client, "wf_task2@test.com", role="LAWYER")

    res_c = client.post("/api/v1/cases", json={"title": "Task Case", "description": "D"}, headers=h1)
    case_id = res_c.json()["id"]

    # Add Lawyer as participant
    p_lawyer = CaseParticipant(
        id=generate_uuid7(), case_id=UUID(case_id), user_id=UUID(u2_id),
        participant_role=ParticipantRole.LAWYER, status=ParticipantStatus.ACTIVE,
    )
    db.add(p_lawyer)
    db.commit()

    # 1. Create task assigned to lawyer
    due = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    res_t = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Draft Written Statement", "due_date": due, "owner_user_id": u2_id, "priority": "HIGH"},
        headers=h1,
    )
    assert res_t.status_code == 201
    task = res_t.json()
    task_id = task["id"]
    assert task["owner_user_id"] == u2_id
    assert task["status"] == "PENDING"
    assert task["priority"] == "HIGH"

    # 2. Assignment to non-participant fails
    dummy_uid = str(generate_uuid7())
    res_bad_assign = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Invalid Task", "owner_user_id": dummy_uid},
        headers=h1,
    )
    assert res_bad_assign.status_code in (400, 422)

    # 3. Transition: PENDING -> IN_PROGRESS -> COMPLETED
    res_prog = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=h1,
    )
    assert res_prog.status_code == 200
    assert res_prog.json()["status"] == "IN_PROGRESS"

    res_comp = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"status": "COMPLETED"},
        headers=h1,
    )
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"
    assert res_comp.json()["completed_at"] is not None

    # 4. Invalid transition: COMPLETED -> PENDING should fail
    res_invalid = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"status": "PENDING"},
        headers=h1,
    )
    assert res_invalid.status_code in (400, 422)


def test_deadline_creation_and_overdue_handling(client: TestClient, db: Session):
    """Verifies deadline scheduling, dynamic overdue calculation, and completion."""
    _u_id, headers = _setup_user(client, "wf_deadline@test.com", role="CLIENT")
    res_c = client.post("/api/v1/cases", json={"title": "Deadline Case", "description": "D"}, headers=headers)
    case_id = res_c.json()["id"]

    # 1. Create upcoming deadline
    future_dl = (datetime.now(UTC) + timedelta(days=10)).isoformat()
    res_dl = client.post(
        f"/api/v1/cases/{case_id}/deadlines",
        json={"title": "File Replication", "deadline_at": future_dl, "deadline_type": "COURT_FILING"},
        headers=headers,
    )
    assert res_dl.status_code == 201
    dl_id = res_dl.json()["id"]
    assert res_dl.json()["status"] == DeadlineStatus.UPCOMING.value

    # 2. Seed an overdue deadline directly in DB (scheduled in the past)
    past_dl_time = datetime.now(UTC) - timedelta(days=2)
    past_dl = CaseDeadline(
        id=generate_uuid7(), case_id=UUID(case_id), title="Statutory 15-Day Reply",
        deadline_at=past_dl_time, deadline_type=DeadlineType.REPLY_NOTICE, status=DeadlineStatus.UPCOMING,
    )
    db.add(past_dl)
    db.commit()

    # 3. Retrieve overview -> past deadline dynamically marked OVERDUE
    res_overview = client.get(f"/api/v1/cases/{case_id}/workflow", headers=headers)
    assert res_overview.status_code == 200
    data = res_overview.json()
    assert data["operations_summary"]["upcoming_deadlines_count"] >= 1
    assert data["operations_summary"]["overdue_deadlines_count"] >= 1

    # 4. Complete deadline
    res_comp = client.patch(
        f"/api/v1/cases/{case_id}/deadlines/{dl_id}",
        json={"status": DeadlineStatus.COMPLETED.value},
        headers=headers,
    )
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == DeadlineStatus.COMPLETED.value
    assert res_comp.json()["completed_at"] is not None


def test_hearing_management_and_confirmation(client: TestClient, db: Session):
    """Verifies court hearing scheduling, updates, and human confirmation."""
    _u_id, headers = _setup_user(client, "wf_hearing@test.com", role="LAWYER")
    res_c = client.post("/api/v1/cases", json={"title": "Hearing Case", "description": "D"}, headers=headers)
    case_id = res_c.json()["id"]

    # 1. Create hearing
    h_time = (datetime.now(UTC) + timedelta(days=14)).isoformat()
    res_h = client.post(
        f"/api/v1/cases/{case_id}/hearings",
        json={
            "court_name": "High Court of Delhi",
            "hearing_at": h_time,
            "purpose": "Arguments on Interim Injunction Application",
            "bench_or_coram": "Court Room 21, Hon'ble Justice A.K. Pathak",
            "is_confirmed": False,
        },
        headers=headers,
    )
    assert res_h.status_code == 201
    hearing_id = res_h.json()["id"]
    assert res_h.json()["is_confirmed"] is False

    # 2. Confirm hearing
    res_conf = client.post(f"/api/v1/cases/{case_id}/hearings/{hearing_id}/confirm", headers=headers)
    assert res_conf.status_code == 200
    assert res_conf.json()["is_confirmed"] is True

    # 3. Update hearing status to CONCLUDED
    res_up = client.patch(
        f"/api/v1/cases/{case_id}/hearings/{hearing_id}",
        json={"status": HearingStatus.CONCLUDED.value, "notes": "Arguments concluded, orders reserved."},
        headers=headers,
    )
    assert res_up.status_code == 200
    assert res_up.json()["status"] == HearingStatus.CONCLUDED.value


def test_smart_workflow_suggestions_from_case_intelligence(client: TestClient, db: Session):
    """Verifies automatic generation of unconfirmed task & deadline suggestions from evidence gaps and chronology."""
    _u_id, headers = _setup_user(client, "wf_sugg@test.com", role="LAWYER")
    res_c = client.post("/api/v1/cases", json={"title": "Suggestions Case", "description": "D"}, headers=headers)
    case_id = res_c.json()["id"]

    # 1. Seed Evidence Gap (Missing Notice Receipt)
    gap = CaseEvidenceGap(
        id=generate_uuid7(), case_id=UUID(case_id),
        description="Speed post tracking receipt for demand notice not found.",
        gap_type=EvidenceGapType.MISSING_DOCUMENT, severity=RiskSeverity.HIGH,
        status=EvidenceGapStatus.NOT_FOUND_IN_AVAILABLE_MATERIALS,
    )
    # 2. Seed Chronology Event
    event = CaseChronologyEvent(
        id=generate_uuid7(), case_id=UUID(case_id),
        event_date=date(2026, 9, 20), date_text="20 Sept 2026",
        date_precision=DatePrecision.EXACT_DATE, event_type="COURT_LISTING",
        description="Matter listed for preliminary hearing before the Registrar.",
    )
    db.add_all([gap, event])
    db.commit()

    # 3. Trigger smart suggestion generation
    res_sugg = client.post(f"/api/v1/cases/{case_id}/workflow/suggestions/generate", headers=headers)
    assert res_sugg.status_code == 200
    assert res_sugg.json()["suggested_tasks_count"] >= 1
    assert res_sugg.json()["suggested_hearings_count"] >= 1

    # 4. Check that suggested items are unconfirmed (is_confirmed=False)
    res_wf = client.get(f"/api/v1/cases/{case_id}/workflow", headers=headers)
    data = res_wf.json()
    assert data["operations_summary"]["unconfirmed_suggestions_count"] >= 2

    # 5. Repeated call is idempotent (0 new items generated)
    res_sugg_repeat = client.post(f"/api/v1/cases/{case_id}/workflow/suggestions/generate", headers=headers)
    assert res_sugg_repeat.json()["suggested_tasks_count"] == 0
    assert res_sugg_repeat.json()["suggested_hearings_count"] == 0


def test_closed_case_workflow_mutations_blocked(client: TestClient, db: Session):
    """Verifies that mutations on tasks/deadlines/hearings are rejected when a case is CLOSED."""
    _u_id, headers = _setup_user(client, "wf_closed@test.com", role="CLIENT")
    res_c = client.post("/api/v1/cases", json={"title": "Closed Case", "description": "D"}, headers=headers)
    case_id = res_c.json()["id"]

    # Close the case directly
    case = db.query(Case).filter(Case.id == UUID(case_id)).first()
    case.status = CaseStatus.CLOSED
    db.commit()

    # Attempt to create task -> 400/422 error
    res_task = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "Post-closing task"},
        headers=headers,
    )
    assert res_task.status_code in (400, 422)

    # Attempt to create deadline -> 400/422 error
    res_dl = client.post(
        f"/api/v1/cases/{case_id}/deadlines",
        json={"title": "Post-closing deadline", "deadline_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
        headers=headers,
    )
    assert res_dl.status_code in (400, 422)


def test_workflow_cross_case_isolation_and_security(client: TestClient, db: Session):
    """Verifies that unauthorized users from other cases cannot access or mutate workflow objects."""
    _u1_id, h1 = _setup_user(client, "wf_iso1@test.com", role="CLIENT")
    _u2_id, h2 = _setup_user(client, "wf_iso2@test.com", role="CLIENT")

    res_c1 = client.post("/api/v1/cases", json={"title": "Case A", "description": "D"}, headers=h1)
    c1_id = res_c1.json()["id"]

    # User 1 creates deadline in Case A
    res_dl = client.post(
        f"/api/v1/cases/{c1_id}/deadlines",
        json={"title": "Confidential Filing", "deadline_at": (datetime.now(UTC) + timedelta(days=3)).isoformat()},
        headers=h1,
    )
    assert res_dl.status_code == 201
    dl_id = res_dl.json()["id"]

    # User 2 attempts to read Case A workflow -> 404
    res_unauth_wf = client.get(f"/api/v1/cases/{c1_id}/workflow", headers=h2)
    assert res_unauth_wf.status_code == 404

    # User 2 attempts to mutate Case A deadline -> 404
    res_unauth_dl = client.patch(
        f"/api/v1/cases/{c1_id}/deadlines/{dl_id}",
        json={"status": "COMPLETED"},
        headers=h2,
    )
    assert res_unauth_dl.status_code == 404
