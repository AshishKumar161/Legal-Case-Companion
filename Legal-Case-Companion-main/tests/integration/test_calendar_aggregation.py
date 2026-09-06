from datetime import UTC, datetime, timedelta
import pytest

from app.core.identifiers import generate_uuid7
from app.core.security import create_access_token
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole, ParticipantStatus
from app.models.task import CaseTask, TaskPriority, TaskStatus
from app.models.user import AccountStatus, User, UserRole
from app.models.workflow import CaseDeadline, CaseHearing, DeadlineStatus, DeadlineType, HearingStatus


@pytest.fixture
def calendar_user(client, db):
    user = db.query(User).filter(User.email == "test_calendar_user@example.com").first()
    if not user:
        user = User(
            id=generate_uuid7(),
            email="test_calendar_user@example.com",
            role=UserRole.CLIENT,
            account_status=AccountStatus.ACTIVE,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Create a test case
    case = Case(
        id=generate_uuid7(),
        title="Calendar Verification Matter",
        description="Matter for testing calendar aggregation",
        status=CaseStatus.OPEN,
    )
    db.add(case)
    db.flush()

    # Add user as participant
    participant = CaseParticipant(
        id=generate_uuid7(),
        case_id=case.id,
        user_id=user.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(participant)

    # Add a hearing
    hearing = CaseHearing(
        id=generate_uuid7(),
        case_id=case.id,
        court_name="Delhi High Court",
        hearing_at=datetime.now(UTC) + timedelta(days=2),
        purpose="Final Arguments",
        status=HearingStatus.SCHEDULED,
        bench_or_coram="Court Room 4",
    )
    db.add(hearing)

    # Add a deadline
    deadline = CaseDeadline(
        id=generate_uuid7(),
        case_id=case.id,
        title="Filing of Rejoinder Affidavit",
        deadline_at=datetime.now(UTC) + timedelta(days=5),
        deadline_type=DeadlineType.COURT_FILING,
        status=DeadlineStatus.UPCOMING,
    )
    db.add(deadline)

    # Add a task
    task = CaseTask(
        id=generate_uuid7(),
        case_id=case.id,
        title="Scan Original Title Deeds",
        owner_user_id=user.id,
        due_date=datetime.now(UTC) + timedelta(days=1),
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
    )
    db.add(task)

    db.commit()

    token = create_access_token(subject=str(user.id), role=user.role.value)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client, user.id, case.id


def test_calendar_events_aggregation(calendar_user):
    authed, user_id, case_id = calendar_user

    res = authed.get("/api/v1/calendar/events?timeframe=all")
    assert res.status_code == 200
    data = res.json()
    assert "events" in data
    assert data["total"] >= 3

    event_types = {e["type"] for e in data["events"]}
    assert "hearing" in event_types
    assert "limitation" in event_types
    assert "task" in event_types

    assert data["next_attention_event"] is not None


def test_calendar_events_timeframe_filtering(calendar_user):
    authed, user_id, case_id = calendar_user

    # upcoming
    res = authed.get("/api/v1/calendar/events?timeframe=upcoming")
    assert res.status_code == 200
    assert len(res.json()["events"]) >= 1

    # type filter: hearing only
    res_hearing = authed.get("/api/v1/calendar/events?timeframe=all&event_type=hearing")
    assert res_hearing.status_code == 200
    for e in res_hearing.json()["events"]:
        assert e["type"] == "hearing"
