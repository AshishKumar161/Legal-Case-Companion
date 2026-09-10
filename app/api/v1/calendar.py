from datetime import UTC, datetime, timedelta
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import false, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.auth import limiter
from app.core.exceptions import ResourceNotFoundError, ValidationError
from app.models.case import Case, CaseParticipant, ParticipantStatus
from app.models.consultation import Consultation, ConsultationStatus
from app.models.court_case import CourtCase, UserFollowedCase
from app.models.task import CaseTask, TaskStatus
from app.models.user import ClientProfile, LawyerProfile, User, UserRole
from app.models.workflow import CaseDeadline, CaseHearing
from app.schemas.calendar import CalendarEventItem, CalendarEventsResponse

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/events", response_model=CalendarEventsResponse)
@limiter.limit("60/minute")
def get_calendar_events(
    request: Request,
    timeframe: Literal["all", "upcoming", "today", "this_week", "later"] = "upcoming",
    event_type: Literal["all", "hearing", "limitation", "consultation", "task"] = "all",
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    case_id: uuid.UUID | None = None,
    priority: str | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Aggregates unified authorized legal events: court hearings, statutory deadlines, consultations, and tasks.
    Enforces strict case membership authorization, bounded date range queries (max 90 days), and 404 existence masking.
    """
    now = datetime.now(UTC)
    events: list[CalendarEventItem] = []

    # 1. Date Range Validation
    s_dt: datetime | None = None
    e_dt: datetime | None = None
    if start_date:
        s_dt = start_date if start_date.tzinfo else start_date.replace(tzinfo=UTC)
    if end_date:
        e_dt = end_date if end_date.tzinfo else end_date.replace(tzinfo=UTC)

    if s_dt and e_dt:
        if e_dt < s_dt:
            raise ValidationError("end_date cannot be earlier than start_date.")
        if (e_dt - s_dt).days > 90:
            raise ValidationError("Date range cannot exceed 90 days.")

    # 2. Case Authorization Scoping & 404 Masking
    user_case_ids: list[uuid.UUID] = []
    if current_user:
        user_case_ids = [
            cp.case_id
            for cp in db.query(CaseParticipant.case_id)
            .filter(CaseParticipant.user_id == current_user.id, CaseParticipant.status == ParticipantStatus.ACTIVE)
            .all()
        ]

    # If specific case_id requested, enforce 404 existence masking if user lacks access
    target_case_ids: list[uuid.UUID] = user_case_ids
    if case_id:
        if not current_user or (current_user.role != UserRole.ADMIN and case_id not in user_case_ids):
            raise ResourceNotFoundError("Case not found.")
        target_case_ids = [case_id]

    # Pre-fetch case titles map
    case_titles_map: dict[uuid.UUID, str] = {}
    if target_case_ids:
        for c_rec in db.query(Case.id, Case.title).filter(Case.id.in_(target_case_ids), Case.deleted_at.is_(None)).all():
            case_titles_map[c_rec[0]] = c_rec[1]

    # 3. Court Hearings Projection
    if event_type in ("all", "hearing"):
        hearings_query = db.query(CaseHearing).filter(CaseHearing.deleted_at.is_(None))
        if target_case_ids:
            hearings_query = hearings_query.filter(CaseHearing.case_id.in_(target_case_ids))
        elif not current_user or current_user.role != UserRole.ADMIN:
            hearings_query = hearings_query.filter(false())

        hearings = hearings_query.all()
        for h in hearings:
            h_dt = h.hearing_at.replace(tzinfo=UTC) if h.hearing_at.tzinfo is None else h.hearing_at
            case_title = case_titles_map.get(h.case_id, "Active Court Matter")

            month_str = h_dt.strftime("%b").upper()
            day_str = h_dt.strftime("%d")
            time_display = h_dt.strftime("%d %b · %I:%M %p IST")

            is_urgent = (h_dt - now).total_seconds() < 86400 * 2 and h_dt >= now

            events.append(
                CalendarEventItem(
                    id=f"hearing-{h.id}",
                    type="hearing",
                    type_label="Court Hearing",
                    scheduled_at=h_dt,
                    month=month_str,
                    day=day_str,
                    time_display=time_display,
                    title=h.purpose or "Listed Court Hearing",
                    case_id=h.case_id,
                    case_name=case_title,
                    case_ref=h.court_name,
                    forum=f"{h.court_name} {f'· {h.bench_or_coram}' if h.bench_or_coram else ''}",
                    action_tip=h.notes or "Oral arguments listed before court. Coordinate with your advocate for required filings.",
                    technical_term="Listed on Cause List",
                    source=f"eCourts Cause List · {h.source_reference or 'Court Board'}",
                    action_label="View Case",
                    action_href=f"/cases/{h.case_id}?tab=hearings",
                    is_urgent=is_urgent,
                    source_type="HEARING",
                    source_id=str(h.id),
                    start_at=h_dt,
                    end_at=h_dt + timedelta(hours=1),
                    status=h.status.value if hasattr(h.status, "value") else str(h.status),
                    priority="URGENT" if is_urgent else "HIGH",
                    category="Court Hearing",
                    lawyer_details={
                        "court": h.court_name,
                        "bench": h.bench_or_coram or "Single Bench",
                        "status": h.status.value if hasattr(h.status, "value") else str(h.status),
                        "is_confirmed": h.is_confirmed,
                    },
                )
            )

        # Tracked eCourts CourtCases
        if not case_id:
            court_cases_query = db.query(CourtCase).filter(
                CourtCase.next_hearing_date.isnot(None), CourtCase.deleted_at.is_(None)
            )
            if current_user:
                followed_case_ids = [
                    f.court_case_id
                    for f in db.query(UserFollowedCase.court_case_id)
                    .filter(UserFollowedCase.user_id == current_user.id)
                    .all()
                ]
                if followed_case_ids:
                    court_cases_query = court_cases_query.filter(
                        or_(CourtCase.id.in_(followed_case_ids), CourtCase.case_id.in_(user_case_ids))
                    )
            court_cases = court_cases_query.all()
            for cc in court_cases:
                if not cc.next_hearing_date:
                    continue
                cc_dt = cc.next_hearing_date.replace(tzinfo=UTC) if cc.next_hearing_date.tzinfo is None else cc.next_hearing_date
                month_str = cc_dt.strftime("%b").upper()
                day_str = cc_dt.strftime("%d")
                time_display = cc_dt.strftime("%d %b · %I:%M %p IST")

                is_urgent = (cc_dt - now).total_seconds() < 86400 * 2 and cc_dt >= now

                events.append(
                    CalendarEventItem(
                        id=f"court-case-{cc.id}",
                        type="hearing",
                        type_label="Court Hearing",
                        scheduled_at=cc_dt,
                        month=month_str,
                        day=day_str,
                        time_display=time_display,
                        title=cc.next_hearing_purpose or "Court Hearing & Proceedings",
                        case_id=cc.case_id,
                        case_name=f"{cc.petitioner} v. {cc.respondent}",
                        case_ref=cc.case_number,
                        forum=f"{cc.court_name} {f'· {cc.court_room}' if cc.court_room else ''} {f'({cc.item_number})' if cc.item_number else ''}",
                        action_tip="Follow listed matter on the daily cause list. Advocate will appear for submissions.",
                        technical_term=cc.technical_status or "Judgment Reserved",
                        source=f"eCourts Cause List · {cc.court_name}",
                        action_label="View Cause List",
                        action_href="/court-tracking",
                        is_urgent=is_urgent,
                        source_type="HEARING",
                        source_id=str(cc.id),
                        start_at=cc_dt,
                        end_at=cc_dt + timedelta(hours=1),
                        status=cc.technical_status or "SCHEDULED",
                        priority="URGENT" if is_urgent else "HIGH",
                        category="Court Hearing",
                        lawyer_details={
                            "court": cc.court_name,
                            "court_room": cc.court_room or "Room 4",
                            "item_number": cc.item_number or "Item 14",
                            "bench": cc.bench or "Hon'ble Court",
                            "status": cc.technical_status,
                            "petitioner_advocate": cc.petitioner_advocate,
                            "respondent_advocate": cc.respondent_advocate,
                        },
                    )
                )

    # 4. Statutory Limitations & Deadlines Projection
    if event_type in ("all", "limitation"):
        deadlines_query = db.query(CaseDeadline).filter(CaseDeadline.deleted_at.is_(None))
        if target_case_ids:
            deadlines_query = deadlines_query.filter(CaseDeadline.case_id.in_(target_case_ids))
        elif not current_user or current_user.role != UserRole.ADMIN:
            deadlines_query = deadlines_query.filter(false())

        deadlines = deadlines_query.all()
        for d in deadlines:
            d_dt = d.deadline_at.replace(tzinfo=UTC) if d.deadline_at.tzinfo is None else d.deadline_at
            case_title = case_titles_map.get(d.case_id, "Active Matter")

            month_str = d_dt.strftime("%b").upper()
            day_str = d_dt.strftime("%d")
            time_display = d_dt.strftime("%d %b · %I:%M %p IST")

            is_urgent = (d_dt - now).total_seconds() < 86400 * 3 and d_dt >= now

            events.append(
                CalendarEventItem(
                    id=f"deadline-{d.id}",
                    type="limitation",
                    type_label="Limitation / Cutoff",
                    scheduled_at=d_dt,
                    month=month_str,
                    day=day_str,
                    time_display=time_display,
                    title=d.title,
                    case_id=d.case_id,
                    case_name=case_title,
                    case_ref="Statutory Cutoff",
                    forum="Statutory Limitation / Registry Rules",
                    action_tip=d.description or "Mandatory filing deadline. Ensure counsel completes submissions prior to cutoff.",
                    technical_term="Limitation Period",
                    source=f"Limitation Act / Procedural Rule · {d.source_reference or 'Official Rule'}",
                    action_label="Review Case",
                    action_href=f"/cases/{d.case_id}?tab=tasks",
                    is_urgent=is_urgent,
                    source_type="DEADLINE",
                    source_id=str(d.id),
                    start_at=d_dt,
                    end_at=d_dt,
                    status=d.status.value if hasattr(d.status, "value") else str(d.status),
                    priority="URGENT" if is_urgent else "HIGH",
                    category="Statutory Limitation",
                    lawyer_details={
                        "deadline_type": d.deadline_type.value if hasattr(d.deadline_type, "value") else str(d.deadline_type),
                        "status": d.status.value if hasattr(d.status, "value") else str(d.status),
                    },
                )
            )

    # 5. Lawyer Consultations Projection
    if event_type in ("all", "consultation") and current_user and not case_id:
        client_prof = db.query(ClientProfile.id).filter(ClientProfile.user_id == current_user.id).scalar()
        lawyer_prof = db.query(LawyerProfile.id).filter(LawyerProfile.user_id == current_user.id).scalar()
        consult_filters = []
        if client_prof:
            consult_filters.append(Consultation.client_id == client_prof)
        if lawyer_prof:
            consult_filters.append(Consultation.lawyer_id == lawyer_prof)

        consultations = []
        if consult_filters:
            consultations = (
                db.query(Consultation)
                .filter(
                    or_(*consult_filters),
                    Consultation.scheduled_at.isnot(None),
                    Consultation.status.in_([ConsultationStatus.REQUESTED, ConsultationStatus.SCHEDULED, ConsultationStatus.IN_PROGRESS]),
                )
                .all()
            )
        for c in consultations:
            c_dt = c.scheduled_at.replace(tzinfo=UTC) if c.scheduled_at.tzinfo is None else c.scheduled_at
            month_str = c_dt.strftime("%b").upper()
            day_str = c_dt.strftime("%d")
            time_display = c_dt.strftime("%d %b · %I:%M %p IST")

            is_urgent = (c_dt - now).total_seconds() < 86400 * 2 and c_dt >= now

            events.append(
                CalendarEventItem(
                    id=f"consultation-{c.id}",
                    type="consultation",
                    type_label="Video Consultation",
                    scheduled_at=c_dt,
                    month=month_str,
                    day=day_str,
                    time_display=time_display,
                    title=f"Legal Strategy Consultation ({c.duration_minutes} mins)",
                    case_id=c.case_id,
                    case_name="Counsel Case Strategy",
                    case_ref=f"Consultation #{str(c.id)[:8]}",
                    forum="Secure Video Room (LCC Encrypted WebRTC)",
                    action_tip="Review any marked documents or evidence gaps before joining the session with counsel.",
                    technical_term="Advocate Consultation",
                    source="Confirmed Appointment · LCC Escrow",
                    action_label="Join Consultation",
                    action_href=f"/consultations/{c.id}/room",
                    is_urgent=is_urgent,
                    source_type="CONSULTATION",
                    source_id=str(c.id),
                    start_at=c_dt,
                    end_at=c_dt + timedelta(minutes=c.duration_minutes),
                    status=c.status.value if hasattr(c.status, "value") else str(c.status),
                    priority="HIGH",
                    category="Consultation",
                    lawyer_details={
                        "duration_minutes": c.duration_minutes,
                        "fee": c.fee_amount,
                        "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                    },
                )
            )

    # 6. Tasks Projection
    if event_type in ("all", "task") and current_user:
        tasks_query = db.query(CaseTask).filter(
            CaseTask.deleted_at.is_(None),
            CaseTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]),
            CaseTask.due_date.isnot(None),
        )
        if target_case_ids:
            tasks_query = tasks_query.filter(
                or_(CaseTask.case_id.in_(target_case_ids), CaseTask.owner_user_id == current_user.id)
            )
        else:
            tasks_query = tasks_query.filter(CaseTask.owner_user_id == current_user.id)

        tasks = tasks_query.all()
        for t in tasks:
            if t.due_date is None:
                continue
            t_dt = t.due_date.replace(tzinfo=UTC) if t.due_date.tzinfo is None else t.due_date
            month_str = t_dt.strftime("%b").upper()
            day_str = t_dt.strftime("%d")
            time_display = t_dt.strftime("%d %b · %I:%M %p IST")

            is_urgent = (t_dt - now).total_seconds() < 86400 * 2 and t_dt >= now
            case_title = case_titles_map.get(t.case_id, "Active Matter")

            events.append(
                CalendarEventItem(
                    id=f"task-{t.id}",
                    type="task",
                    type_label="Advocate Request",
                    scheduled_at=t_dt,
                    month=month_str,
                    day=day_str,
                    time_display=time_display,
                    title=t.title,
                    case_id=t.case_id,
                    case_name=case_title,
                    case_ref=f"Task #{str(t.id)[:8]}",
                    forum="Matter Vault / Document Compliance",
                    action_tip=t.description or "Provide requested documents or compliance items to counsel.",
                    technical_term="Client Action Item",
                    source="Advocate Chamber Request",
                    action_label="Upload to Vault",
                    action_href=f"/cases/{t.case_id}?tab=tasks",
                    is_urgent=is_urgent,
                    source_type="TASK",
                    source_id=str(t.id),
                    start_at=t_dt,
                    end_at=t_dt,
                    status=t.status.value if hasattr(t.status, "value") else str(t.status),
                    priority=t.priority.value if hasattr(t.priority, "value") else str(t.priority),
                    category="Task",
                    lawyer_details={
                        "priority": t.priority.value if hasattr(t.priority, "value") else str(t.priority),
                        "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                    },
                )
            )

    # 7. Apply Priority and Status Filters if passed
    if priority:
        events = [e for e in events if e.priority and e.priority.upper() == priority.upper()]
    if status:
        events = [e for e in events if e.status and e.status.upper() == status.upper()]

    # 8. Filter by Date Range or Timeframe
    filtered_events: list[CalendarEventItem] = []
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    week_end = today_start + timedelta(days=7)

    range_start = s_dt
    range_end = e_dt

    if s_dt or e_dt:
        for evt in events:
            if s_dt and evt.scheduled_at < s_dt:
                continue
            if e_dt and evt.scheduled_at > e_dt:
                continue
            filtered_events.append(evt)
    else:
        for evt in events:
            if timeframe == "today":
                if today_start <= evt.scheduled_at < today_end:
                    filtered_events.append(evt)
            elif timeframe == "this_week":
                if today_start <= evt.scheduled_at <= week_end:
                    filtered_events.append(evt)
            elif timeframe == "later":
                if evt.scheduled_at > week_end:
                    filtered_events.append(evt)
            elif timeframe == "upcoming":
                if evt.scheduled_at >= now - timedelta(hours=12):
                    filtered_events.append(evt)
            else:
                filtered_events.append(evt)

    # Sort chronologically
    filtered_events.sort(key=lambda x: x.scheduled_at)

    # Determine next attention event
    next_attention = None
    upcoming_candidates = [e for e in filtered_events if e.scheduled_at >= now - timedelta(hours=2)]
    if upcoming_candidates:
        urgent_candidates = [e for e in upcoming_candidates if e.is_urgent or e.type == "hearing"]
        next_attention = urgent_candidates[0] if urgent_candidates else upcoming_candidates[0]

    paginated = filtered_events[skip : skip + limit]

    return CalendarEventsResponse(
        events=paginated,
        total=len(filtered_events),
        next_attention_event=next_attention,
        timeframe=timeframe if not (s_dt or e_dt) else "custom",
        range_start=range_start,
        range_end=range_end,
    )
