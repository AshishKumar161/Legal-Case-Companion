from datetime import UTC, date, datetime, timedelta
import uuid
from typing import Any

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.models.bundle import EvidenceBundle, BundleStatus
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantStatus
from app.models.consultation import Consultation, ConsultationStatus
from app.models.evidence import CaseExhibit, Evidence, EvidenceStatus
from app.models.task import CaseTask, TaskPriority, TaskStatus
from app.models.user import LawyerProfile, User
from app.models.workflow import CaseDeadline, CaseHearing, DeadlineStatus, HearingStatus
from app.schemas.lawyer_dashboard import (
    AssignedMatterSummary,
    LawyerDashboardResponse,
    LawyerOperationalMetrics,
    OperationalAttentionItem,
    TodayAgendaItem,
    UpcomingDeadlineSummary,
    UpcomingHearingSummary,
)
from app.services.notification_service import NotificationService


class LawyerDashboardService:
    """
    Server-side aggregation service for Advocate Operational Dashboard.
    Strictly enforces case membership scoping, bounded SQL queries, and deterministic zero-AI operational attention.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.notification_service = NotificationService(db)

    def get_operational_dashboard(
        self,
        current_user: User,
        days_ahead: int = 7,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> LawyerDashboardResponse:
        # 1. Enforce query date range boundaries
        if days_ahead < 1 or days_ahead > 90:
            raise ValidationError("days_ahead must be between 1 and 90 days.")

        if date_from and date_to:
            if date_to < date_from:
                raise ValidationError("date_to cannot be earlier than date_from.")
            if (date_to - date_from).days > 90:
                raise ValidationError("Date range cannot exceed 90 days.")

        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        window_end = today_start + timedelta(days=days_ahead)

        if date_from:
            today_start = datetime.combine(date_from, datetime.min.time(), tzinfo=UTC)
        if date_to:
            window_end = datetime.combine(date_to, datetime.max.time(), tzinfo=UTC)

        # 2. Strict User / Lawyer Scoping
        # Only cases where current user is an ACTIVE participant
        user_case_ids: list[uuid.UUID] = [
            cp.case_id
            for cp in self.db.query(CaseParticipant.case_id)
            .filter(
                CaseParticipant.user_id == current_user.id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .all()
        ]

        lawyer_profile_id: uuid.UUID | None = (
            self.db.query(LawyerProfile.id)
            .filter(LawyerProfile.user_id == current_user.id, LawyerProfile.deleted_at.is_(None))
            .scalar()
        )

        if not user_case_ids and not lawyer_profile_id:
            # Return empty response if lawyer has no active assigned matters
            unread_count = self.notification_service.get_unread_count(current_user)
            return LawyerDashboardResponse(
                metrics=LawyerOperationalMetrics(unread_notifications_count=unread_count),
                today_agenda=[],
                needs_attention=[],
                upcoming_hearings=[],
                upcoming_deadlines=[],
                high_priority_tasks=[],
                assigned_matters=[],
                range_days=days_ahead,
            )

        # Pre-fetch case titles map to avoid N+1
        cases_map: dict[uuid.UUID, Case] = {}
        if user_case_ids:
            active_cases = (
                self.db.query(Case)
                .filter(Case.id.in_(user_case_ids), Case.deleted_at.is_(None))
                .all()
            )
            cases_map = {c.id: c for c in active_cases}

        # ---------------------------------------------------------------------
        # 3. TODAY'S AGENDA (Hearings, Deadlines, Tasks, Consultations)
        # ---------------------------------------------------------------------
        today_agenda: list[TodayAgendaItem] = []

        # A. Today's Hearings
        if user_case_ids:
            today_hearings = (
                self.db.query(CaseHearing)
                .filter(
                    CaseHearing.case_id.in_(user_case_ids),
                    CaseHearing.deleted_at.is_(None),
                    CaseHearing.hearing_at >= today_start,
                    CaseHearing.hearing_at < today_end,
                    CaseHearing.status == HearingStatus.SCHEDULED,
                )
                .all()
            )
            for h in today_hearings:
                c = cases_map.get(h.case_id)
                h_dt = h.hearing_at.replace(tzinfo=UTC) if h.hearing_at.tzinfo is None else h.hearing_at
                today_agenda.append(
                    TodayAgendaItem(
                        id=f"hearing-{h.id}",
                        event_type="HEARING",
                        title=f"Court Hearing: {h.purpose or 'Listed Proceedings'}",
                        scheduled_at=h_dt,
                        time_display=h_dt.strftime("%I:%M %p IST"),
                        case_id=h.case_id,
                        case_title=c.title if c else "Assigned Matter",
                        court_info=f"{h.court_name} {f'· {h.bench_or_coram}' if h.bench_or_coram else ''}",
                        status=h.status.value,
                        priority="URGENT",
                        action_href=f"/cases/{h.case_id}?tab=hearings",
                        action_label="View Hearing",
                        is_urgent=True,
                    )
                )

        # B. Today's Deadlines & Overdue Deadlines
        if user_case_ids:
            active_deadlines = (
                self.db.query(CaseDeadline)
                .filter(
                    CaseDeadline.case_id.in_(user_case_ids),
                    CaseDeadline.deleted_at.is_(None),
                    CaseDeadline.status.in_([DeadlineStatus.UPCOMING, DeadlineStatus.DUE, DeadlineStatus.OVERDUE]),
                    CaseDeadline.deadline_at < today_end,
                )
                .all()
            )
            for d in active_deadlines:
                c = cases_map.get(d.case_id)
                d_dt = d.deadline_at.replace(tzinfo=UTC) if d.deadline_at.tzinfo is None else d.deadline_at
                is_overdue = d_dt < now or d.status == DeadlineStatus.OVERDUE
                today_agenda.append(
                    TodayAgendaItem(
                        id=f"deadline-{d.id}",
                        event_type="DEADLINE",
                        title=f"Deadline: {d.title}",
                        scheduled_at=d_dt,
                        time_display=d_dt.strftime("%d %b · %I:%M %p IST") if is_overdue else d_dt.strftime("%I:%M %p IST"),
                        case_id=d.case_id,
                        case_title=c.title if c else "Assigned Matter",
                        court_info=f"Source: {d.source_type.value if hasattr(d.source_type, 'value') else str(d.source_type)}",
                        status="OVERDUE" if is_overdue else d.status.value,
                        priority="URGENT" if is_overdue else "HIGH",
                        action_href=f"/cases/{d.case_id}?tab=tasks",
                        action_label="Review Deadline",
                        is_urgent=True,
                    )
                )

        # C. Today's Tasks & Overdue Tasks
        if user_case_ids:
            active_tasks = (
                self.db.query(CaseTask)
                .filter(
                    CaseTask.case_id.in_(user_case_ids),
                    CaseTask.deleted_at.is_(None),
                    CaseTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]),
                    CaseTask.due_date.isnot(None),
                    CaseTask.due_date < today_end,
                )
                .all()
            )
            for t in active_tasks:
                c = cases_map.get(t.case_id)
                t_dt = t.due_date.replace(tzinfo=UTC) if t.due_date.tzinfo is None else t.due_date
                is_overdue = t_dt < now
                today_agenda.append(
                    TodayAgendaItem(
                        id=f"task-{t.id}",
                        event_type="TASK",
                        title=f"Task: {t.title}",
                        scheduled_at=t_dt,
                        time_display=t_dt.strftime("%d %b · %I:%M %p IST") if is_overdue else t_dt.strftime("%I:%M %p IST"),
                        case_id=t.case_id,
                        case_title=c.title if c else "Assigned Matter",
                        court_info=None,
                        status=t.status.value,
                        priority="URGENT" if is_overdue else (t.priority.value if hasattr(t.priority, "value") else str(t.priority)),
                        action_href=f"/cases/{t.case_id}?tab=tasks",
                        action_label="Open Task",
                        is_urgent=is_overdue or t.priority == TaskPriority.URGENT,
                    )
                )

        # D. Today's Consultations
        if lawyer_profile_id:
            today_consultations = (
                self.db.query(Consultation)
                .filter(
                    Consultation.lawyer_id == lawyer_profile_id,
                    Consultation.scheduled_at >= today_start,
                    Consultation.scheduled_at < today_end,
                    Consultation.status.in_([
                        ConsultationStatus.REQUESTED,
                        ConsultationStatus.SCHEDULED,
                        ConsultationStatus.IN_PROGRESS,
                    ]),
                )
                .all()
            )
            for cs in today_consultations:
                cs_dt = cs.scheduled_at.replace(tzinfo=UTC) if cs.scheduled_at.tzinfo is None else cs.scheduled_at
                c = cases_map.get(cs.case_id) if cs.case_id else None
                today_agenda.append(
                    TodayAgendaItem(
                        id=f"consultation-{cs.id}",
                        event_type="CONSULTATION",
                        title=f"Video Consultation ({cs.duration_minutes}m)",
                        scheduled_at=cs_dt,
                        time_display=cs_dt.strftime("%I:%M %p IST"),
                        case_id=cs.case_id,
                        case_title=c.title if c else "Direct Consultation",
                        court_info="Secure Encrypted Room",
                        status=cs.status.value,
                        priority="HIGH",
                        action_href=f"/consultations/{cs.id}/room",
                        action_label="Join Room",
                        is_urgent=abs((cs_dt - now).total_seconds()) < 3600,
                    )
                )

        # Sort agenda chronologically
        today_agenda.sort(key=lambda x: x.scheduled_at)

        # ---------------------------------------------------------------------
        # 4. DETERMINISTIC "NEEDS ATTENTION" RADAR (NO AI)
        # ---------------------------------------------------------------------
        needs_attention: list[OperationalAttentionItem] = []

        # Overdue Tasks
        if user_case_ids:
            overdue_tasks = (
                self.db.query(CaseTask)
                .filter(
                    CaseTask.case_id.in_(user_case_ids),
                    CaseTask.deleted_at.is_(None),
                    CaseTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]),
                    CaseTask.due_date.isnot(None),
                    CaseTask.due_date < now,
                )
                .order_by(CaseTask.due_date.asc())
                .limit(10)
                .all()
            )
            for ot in overdue_tasks:
                c = cases_map.get(ot.case_id)
                ot_dt = ot.due_date.replace(tzinfo=UTC) if ot.due_date.tzinfo is None else ot.due_date
                hours_past = int((now - ot_dt).total_seconds() // 3600)
                needs_attention.append(
                    OperationalAttentionItem(
                        item_id=f"attn-task-{ot.id}",
                        item_type="OVERDUE_TASK",
                        title=ot.title,
                        case_id=ot.case_id,
                        case_title=c.title if c else "Active Matter",
                        severity="URGENT",
                        reason=f"Task is overdue by {hours_past} hours (due {ot_dt.strftime('%d %b %Y')}). Action required.",
                        action_href=f"/cases/{ot.case_id}?tab=tasks",
                        action_label="Resolve Task",
                        due_at=ot_dt,
                    )
                )

        # Overdue Deadlines
        if user_case_ids:
            overdue_deadlines_list = (
                self.db.query(CaseDeadline)
                .filter(
                    CaseDeadline.case_id.in_(user_case_ids),
                    CaseDeadline.deleted_at.is_(None),
                    CaseDeadline.status.in_([DeadlineStatus.UPCOMING, DeadlineStatus.DUE, DeadlineStatus.OVERDUE]),
                    CaseDeadline.deadline_at < now,
                )
                .order_by(CaseDeadline.deadline_at.asc())
                .limit(10)
                .all()
            )
            for od in overdue_deadlines_list:
                c = cases_map.get(od.case_id)
                od_dt = od.deadline_at.replace(tzinfo=UTC) if od.deadline_at.tzinfo is None else od.deadline_at
                days_past = max(1, int((now - od_dt).total_seconds() // 86400))
                needs_attention.append(
                    OperationalAttentionItem(
                        item_id=f"attn-dl-{od.id}",
                        item_type="OVERDUE_DEADLINE",
                        title=od.title,
                        case_id=od.case_id,
                        case_title=c.title if c else "Active Matter",
                        severity="URGENT",
                        reason=f"Compliance / statutory deadline expired {days_past} day(s) ago ({od_dt.strftime('%d %b %Y')}).",
                        action_href=f"/cases/{od.case_id}?tab=tasks",
                        action_label="Review Deadline",
                        due_at=od_dt,
                    )
                )

        # Imminent Hearings within 24 Hours
        if user_case_ids:
            imminent_hearings = (
                self.db.query(CaseHearing)
                .filter(
                    CaseHearing.case_id.in_(user_case_ids),
                    CaseHearing.deleted_at.is_(None),
                    CaseHearing.status == HearingStatus.SCHEDULED,
                    CaseHearing.hearing_at >= now,
                    CaseHearing.hearing_at <= now + timedelta(hours=24),
                )
                .all()
            )
            for ih in imminent_hearings:
                c = cases_map.get(ih.case_id)
                ih_dt = ih.hearing_at.replace(tzinfo=UTC) if ih.hearing_at.tzinfo is None else ih.hearing_at
                hours_left = max(1, int((ih_dt - now).total_seconds() // 3600))
                needs_attention.append(
                    OperationalAttentionItem(
                        item_id=f"attn-hearing-{ih.id}",
                        item_type="IMMINENT_HEARING",
                        title=f"{ih.court_name}: {ih.purpose or 'Listed Hearing'}",
                        case_id=ih.case_id,
                        case_title=c.title if c else "Active Matter",
                        severity="URGENT",
                        reason=f"Hearing scheduled in {hours_left} hours before {ih.court_name}. Ensure evidentiary bundle is finalized.",
                        action_href=f"/cases/{ih.case_id}?tab=hearings",
                        action_label="Check Bundle",
                        due_at=ih_dt,
                    )
                )

        # Approaching Deadlines within 48 Hours
        if user_case_ids:
            approaching_deadlines = (
                self.db.query(CaseDeadline)
                .filter(
                    CaseDeadline.case_id.in_(user_case_ids),
                    CaseDeadline.deleted_at.is_(None),
                    CaseDeadline.status.in_([DeadlineStatus.UPCOMING, DeadlineStatus.DUE]),
                    CaseDeadline.deadline_at >= now,
                    CaseDeadline.deadline_at <= now + timedelta(hours=48),
                )
                .all()
            )
            for ad in approaching_deadlines:
                c = cases_map.get(ad.case_id)
                ad_dt = ad.deadline_at.replace(tzinfo=UTC) if ad.deadline_at.tzinfo is None else ad.deadline_at
                hours_left = max(1, int((ad_dt - now).total_seconds() // 3600))
                needs_attention.append(
                    OperationalAttentionItem(
                        item_id=f"attn-app-dl-{ad.id}",
                        item_type="APPROACHING_DEADLINE",
                        title=ad.title,
                        case_id=ad.case_id,
                        case_title=c.title if c else "Active Matter",
                        severity="WARNING",
                        reason=f"Filing due in {hours_left} hours ({ad_dt.strftime('%d %b %Y')}). Prepare submissions.",
                        action_href=f"/cases/{ad.case_id}?tab=tasks",
                        action_label="Prepare Filing",
                        due_at=ad_dt,
                    )
                )

        # Unreviewed Evidence in Active Cases
        if user_case_ids:
            unreviewed_evidence_counts = (
                self.db.query(Evidence.case_id, func.count(Evidence.id))
                .filter(
                    Evidence.case_id.in_(user_case_ids),
                    Evidence.deleted_at.is_(None),
                    Evidence.status.in_([EvidenceStatus.QUARANTINED, EvidenceStatus.UPLOADING]),
                )
                .group_by(Evidence.case_id)
                .all()
            )
            for cid, count in unreviewed_evidence_counts:
                if count > 0:
                    c = cases_map.get(cid)
                    needs_attention.append(
                        OperationalAttentionItem(
                            item_id=f"attn-ev-{cid}",
                            item_type="UNREVIEWED_EVIDENCE",
                            title=f"{count} Unreviewed Evidence Item(s)",
                            case_id=cid,
                            case_title=c.title if c else "Active Matter",
                            severity="INFO",
                            reason=f"{count} uploaded evidence item(s) pending chain-of-custody verification.",
                            action_href=f"/cases/{cid}/evidence",
                            action_label="Review Evidence",
                            due_at=None,
                        )
                    )

        # Sort needs attention by severity (URGENT -> WARNING -> INFO)
        severity_order = {"URGENT": 0, "WARNING": 1, "INFO": 2}
        needs_attention.sort(key=lambda x: severity_order.get(x.severity, 3))

        # ---------------------------------------------------------------------
        # 5. UPCOMING HEARINGS WITH PREPARATION CONTEXT (Next 7 - 90 Days)
        # ---------------------------------------------------------------------
        upcoming_hearings_list: list[UpcomingHearingSummary] = []
        if user_case_ids:
            hearings_query = (
                self.db.query(CaseHearing)
                .filter(
                    CaseHearing.case_id.in_(user_case_ids),
                    CaseHearing.deleted_at.is_(None),
                    CaseHearing.hearing_at >= now,
                    CaseHearing.hearing_at <= window_end,
                    CaseHearing.status == HearingStatus.SCHEDULED,
                )
                .order_by(CaseHearing.hearing_at.asc())
                .limit(20)
                .all()
            )

            # Pre-fetch task counts, exhibits, and bundle statuses
            hearing_ids = [h.id for h in hearings_query]
            task_counts: dict[uuid.UUID, tuple[int, int]] = {}
            bundle_statuses: dict[uuid.UUID, str] = {}

            if hearing_ids:
                tasks_data = (
                    self.db.query(
                        CaseTask.linked_hearing_id,
                        func.count(CaseTask.id),
                        func.sum(case((CaseTask.status == TaskStatus.COMPLETED, 1), else_=0)),
                    )
                    .filter(
                        CaseTask.linked_hearing_id.in_(hearing_ids),
                        CaseTask.deleted_at.is_(None),
                    )
                    .group_by(CaseTask.linked_hearing_id)
                    .all()
                )
                for hid, total, comp in tasks_data:
                    task_counts[hid] = (total or 0, int(comp or 0))

                bundles = (
                    self.db.query(EvidenceBundle.hearing_id, EvidenceBundle.status)
                    .filter(
                        EvidenceBundle.hearing_id.in_(hearing_ids),
                        EvidenceBundle.deleted_at.is_(None),
                    )
                    .all()
                )
                for hid, b_status in bundles:
                    if hid:
                        bundle_statuses[hid] = b_status.value if hasattr(b_status, "value") else str(b_status)

            # Exhibit counts per case
            exhibit_counts: dict[uuid.UUID, int] = {}
            if user_case_ids:
                ex_data = (
                    self.db.query(CaseExhibit.case_id, func.count(CaseExhibit.id))
                    .filter(
                        CaseExhibit.case_id.in_(user_case_ids),
                        CaseExhibit.deleted_at.is_(None),
                    )
                    .group_by(CaseExhibit.case_id)
                    .all()
                )
                for cid, count in ex_data:
                    exhibit_counts[cid] = count or 0

            for h in hearings_query:
                c = cases_map.get(h.case_id)
                h_dt = h.hearing_at.replace(tzinfo=UTC) if h.hearing_at.tzinfo is None else h.hearing_at
                t_total, t_comp = task_counts.get(h.id, (0, 0))
                upcoming_hearings_list.append(
                    UpcomingHearingSummary(
                        hearing_id=h.id,
                        case_id=h.case_id,
                        case_title=c.title if c else "Active Matter",
                        court_name=h.court_name,
                        courtroom=getattr(h, "court_number", None),
                        bench=h.bench_or_coram,
                        purpose=h.purpose,
                        hearing_at=h_dt,
                        time_display=h_dt.strftime("%d %b · %I:%M %p IST"),
                        status=h.status.value,
                        preparation_tasks_total=t_total,
                        preparation_tasks_completed=t_comp,
                        exhibits_count=exhibit_counts.get(h.case_id, 0),
                        bundle_status=bundle_statuses.get(h.id),
                        action_href=f"/cases/{h.case_id}?tab=hearings",
                    )
                )

        # ---------------------------------------------------------------------
        # 6. UPCOMING DEADLINES (Next 7 - 90 Days)
        # ---------------------------------------------------------------------
        upcoming_deadlines_list: list[UpcomingDeadlineSummary] = []
        if user_case_ids:
            deadlines_query = (
                self.db.query(CaseDeadline)
                .filter(
                    CaseDeadline.case_id.in_(user_case_ids),
                    CaseDeadline.deleted_at.is_(None),
                    CaseDeadline.deadline_at >= now,
                    CaseDeadline.deadline_at <= window_end,
                    CaseDeadline.status.in_([DeadlineStatus.UPCOMING, DeadlineStatus.DUE]),
                )
                .order_by(CaseDeadline.deadline_at.asc())
                .limit(20)
                .all()
            )
            for d in deadlines_query:
                c = cases_map.get(d.case_id)
                d_dt = d.deadline_at.replace(tzinfo=UTC) if d.deadline_at.tzinfo is None else d.deadline_at
                is_urgent = (d_dt - now).total_seconds() < 86400 * 3
                upcoming_deadlines_list.append(
                    UpcomingDeadlineSummary(
                        deadline_id=d.id,
                        case_id=d.case_id,
                        case_title=c.title if c else "Active Matter",
                        title=d.title,
                        deadline_at=d_dt,
                        time_display=d_dt.strftime("%d %b · %I:%M %p IST"),
                        status=d.status.value,
                        source=d.source_type.value if hasattr(d.source_type, "value") else str(d.source_type),
                        retrieval_method=d.retrieval_method,
                        is_urgent=is_urgent,
                        action_href=f"/cases/{d.case_id}?tab=tasks",
                    )
                )

        # ---------------------------------------------------------------------
        # 7. HIGH PRIORITY TASKS
        # ---------------------------------------------------------------------
        high_priority_tasks_list: list[TodayAgendaItem] = []
        if user_case_ids:
            high_tasks = (
                self.db.query(CaseTask)
                .filter(
                    CaseTask.case_id.in_(user_case_ids),
                    CaseTask.deleted_at.is_(None),
                    CaseTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]),
                    CaseTask.priority.in_([TaskPriority.HIGH, TaskPriority.URGENT]),
                )
                .order_by(CaseTask.due_date.asc().nulls_last())
                .limit(20)
                .all()
            )
            for ht in high_tasks:
                c = cases_map.get(ht.case_id)
                ht_dt = (
                    ht.due_date.replace(tzinfo=UTC)
                    if ht.due_date and ht.due_date.tzinfo is None
                    else (ht.due_date or now)
                )
                high_priority_tasks_list.append(
                    TodayAgendaItem(
                        id=f"task-high-{ht.id}",
                        event_type="TASK",
                        title=ht.title,
                        scheduled_at=ht_dt,
                        time_display=ht_dt.strftime("%d %b · %I:%M %p IST") if ht.due_date else "No due date",
                        case_id=ht.case_id,
                        case_title=c.title if c else "Active Matter",
                        court_info=None,
                        status=ht.status.value,
                        priority=ht.priority.value if hasattr(ht.priority, "value") else str(ht.priority),
                        action_href=f"/cases/{ht.case_id}?tab=tasks",
                        action_label="Resolve Task",
                        is_urgent=ht.priority == TaskPriority.URGENT or (ht.due_date and ht_dt < now),
                    )
                )

        # ---------------------------------------------------------------------
        # 8. ASSIGNED MATTERS DIRECTORY SUMMARY
        # ---------------------------------------------------------------------
        assigned_matters_list: list[AssignedMatterSummary] = []
        if user_case_ids:
            # Aggregate stats per case
            overdue_counts_map: dict[uuid.UUID, int] = {}
            for cid, count in (
                self.db.query(CaseTask.case_id, func.count(CaseTask.id))
                .filter(
                    CaseTask.case_id.in_(user_case_ids),
                    CaseTask.deleted_at.is_(None),
                    CaseTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]),
                    CaseTask.due_date.isnot(None),
                    CaseTask.due_date < now,
                )
                .group_by(CaseTask.case_id)
                .all()
            ):
                overdue_counts_map[cid] = count or 0

            active_deadlines_map: dict[uuid.UUID, int] = {}
            for cid, count in (
                self.db.query(CaseDeadline.case_id, func.count(CaseDeadline.id))
                .filter(
                    CaseDeadline.case_id.in_(user_case_ids),
                    CaseDeadline.deleted_at.is_(None),
                    CaseDeadline.status.in_([DeadlineStatus.UPCOMING, DeadlineStatus.DUE, DeadlineStatus.OVERDUE]),
                )
                .group_by(CaseDeadline.case_id)
                .all()
            ):
                active_deadlines_map[cid] = count or 0

            unreviewed_evidence_map: dict[uuid.UUID, int] = {}
            for cid, count in (
                self.db.query(Evidence.case_id, func.count(Evidence.id))
                .filter(
                    Evidence.case_id.in_(user_case_ids),
                    Evidence.deleted_at.is_(None),
                    Evidence.status.in_([EvidenceStatus.QUARANTINED, EvidenceStatus.UPLOADING]),
                )
                .group_by(Evidence.case_id)
                .all()
            ):
                unreviewed_evidence_map[cid] = count or 0

            case_bundles_map: dict[uuid.UUID, str] = {}
            for cid, b_status in (
                self.db.query(EvidenceBundle.case_id, EvidenceBundle.status)
                .filter(
                    EvidenceBundle.case_id.in_(user_case_ids),
                    EvidenceBundle.deleted_at.is_(None),
                )
                .order_by(EvidenceBundle.created_at.desc())
                .all()
            ):
                if cid not in case_bundles_map:
                    case_bundles_map[cid] = b_status.value if hasattr(b_status, "value") else str(b_status)

            # Next hearing per case
            next_hearings_map: dict[uuid.UUID, tuple[datetime, str | None]] = {}
            for h in (
                self.db.query(CaseHearing)
                .filter(
                    CaseHearing.case_id.in_(user_case_ids),
                    CaseHearing.deleted_at.is_(None),
                    CaseHearing.status == HearingStatus.SCHEDULED,
                    CaseHearing.hearing_at >= now,
                )
                .order_by(CaseHearing.hearing_at.asc())
                .all()
            ):
                if h.case_id not in next_hearings_map:
                    h_dt = h.hearing_at.replace(tzinfo=UTC) if h.hearing_at.tzinfo is None else h.hearing_at
                    next_hearings_map[h.case_id] = (h_dt, h.purpose)

            for cid in user_case_ids:
                c = cases_map.get(cid)
                if not c:
                    continue
                nh_info = next_hearings_map.get(cid)
                assigned_matters_list.append(
                    AssignedMatterSummary(
                        case_id=c.id,
                        title=c.title,
                        case_number=c.case_number if hasattr(c, "case_number") else None,
                        status=c.status.value,
                        court_name=c.court_name if hasattr(c, "court_name") else None,
                        next_hearing_at=nh_info[0] if nh_info else None,
                        next_hearing_purpose=nh_info[1] if nh_info else None,
                        overdue_tasks_count=overdue_counts_map.get(cid, 0),
                        active_deadlines_count=active_deadlines_map.get(cid, 0),
                        unreviewed_evidence_count=unreviewed_evidence_map.get(cid, 0),
                        bundle_status=case_bundles_map.get(cid),
                        last_activity_at=c.updated_at,
                        action_href=f"/cases/{c.id}",
                    )
                )

        # Sort matters: matters with overdue tasks or imminent hearings first, then by updated_at desc
        assigned_matters_list.sort(
            key=lambda m: (
                m.overdue_tasks_count > 0,
                m.next_hearing_at is not None,
                m.last_activity_at or datetime.min.replace(tzinfo=UTC),
            ),
            reverse=True,
        )

        # ---------------------------------------------------------------------
        # 9. OPERATIONAL KPI METRICS
        # ---------------------------------------------------------------------
        pending_consultations_count = 0
        if lawyer_profile_id:
            pending_consultations_count = (
                self.db.query(func.count(Consultation.id))
                .filter(
                    Consultation.lawyer_id == lawyer_profile_id,
                    Consultation.status == ConsultationStatus.REQUESTED,
                )
                .scalar()
                or 0
            )

        unread_notifications_count = self.notification_service.get_unread_count(current_user)

        metrics = LawyerOperationalMetrics(
            active_cases_count=len(user_case_ids),
            upcoming_hearings_count=len(upcoming_hearings_list),
            overdue_tasks_count=len(overdue_tasks) if user_case_ids else 0,
            upcoming_deadlines_count=len(upcoming_deadlines_list),
            pending_consultations_count=pending_consultations_count,
            unread_notifications_count=unread_notifications_count,
        )

        return LawyerDashboardResponse(
            metrics=metrics,
            today_agenda=today_agenda,
            needs_attention=needs_attention,
            upcoming_hearings=upcoming_hearings_list,
            upcoming_deadlines=upcoming_deadlines_list,
            high_priority_tasks=high_priority_tasks_list,
            assigned_matters=assigned_matters_list,
            range_days=days_ahead,
        )
