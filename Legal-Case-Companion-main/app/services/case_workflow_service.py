import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from sqlalchemy.orm import Session

from app.core.authorization import (
    _get_case_participant,
    authorize_case_access,
    authorize_case_modification,
)
from app.core.exceptions import (
    AuthorizationError,
    ResourceNotFoundError,
    ValidationError,
)
from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.case import (
    Case,
    CaseStatus,
    CaseTimelineEvent,
    ParticipantRole,
)
from app.models.case_intelligence import (
    CaseChronologyEvent,
    CaseEvidenceGap,
    EvidenceGapStatus,
)
from app.models.task import CaseTask, TaskPriority, TaskSourceType, TaskStatus
from app.models.user import AccountStatus, User, UserRole
from app.models.workflow import (
    CaseDeadline,
    CaseHearing,
    DeadlineSourceType,
    DeadlineStatus,
    DeadlineType,
    HearingSourceType,
    HearingStatus,
)
from app.schemas.task import CaseTaskCreate, CaseTaskResponse, CaseTaskUpdate
from app.schemas.workflow import (
    CaseDeadlineCreate,
    CaseDeadlineResponse,
    CaseDeadlineUpdate,
    CaseHearingCreate,
    CaseHearingResponse,
    CaseHearingUpdate,
    CaseOperationsSummary,
    CaseWorkflowResponse,
)

logger = logging.getLogger(__name__)


