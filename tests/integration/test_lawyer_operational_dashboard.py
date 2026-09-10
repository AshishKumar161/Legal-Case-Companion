from datetime import UTC, date, datetime, timedelta
import uuid
import pytest

from app.core.identifiers import generate_uuid7
from app.core.locking import DistributedJobLock, job_lock
from app.core.security import create_access_token
from app.models.bundle import BundleStatus, EvidenceBundle
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole, ParticipantStatus
from app.models.consultation import Consultation, ConsultationStatus
from app.models.evidence import CaseExhibit, Evidence, EvidenceCategory, EvidenceStatus
from app.models.task import CaseTask, TaskPriority, TaskStatus
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole
from app.models.workflow import CaseDeadline, CaseHearing, DeadlineStatus, DeadlineType, HearingStatus
from app.domain.notifications.reminder_service import ReminderService


@pytest.fixture
def dashboard_fixture(client, db):
    """
    Sets up Lawyer A with Case 1 & Case 2, and Lawyer B with Case 3.
    Populates hearings, deadlines, tasks, consultations, and bundles.
    """
    now = datetime.now(UTC)

    # 1. Create Lawyer A
    lawyer_a = User(
        id=generate_uuid7(),
        email=f"lawyer_a_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(lawyer_a)
    db.flush()

    prof_a = LawyerProfile(
        id=generate_uuid7(),
        user_id=lawyer_a.id,
        full_name="Advocate A",
    )
    db.add(prof_a)

    # 2. Create Lawyer B
    lawyer_b = User(
        id=generate_uuid7(),
        email=f"lawyer_b_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(lawyer_b)
    db.flush()

    prof_b = LawyerProfile(
        id=generate_uuid7(),
        user_id=lawyer_b.id,
        full_name="Advocate B",
    )
    db.add(prof_b)

    # 3. Create Case 1 (Lawyer A assigned)
    case_1 = Case(
        id=generate_uuid7(),
        title="Matter 1 — Sharma Dispute",
        description="Active commercial suit",
        status=CaseStatus.OPEN,
    )
    db.add(case_1)
    db.flush()

    part_1 = CaseParticipant(
        id=generate_uuid7(),
        case_id=case_1.id,
        user_id=lawyer_a.id,
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(part_1)

    # 4. Create Case 2 (Lawyer A assigned)
    case_2 = Case(
        id=generate_uuid7(),
        title="Matter 2 — Apex Construction",
        description="Arbitration matter",
        status=CaseStatus.OPEN,
    )
    db.add(case_2)
    db.flush()

    part_2 = CaseParticipant(
        id=generate_uuid7(),
        case_id=case_2.id,
        user_id=lawyer_a.id,
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(part_2)

    # 5. Create Case 3 (Lawyer B assigned, Lawyer A NOT assigned)
    case_3 = Case(
        id=generate_uuid7(),
        title="Matter 3 — Confidential Foreign Case",
        description="Private matter belonging strictly to Lawyer B",
        status=CaseStatus.OPEN,
    )
    db.add(case_3)
    db.flush()

    part_3 = CaseParticipant(
        id=generate_uuid7(),
        case_id=case_3.id,
        user_id=lawyer_b.id,
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(part_3)

    # -------------------------------------------------------------
    # Case 1 Items (Today & Imminent)
    # -------------------------------------------------------------
    # Hearing today in 2 hours
    hearing_1 = CaseHearing(
        id=generate_uuid7(),
        case_id=case_1.id,
        court_name="Delhi High Court",
        hearing_at=now + timedelta(hours=2),
        purpose="Arguments on Interim Relief",
        status=HearingStatus.SCHEDULED,
        bench_or_coram="Courtroom 4",
    )
    db.add(hearing_1)

    # Task linked to hearing 1 (completed)
    task_1 = CaseTask(
        id=generate_uuid7(),
        case_id=case_1.id,
        title="Finalize Exhibit Index",
        owner_user_id=lawyer_a.id,
        due_date=now - timedelta(hours=1),  # overdue / due today
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.HIGH,
        linked_hearing_id=hearing_1.id,
    )
    db.add(task_1)

    # Overdue Task in Case 1
    task_overdue = CaseTask(
        id=generate_uuid7(),
        case_id=case_1.id,
        title="File Written Statement",
        owner_user_id=lawyer_a.id,
        due_date=now - timedelta(days=2),
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.URGENT,
    )
    db.add(task_overdue)

    # Deadline in Case 1 (Approaching in 24h)
    deadline_1 = CaseDeadline(
        id=generate_uuid7(),
        case_id=case_1.id,
        title="Rejoinder Filing Cutoff",
        deadline_at=now + timedelta(hours=24),
        deadline_type=DeadlineType.COURT_FILING,
        status=DeadlineStatus.UPCOMING,
        source_type="COURT_ORDER",
        source_reference="Order dated 10 Aug",
    )
    db.add(deadline_1)

    # Bundle for hearing 1
    bundle_1 = EvidenceBundle(
        id=generate_uuid7(),
        case_id=case_1.id,
        hearing_id=hearing_1.id,
        title="Hearing Core Bundle",
        bates_prefix="LCC",
        bates_start=1,
        status=BundleStatus.FINALIZED,
        created_by_user_id=lawyer_a.id,
    )
    db.add(bundle_1)

    # -------------------------------------------------------------
    # Case 2 Items (Upcoming in 5 days)
    # -------------------------------------------------------------
    hearing_2 = CaseHearing(
        id=generate_uuid7(),
        case_id=case_2.id,
        court_name="Commercial Court",
        hearing_at=now + timedelta(days=5),
        purpose="Framing of Issues",
        status=HearingStatus.SCHEDULED,
    )
    db.add(hearing_2)

    task_2 = CaseTask(
        id=generate_uuid7(),
        case_id=case_2.id,
        title="Prepare Draft Issues",
        owner_user_id=lawyer_a.id,
        due_date=now + timedelta(days=3),
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
        linked_hearing_id=hearing_2.id,
    )
    db.add(task_2)

    # Unreviewed / Quarantined Evidence in Case 2
    ev_2 = Evidence(
        id=generate_uuid7(),
        case_id=case_2.id,
        created_by_user_id=lawyer_a.id,
        title="Contract Agreement 2024",
        original_filename="contract_2024.pdf",
        category=EvidenceCategory.CONTRACTUAL,
        status=EvidenceStatus.QUARANTINED,
    )
    db.add(ev_2)

    # -------------------------------------------------------------
    # Case 3 Items (Lawyer B Only - MUST NEVER LEAK TO LAWYER A)
    # -------------------------------------------------------------
    hearing_3 = CaseHearing(
        id=generate_uuid7(),
        case_id=case_3.id,
        court_name="Secret Court B",
        hearing_at=now + timedelta(hours=3),
        purpose="Top Secret B Proceedings",
        status=HearingStatus.SCHEDULED,
    )
    db.add(hearing_3)

    task_3 = CaseTask(
        id=generate_uuid7(),
        case_id=case_3.id,
        title="Lawyer B Confidential Task",
        owner_user_id=lawyer_b.id,
        due_date=now - timedelta(days=1),
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.URGENT,
    )
    db.add(task_3)

    deadline_3 = CaseDeadline(
        id=generate_uuid7(),
        case_id=case_3.id,
        title="Lawyer B Secret Deadline",
        deadline_at=now + timedelta(hours=12),
        status=DeadlineStatus.UPCOMING,
    )
    db.add(deadline_3)

    client_user = User(
        id=generate_uuid7(),
        email=f"client_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(client_user)
    db.flush()

    client_profile = ClientProfile(
        id=generate_uuid7(),
        user_id=client_user.id,
        full_name="Test Client",
    )
    db.add(client_profile)
    db.flush()

    consultation_3 = Consultation(
        id=generate_uuid7(),
        case_id=case_3.id,
        lawyer_id=prof_b.id,
        client_id=client_profile.id,
        scheduled_at=now + timedelta(hours=1),
        status=ConsultationStatus.SCHEDULED,
        duration_minutes=30,
        fee_amount=5000,
        currency="INR",
    )
    db.add(consultation_3)

    db.commit()

    token_a = create_access_token(subject=str(lawyer_a.id), role=lawyer_a.role.value)
    token_b = create_access_token(subject=str(lawyer_b.id), role=lawyer_b.role.value)

    return {
        "client": client,
        "lawyer_a": lawyer_a,
        "lawyer_b": lawyer_b,
        "token_a": token_a,
        "token_b": token_b,
        "case_1": case_1,
        "case_2": case_2,
        "case_3": case_3,
        "hearing_1": hearing_1,
        "hearing_3": hearing_3,
        "task_overdue": task_overdue,
        "task_3": task_3,
        "deadline_1": deadline_1,
        "deadline_3": deadline_3,
    }


def test_lawyer_dashboard_aggregation_and_metrics(dashboard_fixture):
    """Verifies that the lawyer dashboard correctly aggregates today's agenda, metrics, hearings, and matters."""
    client = dashboard_fixture["client"]
    token_a = dashboard_fixture["token_a"]
    case_1 = dashboard_fixture["case_1"]
    case_2 = dashboard_fixture["case_2"]

    client.headers.update({"Authorization": f"Bearer {token_a}"})
    res = client.get("/api/v1/lawyers/dashboard?days_ahead=14")
    assert res.status_code == 200
    data = res.json()

    # Metrics
    metrics = data["metrics"]
    assert metrics["active_cases_count"] == 2
    assert metrics["upcoming_hearings_count"] >= 1
    assert metrics["overdue_tasks_count"] >= 1
    assert metrics["upcoming_deadlines_count"] >= 1

    # Today's Agenda
    agenda = data["today_agenda"]
    assert len(agenda) >= 1
    agenda_titles = [item["title"] for item in agenda]
    assert any("Arguments on Interim Relief" in t for t in agenda_titles)

    # Upcoming Hearings
    hearings = data["upcoming_hearings"]
    assert len(hearings) >= 1
    h_cases = {h["case_id"] for h in hearings}
    assert str(case_1.id) in h_cases or str(case_2.id) in h_cases

    # Assigned Matters
    matters = data["assigned_matters"]
    assert len(matters) == 2
    m_ids = {m["case_id"] for m in matters}
    assert str(case_1.id) in m_ids
    assert str(case_2.id) in m_ids


def test_cross_lawyer_cross_case_isolation(dashboard_fixture):
    """
    Critical Security Test:
    Lawyer A must NEVER see Lawyer B's Case 3 hearings, tasks, deadlines, or consultations in dashboard or calendar.
    """
    client = dashboard_fixture["client"]
    token_a = dashboard_fixture["token_a"]
    case_3 = dashboard_fixture["case_3"]
    hearing_3 = dashboard_fixture["hearing_3"]
    task_3 = dashboard_fixture["task_3"]
    deadline_3 = dashboard_fixture["deadline_3"]

    client.headers.update({"Authorization": f"Bearer {token_a}"})

    # 1. Lawyer Dashboard Check
    dash_res = client.get("/api/v1/lawyers/dashboard?days_ahead=30")
    assert dash_res.status_code == 200
    dash_data = dash_res.json()

    # Assert Case 3 is not in assigned matters
    matter_ids = [m["case_id"] for m in dash_data["assigned_matters"]]
    assert str(case_3.id) not in matter_ids

    # Assert Case 3 hearings, tasks, deadlines do not leak
    all_agenda_ids = [item["id"] for item in dash_data["today_agenda"]]
    assert f"hearing-{hearing_3.id}" not in all_agenda_ids
    assert f"task-{task_3.id}" not in all_agenda_ids
    assert f"deadline-{deadline_3.id}" not in all_agenda_ids

    all_attn_titles = [item["title"] for item in dash_data["needs_attention"]]
    assert task_3.title not in all_attn_titles
    assert deadline_3.title not in all_attn_titles

    # 2. Calendar Events Check
    cal_res = client.get("/api/v1/calendar/events?timeframe=all")
    assert cal_res.status_code == 200
    cal_data = cal_res.json()

    cal_event_ids = [e["id"] for e in cal_data["events"]]
    assert f"hearing-{hearing_3.id}" not in cal_event_ids
    assert f"task-{task_3.id}" not in cal_event_ids
    assert f"deadline-{deadline_3.id}" not in cal_event_ids

    # 3. 404 Existence Masking: Attempting to query Case 3 directly in calendar
    case_3_cal_res = client.get(f"/api/v1/calendar/events?case_id={case_3.id}")
    assert case_3_cal_res.status_code == 404
    assert "not found" in case_3_cal_res.text.lower()


def test_date_range_validation_and_abuse_prevention(dashboard_fixture):
    """Verifies that invalid or excessive date ranges (> 90 days) are strictly rejected with HTTP 422."""
    client = dashboard_fixture["client"]
    token_a = dashboard_fixture["token_a"]

    client.headers.update({"Authorization": f"Bearer {token_a}"})

    # Excessive days_ahead in dashboard
    res_excess = client.get("/api/v1/lawyers/dashboard?days_ahead=91")
    assert res_excess.status_code == 422

    # Zero or negative days_ahead
    res_zero = client.get("/api/v1/lawyers/dashboard?days_ahead=0")
    assert res_zero.status_code == 422

    # Date range exceeding 90 days in dashboard
    start = date(2026, 1, 1)
    end = date(2026, 6, 1)
    res_range_abuse = client.get(f"/api/v1/lawyers/dashboard?date_from={start}&date_to={end}")
    assert res_range_abuse.status_code == 422

    # Inverted date range
    res_inverted = client.get(f"/api/v1/lawyers/dashboard?date_from={end}&date_to={start}")
    assert res_inverted.status_code == 422

    # Date range exceeding 90 days in calendar
    dt_start = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    dt_end = datetime(2026, 6, 1, tzinfo=UTC).isoformat()
    cal_excess = client.get(f"/api/v1/calendar/events?start_date={dt_start}&end_date={dt_end}")
    assert cal_excess.status_code == 422


def test_needs_attention_deterministic_engine(dashboard_fixture):
    """
    Verifies that overdue tasks, imminent hearings, approaching deadlines, and unreviewed evidence
    are deterministically flagged in needs_attention with appropriate severity and without AI.
    """
    client = dashboard_fixture["client"]
    token_a = dashboard_fixture["token_a"]
    task_overdue = dashboard_fixture["task_overdue"]
    hearing_1 = dashboard_fixture["hearing_1"]
    deadline_1 = dashboard_fixture["deadline_1"]

    client.headers.update({"Authorization": f"Bearer {token_a}"})
    res = client.get("/api/v1/lawyers/dashboard?days_ahead=14")
    assert res.status_code == 200
    data = res.json()

    needs_attention = data["needs_attention"]
    assert len(needs_attention) >= 2

    types_found = {item["item_type"] for item in needs_attention}
    assert "OVERDUE_TASK" in types_found
    assert "IMMINENT_HEARING" in types_found or "APPROACHING_DEADLINE" in types_found

    # Overdue task check
    overdue_item = next(item for item in needs_attention if item["item_type"] == "OVERDUE_TASK")
    assert overdue_item["title"] == task_overdue.title
    assert overdue_item["severity"] == "URGENT"
    assert "overdue" in overdue_item["reason"].lower()

    # Imminent hearing check
    hearing_item = next((item for item in needs_attention if item["item_type"] == "IMMINENT_HEARING"), None)
    if hearing_item:
        assert hearing_item["severity"] == "URGENT"
        assert str(hearing_1.id) in hearing_item["item_id"]


def test_unified_calendar_projections_and_filters(dashboard_fixture):
    """Verifies that unified calendar projects hearings, deadlines, tasks, and consultations with metadata."""
    client = dashboard_fixture["client"]
    token_a = dashboard_fixture["token_a"]

    client.headers.update({"Authorization": f"Bearer {token_a}"})

    # Query with bounded date range (e.g. next 7 days)
    now = datetime.now(UTC)
    s_dt = (now - timedelta(days=1)).isoformat()
    e_dt = (now + timedelta(days=7)).isoformat()

    res = client.get("/api/v1/calendar/events", params={"start_date": s_dt, "end_date": e_dt})
    assert res.status_code == 200
    data = res.json()

    events = data["events"]
    assert len(events) >= 2

    # Check projection metadata fields
    first_evt = events[0]
    assert first_evt["source_type"] in ["HEARING", "DEADLINE", "TASK", "CONSULTATION"]
    assert first_evt["start_at"] is not None
    assert first_evt["category"] is not None

    # Filter by category: hearing only
    h_res = client.get(
        "/api/v1/calendar/events",
        params={"start_date": s_dt, "end_date": e_dt, "event_type": "hearing"},
    )
    assert h_res.status_code == 200
    for evt in h_res.json()["events"]:
        assert evt["source_type"] == "HEARING"

    # Filter by priority: URGENT
    urg_res = client.get(
        "/api/v1/calendar/events",
        params={"start_date": s_dt, "end_date": e_dt, "priority": "URGENT"},
    )
    assert urg_res.status_code == 200
    for evt in urg_res.json()["events"]:
        assert evt["priority"] == "URGENT"


def test_worker_concurrency_locking(db):
    """
    Verifies that DistributedJobLock guarantees mutual exclusion between concurrent workers.
    When a lock is held, a second worker trying to run the overdue job skips cleanly.
    """
    # 1. Acquire lock manually with DistributedJobLock
    lock_name = "test_worker_concurrency_lock"
    lock1 = DistributedJobLock(lock_name, ttl_seconds=60, db=db)
    assert lock1.acquire() is True

    # 2. Second worker attempts to acquire same lock
    lock2 = DistributedJobLock(lock_name, ttl_seconds=60, db=db)
    assert lock2.acquire() is False

    # 3. Release lock1
    lock1.release()

    # 4. Now lock2 can acquire
    assert lock2.acquire() is True
    lock2.release()

    # 5. Test ReminderService with simulated lock contention
    reminder_service = ReminderService(db)
    # Hold the lock externally
    with job_lock("process_overdue_deadlines_and_tasks", ttl_seconds=60, db=db) as acquired:
        assert acquired is True
        # Now call process_overdue_deadlines_and_tasks inside ReminderService
        # It must safely detect that the lock is held and return skipped_due_to_lock=True
        result = reminder_service.process_overdue_deadlines_and_tasks()
        assert result["skipped_due_to_lock"] is True
        assert result["deadlines_marked_overdue"] == 0