class CaseWorkflowService:
    """Manages operational case workflows: tasks, deadlines, hearings, reminders, and auditable activities."""

    VALID_TASK_TRANSITIONS: ClassVar[dict[TaskStatus, set[TaskStatus]]] = {
        TaskStatus.PENDING: {
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.COMPLETED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.IN_PROGRESS: {
            TaskStatus.IN_PROGRESS,
            TaskStatus.COMPLETED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.COMPLETED: {TaskStatus.COMPLETED},
        TaskStatus.CANCELLED: {TaskStatus.CANCELLED},
    }

    VALID_DEADLINE_TRANSITIONS: ClassVar[dict[DeadlineStatus, set[DeadlineStatus]]] = {
        DeadlineStatus.UPCOMING: {
            DeadlineStatus.UPCOMING,
            DeadlineStatus.DUE,
            DeadlineStatus.OVERDUE,
            DeadlineStatus.COMPLETED,
            DeadlineStatus.CANCELLED,
        },
        DeadlineStatus.DUE: {
            DeadlineStatus.DUE,
            DeadlineStatus.OVERDUE,
            DeadlineStatus.COMPLETED,
            DeadlineStatus.CANCELLED,
        },
        DeadlineStatus.OVERDUE: {
            DeadlineStatus.OVERDUE,
            DeadlineStatus.COMPLETED,
            DeadlineStatus.CANCELLED,
        },
        DeadlineStatus.COMPLETED: {DeadlineStatus.COMPLETED},
        DeadlineStatus.CANCELLED: {DeadlineStatus.CANCELLED},
    }

    def __init__(self, db: Session):
        self.db = db

    def _check_case_active_for_mutations(self, case_id: uuid.UUID) -> Case:
        case = self.db.query(Case).filter(Case.id == case_id, Case.deleted_at.is_(None)).first()
        if not case:
            raise ResourceNotFoundError("Case not found")
        if case.status in (CaseStatus.CLOSED, CaseStatus.CANCELLED):
            raise ValidationError("Workflow mutations are not permitted on closed or cancelled cases")
        return case

    def _log_audit(self, action: str, user_id: uuid.UUID | None, metadata: dict | None = None) -> None:
        event = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=user_id,
            action=action,
            event_type=action,
            entity_type="WORKFLOW",
            timestamp=datetime.now(UTC),
            metadata_=metadata,
        )
        self.db.add(event)

    def _record_activity(
        self, case_id: uuid.UUID, actor_id: uuid.UUID | None, event_type: str, description: str, metadata: dict | None = None
    ) -> CaseTimelineEvent:
        event = CaseTimelineEvent(
            id=generate_uuid7(),
            case_id=case_id,
            actor_user_id=actor_id,
            event_type=event_type,
            description=description,
            event_metadata=metadata,
        )
        self.db.add(event)
        return event

    def get_workflow_overview(self, user: User, case_id: uuid.UUID) -> CaseWorkflowResponse:
        """Retrieves comprehensive operational workflow dashboard for the case."""
        authorize_case_access(self.db, user, case_id)

        now = datetime.now(UTC)

        # Dynamic deadline overdue check
        deadlines = (
            self.db.query(CaseDeadline)
            .filter(CaseDeadline.case_id == case_id, CaseDeadline.deleted_at.is_(None))
            .order_by(CaseDeadline.deadline_at.asc())
            .all()
        )
        for dl in deadlines:
            dl_at = dl.deadline_at.replace(tzinfo=UTC) if dl.deadline_at.tzinfo is None else dl.deadline_at
            if dl.status in (DeadlineStatus.UPCOMING, DeadlineStatus.DUE) and dl_at < now:
                dl.status = DeadlineStatus.OVERDUE

        tasks = (
            self.db.query(CaseTask)
            .filter(CaseTask.case_id == case_id, CaseTask.deleted_at.is_(None))
            .order_by(CaseTask.created_at.desc())
            .all()
        )
        hearings = (
            self.db.query(CaseHearing)
            .filter(CaseHearing.case_id == case_id, CaseHearing.deleted_at.is_(None))
            .order_by(CaseHearing.hearing_at.asc())
            .all()
        )

        open_tasks = [t for t in tasks if t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)]
        overdue_tasks = []
        for t in open_tasks:
            if t.due_date:
                t_due = t.due_date.replace(tzinfo=UTC) if t.due_date.tzinfo is None else t.due_date
                if t_due < now:
                    overdue_tasks.append(t)

        upcoming_deadlines = [d for d in deadlines if d.status in (DeadlineStatus.UPCOMING, DeadlineStatus.DUE)]
        overdue_deadlines = [d for d in deadlines if d.status == DeadlineStatus.OVERDUE]

        next_hearing = None
        for h in hearings:
            h_at = h.hearing_at.replace(tzinfo=UTC) if h.hearing_at.tzinfo is None else h.hearing_at
            if h.status == HearingStatus.SCHEDULED and h_at >= now:
                next_hearing = h
                break

        unconfirmed_tasks = sum(1 for t in tasks if not t.is_confirmed)
        unconfirmed_deadlines = sum(1 for d in deadlines if not d.is_confirmed)
        unconfirmed_hearings = sum(1 for h in hearings if not h.is_confirmed)

        summary = CaseOperationsSummary(
            open_tasks_count=len(open_tasks),
            overdue_tasks_count=len(overdue_tasks),
            upcoming_deadlines_count=len(upcoming_deadlines),
            overdue_deadlines_count=len(overdue_deadlines),
            next_hearing=CaseHearingResponse.model_validate(next_hearing) if next_hearing else None,
            unconfirmed_suggestions_count=unconfirmed_tasks + unconfirmed_deadlines + unconfirmed_hearings,
        )

        return CaseWorkflowResponse(
            case_id=case_id,
            tasks=[CaseTaskResponse.model_validate(t) for t in tasks],
            deadlines=[CaseDeadlineResponse.model_validate(d) for d in deadlines],
            hearings=[CaseHearingResponse.model_validate(h) for h in hearings],
            operations_summary=summary,
        )

    # --------------------------------------------------------------------------
    # TASK OPERATIONS
    # --------------------------------------------------------------------------

    def create_task(self, user: User, case_id: uuid.UUID, req: CaseTaskCreate) -> CaseTask:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)

        if user.role != UserRole.ADMIN:
            participant = _get_case_participant(self.db, case_id, user.id)
            if not participant or participant.participant_role == ParticipantRole.VIEWER:
                raise AuthorizationError("Viewers cannot create tasks")

        # Due date validation
        due_date = req.due_date
        if due_date is not None:
            if due_date.tzinfo is None:
                due_date = due_date.replace(tzinfo=UTC)
            if due_date < datetime.now(UTC) - timedelta(minutes=5):
                raise ValidationError("Task due date cannot be in the past")

        # Assignee validation
        if req.owner_user_id is not None:
            target_user = self.db.query(User).filter(User.id == req.owner_user_id, User.deleted_at.is_(None)).first()
            if not target_user or target_user.account_status != AccountStatus.ACTIVE:
                raise ValidationError("Assigned user must be an active user")

            assigned_p = _get_case_participant(self.db, case_id, req.owner_user_id)
            if not assigned_p:
                raise ValidationError("Assigned user must be an active participant of this case")

        task = CaseTask(
            id=generate_uuid7(),
            case_id=case_id,
            title=req.title,
            description=req.description,
            priority=req.priority,
            due_date=due_date,
            owner_user_id=req.owner_user_id,
            created_by_user_id=user.id,
            status=TaskStatus.PENDING,
            source_type=req.source_type,
            source_reference=req.source_reference,
            is_confirmed=req.is_confirmed,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        self._log_audit("TASK_CREATED", user.id, {"case_id": str(case_id), "task_id": str(task.id)})
        self._record_activity(case_id, user.id, "TASK_CREATED", f"Task '{task.title}' was created")
        self.db.commit()
        return task

    def update_task(self, user: User, case_id: uuid.UUID, task_id: uuid.UUID, req: CaseTaskUpdate) -> CaseTask:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)

        task = (
            self.db.query(CaseTask)
            .filter(CaseTask.id == task_id, CaseTask.case_id == case_id, CaseTask.deleted_at.is_(None))
            .first()
        )
        if not task:
            raise ResourceNotFoundError("Task not found")

        if user.role != UserRole.ADMIN:
            participant = _get_case_participant(self.db, case_id, user.id)
            if not participant or participant.participant_role == ParticipantRole.VIEWER:
                raise AuthorizationError("Viewers cannot update tasks")

        if req.owner_user_id is not None:
            target_user = self.db.query(User).filter(User.id == req.owner_user_id, User.deleted_at.is_(None)).first()
            if not target_user or target_user.account_status != AccountStatus.ACTIVE:
                raise ValidationError("Assigned user must be an active user")
            assigned_p = _get_case_participant(self.db, case_id, req.owner_user_id)
            if not assigned_p:
                raise ValidationError("Assigned user must be an active participant of this case")
            task.owner_user_id = req.owner_user_id

        if req.title is not None:
            task.title = req.title
        if req.description is not None:
            task.description = req.description
        if req.priority is not None:
            task.priority = req.priority
        if req.due_date is not None:
            due_date = req.due_date.replace(tzinfo=UTC) if req.due_date.tzinfo is None else req.due_date
            task.due_date = due_date

        if req.status is not None:
            allowed = self.VALID_TASK_TRANSITIONS.get(task.status, set())
            if req.status not in allowed:
                raise ValidationError(f"Invalid task status transition from {task.status.value} to {req.status.value}")
            task.status = req.status
            if req.status == TaskStatus.COMPLETED:
                task.completed_at = datetime.now(UTC)

        if req.is_confirmed is not None:
            task.is_confirmed = req.is_confirmed

        self.db.commit()
        self.db.refresh(task)
        return task

    def confirm_task(self, user: User, case_id: uuid.UUID, task_id: uuid.UUID) -> CaseTask:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)
        task = (
            self.db.query(CaseTask)
            .filter(CaseTask.id == task_id, CaseTask.case_id == case_id, CaseTask.deleted_at.is_(None))
            .first()
        )
        if not task:
            raise ResourceNotFoundError("Task not found")

        task.is_confirmed = True
        self._log_audit("AI_SUGGESTION_CONFIRMED", user.id, {"case_id": str(case_id), "task_id": str(task_id)})
        self._record_activity(case_id, user.id, "TASK_CONFIRMED", f"Task '{task.title}' confirmed by reviewer")
        self.db.commit()
        self.db.refresh(task)
        return task

    # --------------------------------------------------------------------------
    # DEADLINE OPERATIONS
    # --------------------------------------------------------------------------

    def create_deadline(self, user: User, case_id: uuid.UUID, req: CaseDeadlineCreate) -> CaseDeadline:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)

        deadline_at = req.deadline_at.replace(tzinfo=UTC) if req.deadline_at.tzinfo is None else req.deadline_at

        deadline = CaseDeadline(
            id=generate_uuid7(),
            case_id=case_id,
            title=req.title,
            description=req.description,
            deadline_at=deadline_at,
            deadline_type=req.deadline_type,
            status=DeadlineStatus.UPCOMING,
            source_type=req.source_type,
            source_reference=req.source_reference,
            is_confirmed=req.is_confirmed,
            created_by_user_id=user.id,
        )
        self.db.add(deadline)
        self.db.commit()
        self.db.refresh(deadline)

        self._log_audit("DEADLINE_CREATED", user.id, {"case_id": str(case_id), "deadline_id": str(deadline.id)})
        self._record_activity(case_id, user.id, "DEADLINE_CREATED", f"Deadline '{deadline.title}' was scheduled for {deadline_at.isoformat()}")
        self.db.commit()
        return deadline

    def update_deadline(self, user: User, case_id: uuid.UUID, deadline_id: uuid.UUID, req: CaseDeadlineUpdate) -> CaseDeadline:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)

        deadline = (
            self.db.query(CaseDeadline)
            .filter(CaseDeadline.id == deadline_id, CaseDeadline.case_id == case_id, CaseDeadline.deleted_at.is_(None))
            .first()
        )
        if not deadline:
            raise ResourceNotFoundError("Deadline not found")

        if req.title is not None:
            deadline.title = req.title
        if req.description is not None:
            deadline.description = req.description
        if req.deadline_at is not None:
            deadline.deadline_at = req.deadline_at.replace(tzinfo=UTC) if req.deadline_at.tzinfo is None else req.deadline_at
        if req.deadline_type is not None:
            deadline.deadline_type = req.deadline_type

        if req.status is not None:
            allowed = self.VALID_DEADLINE_TRANSITIONS.get(deadline.status, set())
            if req.status not in allowed:
                raise ValidationError(f"Invalid deadline status transition from {deadline.status.value} to {req.status.value}")
            deadline.status = req.status
            if req.status == DeadlineStatus.COMPLETED:
                deadline.completed_at = datetime.now(UTC)

        if req.is_confirmed is not None:
            deadline.is_confirmed = req.is_confirmed

        self.db.commit()
        self.db.refresh(deadline)
        return deadline

    def confirm_deadline(self, user: User, case_id: uuid.UUID, deadline_id: uuid.UUID) -> CaseDeadline:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)
        deadline = (
            self.db.query(CaseDeadline)
            .filter(CaseDeadline.id == deadline_id, CaseDeadline.case_id == case_id, CaseDeadline.deleted_at.is_(None))
            .first()
        )
        if not deadline:
            raise ResourceNotFoundError("Deadline not found")

        deadline.is_confirmed = True
        self._log_audit("AI_SUGGESTION_CONFIRMED", user.id, {"case_id": str(case_id), "deadline_id": str(deadline_id)})
        self._record_activity(case_id, user.id, "DEADLINE_CONFIRMED", f"Deadline '{deadline.title}' confirmed by reviewer")
        self.db.commit()
        self.db.refresh(deadline)
        return deadline

    # --------------------------------------------------------------------------
    # HEARING OPERATIONS
    # --------------------------------------------------------------------------

    def create_hearing(self, user: User, case_id: uuid.UUID, req: CaseHearingCreate) -> CaseHearing:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)

        hearing_at = req.hearing_at.replace(tzinfo=UTC) if req.hearing_at.tzinfo is None else req.hearing_at

        hearing = CaseHearing(
            id=generate_uuid7(),
            case_id=case_id,
            court_name=req.court_name,
            hearing_at=hearing_at,
            purpose=req.purpose,
            bench_or_coram=req.bench_or_coram,
            notes=req.notes,
            status=HearingStatus.SCHEDULED,
            source_type=req.source_type,
            source_reference=req.source_reference,
            is_confirmed=req.is_confirmed,
            created_by_user_id=user.id,
        )
        self.db.add(hearing)
        self.db.commit()
        self.db.refresh(hearing)

        self._log_audit("HEARING_CREATED", user.id, {"case_id": str(case_id), "hearing_id": str(hearing.id)})
        self._record_activity(case_id, user.id, "HEARING_SCHEDULED", f"Hearing scheduled at {hearing.court_name} on {hearing_at.isoformat()}")
        self.db.commit()
        return hearing

    def update_hearing(self, user: User, case_id: uuid.UUID, hearing_id: uuid.UUID, req: CaseHearingUpdate) -> CaseHearing:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)

        hearing = (
            self.db.query(CaseHearing)
            .filter(CaseHearing.id == hearing_id, CaseHearing.case_id == case_id, CaseHearing.deleted_at.is_(None))
            .first()
        )
        if not hearing:
            raise ResourceNotFoundError("Hearing not found")

        if req.court_name is not None:
            hearing.court_name = req.court_name
        if req.purpose is not None:
            hearing.purpose = req.purpose
        if req.bench_or_coram is not None:
            hearing.bench_or_coram = req.bench_or_coram
        if req.notes is not None:
            hearing.notes = req.notes
        if req.hearing_at is not None:
            hearing.hearing_at = req.hearing_at.replace(tzinfo=UTC) if req.hearing_at.tzinfo is None else req.hearing_at
        if req.status is not None:
            hearing.status = req.status
        if req.is_confirmed is not None:
            hearing.is_confirmed = req.is_confirmed

        self.db.commit()
        self.db.refresh(hearing)
        return hearing

    def confirm_hearing(self, user: User, case_id: uuid.UUID, hearing_id: uuid.UUID) -> CaseHearing:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)
        hearing = (
            self.db.query(CaseHearing)
            .filter(CaseHearing.id == hearing_id, CaseHearing.case_id == case_id, CaseHearing.deleted_at.is_(None))
            .first()
        )
        if not hearing:
            raise ResourceNotFoundError("Hearing not found")

        hearing.is_confirmed = True
        self._log_audit("AI_SUGGESTION_CONFIRMED", user.id, {"case_id": str(case_id), "hearing_id": str(hearing_id)})
        self._record_activity(case_id, user.id, "HEARING_CONFIRMED", f"Hearing at '{hearing.court_name}' confirmed by reviewer")
        self.db.commit()
        self.db.refresh(hearing)
        return hearing

    # --------------------------------------------------------------------------
    # SMART SUGGESTIONS FROM CASE INTELLIGENCE
    # --------------------------------------------------------------------------

    def generate_suggestions_from_intelligence(self, user: User, case_id: uuid.UUID) -> dict:
        """Idempotently scans case intelligence (evidence gaps, chronology events) and

        proposes unconfirmed tasks, deadlines, and hearings.
        """
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)

        suggested_tasks: list[CaseTask] = []
        suggested_deadlines: list[CaseDeadline] = []
        suggested_hearings: list[CaseHearing] = []

        # 1. Evidence Gaps -> Suggested Tasks
        gaps = (
            self.db.query(CaseEvidenceGap)
            .filter(
                CaseEvidenceGap.case_id == case_id,
                CaseEvidenceGap.status != EvidenceGapStatus.RESOLVED,
                CaseEvidenceGap.deleted_at.is_(None),
            )
            .all()
        )
        existing_task_refs = {
            t.source_reference
            for t in self.db.query(CaseTask.source_reference)
            .filter(CaseTask.case_id == case_id, CaseTask.deleted_at.is_(None))
            .all()
            if t.source_reference
        }

        for gap in gaps:
            ref = str(gap.id)
            if ref in existing_task_refs:
                continue

            task = CaseTask(
                id=generate_uuid7(),
                case_id=case_id,
                title=f"Procure Evidence: {gap.description[:80]}",
                description=gap.description,
                priority=TaskPriority.HIGH if gap.severity.value in ("HIGH", "CRITICAL") else TaskPriority.MEDIUM,
                status=TaskStatus.PENDING,
                source_type=TaskSourceType.EVIDENCE_GAP,
                source_reference=ref,
                is_confirmed=False,
                created_by_user_id=user.id,
            )
            self.db.add(task)
            suggested_tasks.append(task)
            existing_task_refs.add(ref)

        # 2. Chronology Events -> Suggested Deadlines / Hearings
        events = (
            self.db.query(CaseChronologyEvent)
            .filter(CaseChronologyEvent.case_id == case_id, CaseChronologyEvent.deleted_at.is_(None))
            .all()
        )
        existing_dl_refs = {
            d.source_reference
            for d in self.db.query(CaseDeadline.source_reference)
            .filter(CaseDeadline.case_id == case_id, CaseDeadline.deleted_at.is_(None))
            .all()
            if d.source_reference
        }
        existing_hearing_refs = {
            h.source_reference
            for h in self.db.query(CaseHearing.source_reference)
            .filter(CaseHearing.case_id == case_id, CaseHearing.deleted_at.is_(None))
            .all()
            if h.source_reference
        }

        for ev in events:
            ref = str(ev.id)
            if not ev.event_date:
                continue

            ev_date = datetime(ev.event_date.year, ev.event_date.month, ev.event_date.day, 10, 0, tzinfo=UTC)

            if "hearing" in ev.description.lower() or "listed" in ev.description.lower() or "court" in ev.description.lower():
                if ref in existing_hearing_refs:
                    continue
                hearing = CaseHearing(
                    id=generate_uuid7(),
                    case_id=case_id,
                    court_name="Court / Forum",
                    hearing_at=ev_date,
                    purpose=ev.description[:100],
                    status=HearingStatus.SCHEDULED,
                    source_type=HearingSourceType.CASE_DOCUMENT,
                    source_reference=ref,
                    is_confirmed=False,
                    created_by_user_id=user.id,
                )
                self.db.add(hearing)
                suggested_hearings.append(hearing)
                existing_hearing_refs.add(ref)
            elif "notice" in ev.description.lower() or "payment" in ev.description.lower() or "due" in ev.description.lower():
                if ref in existing_dl_refs:
                    continue
                # E.g. statutory 15-day notice compliance
                dl = CaseDeadline(
                    id=generate_uuid7(),
                    case_id=case_id,
                    title=f"Compliance: {ev.event_type}",
                    description=ev.description,
                    deadline_at=ev_date + timedelta(days=15),
                    deadline_type=DeadlineType.REPLY_NOTICE,
                    status=DeadlineStatus.UPCOMING,
                    source_type=DeadlineSourceType.CASE_DOCUMENT,
                    source_reference=ref,
                    is_confirmed=False,
                    created_by_user_id=user.id,
                )
                self.db.add(dl)
                suggested_deadlines.append(dl)
                existing_dl_refs.add(ref)

        self.db.commit()
        return {
            "suggested_tasks_count": len(suggested_tasks),
            "suggested_deadlines_count": len(suggested_deadlines),
            "suggested_hearings_count": len(suggested_hearings),
        }
