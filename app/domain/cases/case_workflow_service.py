import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from sqlalchemy import or_ as sa_or
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
from app.models.evidence import Evidence
from app.models.notification import NotificationType
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
from app.schemas.task import (
    CaseHealthSummaryResponse,
    CaseTaskBatchActionRequest,
    CaseTaskCreate,
    CaseTaskReassignRequest,
    CaseTaskResponse,
    CaseTaskUpdate,
    CaseWorkflowTemplateApplyRequest,
)
from app.schemas.workflow import (
    CaseDeadlineCreate,
    CaseDeadlineResponse,
    CaseDeadlineUpdate,
    CaseHearingAdjournRequest,
    CaseHearingCompleteRequest,
    CaseHearingCreate,
    CaseHearingECourtsImportRequest,
    CaseHearingResponse,
    CaseHearingUpdate,
    CaseOperationsSummary,
    CaseWorkflowResponse,
)
from app.domain.notifications.notification_service import NotificationService

logger = logging.getLogger(__name__)


class CaseWorkflowService:
    """Manages operational case workflows: tasks, deadlines, hearings, reminders, and auditable activities."""

    VALID_TASK_TRANSITIONS: ClassVar[dict[TaskStatus, set[TaskStatus]]] = {
        TaskStatus.PENDING: {
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.COMPLETED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.IN_PROGRESS: {
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.COMPLETED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.BLOCKED: {
            TaskStatus.BLOCKED,
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.COMPLETED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.COMPLETED: {
            TaskStatus.COMPLETED,
            TaskStatus.IN_PROGRESS,  # Supported via explicit reopen
        },
        TaskStatus.CANCELLED: {
            TaskStatus.CANCELLED,
            TaskStatus.IN_PROGRESS,  # Supported via explicit reopen
        },
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
        self.notification_service = NotificationService(db)

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

        open_tasks = [t for t in tasks if t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED)]
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

        # Validate linked entities if provided
        if req.linked_evidence_id is not None:
            ev = self.db.query(Evidence).filter(
                Evidence.id == req.linked_evidence_id,
                Evidence.case_id == case_id,
                Evidence.deleted_at.is_(None),
            ).first()
            if not ev:
                raise ValidationError("Linked evidence not found in this case")

        if req.linked_hearing_id is not None:
            hr = self.db.query(CaseHearing).filter(
                CaseHearing.id == req.linked_hearing_id,
                CaseHearing.case_id == case_id,
                CaseHearing.deleted_at.is_(None),
            ).first()
            if not hr:
                raise ValidationError("Linked hearing not found in this case")

        if req.linked_deadline_id is not None:
            dl = self.db.query(CaseDeadline).filter(
                CaseDeadline.id == req.linked_deadline_id,
                CaseDeadline.case_id == case_id,
                CaseDeadline.deleted_at.is_(None),
            ).first()
            if not dl:
                raise ValidationError("Linked deadline not found in this case")

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
            linked_evidence_id=req.linked_evidence_id,
            linked_hearing_id=req.linked_hearing_id,
            linked_deadline_id=req.linked_deadline_id,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        self._log_audit("TASK_CREATED", user.id, {"case_id": str(case_id), "task_id": str(task.id)})
        self._record_activity(case_id, user.id, "TASK_CREATED", f"Task '{task.title}' was created")
        self.db.commit()

        if task.owner_user_id and task.owner_user_id != user.id:
            self.notification_service.create_notification(
                user_id=task.owner_user_id,
                type=NotificationType.TASK_ASSIGNED,
                title="Task Assigned",
                message=f"You were assigned to task: '{task.title}'.",
                case_id=case_id,
                task_id=task.id,
            )

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
            prev_owner = task.owner_user_id
            task.owner_user_id = req.owner_user_id
            if req.owner_user_id != prev_owner and req.owner_user_id != user.id:
                self.notification_service.create_notification(
                    user_id=req.owner_user_id,
                    type=NotificationType.TASK_ASSIGNED,
                    title="Task Assigned",
                    message=f"You were assigned to task: '{task.title}'.",
                    case_id=case_id,
                    task_id=task.id,
                )

        if req.title is not None:
            task.title = req.title
        if req.description is not None:
            task.description = req.description
        if req.priority is not None:
            task.priority = req.priority
        if req.due_date is not None:
            due_date = req.due_date.replace(tzinfo=UTC) if req.due_date.tzinfo is None else req.due_date
            task.due_date = due_date

        if req.linked_evidence_id is not None:
            ev = self.db.query(Evidence).filter(
                Evidence.id == req.linked_evidence_id,
                Evidence.case_id == case_id,
                Evidence.deleted_at.is_(None),
            ).first()
            if not ev:
                raise ValidationError("Linked evidence not found in this case")
            task.linked_evidence_id = req.linked_evidence_id

        if req.linked_hearing_id is not None:
            hr = self.db.query(CaseHearing).filter(
                CaseHearing.id == req.linked_hearing_id,
                CaseHearing.case_id == case_id,
                CaseHearing.deleted_at.is_(None),
            ).first()
            if not hr:
                raise ValidationError("Linked hearing not found in this case")
            task.linked_hearing_id = req.linked_hearing_id

        if req.linked_deadline_id is not None:
            dl = self.db.query(CaseDeadline).filter(
                CaseDeadline.id == req.linked_deadline_id,
                CaseDeadline.case_id == case_id,
                CaseDeadline.deleted_at.is_(None),
            ).first()
            if not dl:
                raise ValidationError("Linked deadline not found in this case")
            task.linked_deadline_id = req.linked_deadline_id

        if req.status is not None:
            allowed = self.VALID_TASK_TRANSITIONS.get(task.status, set())
            if req.status not in allowed:
                raise ValidationError(f"Invalid task status transition from {task.status.value} to {req.status.value}")
            task.status = req.status
            if req.status == TaskStatus.COMPLETED:
                task.completed_at = datetime.now(UTC)
            elif req.status in (TaskStatus.IN_PROGRESS, TaskStatus.PENDING, TaskStatus.BLOCKED):
                task.completed_at = None

        if req.is_confirmed is not None:
            task.is_confirmed = req.is_confirmed

        self.db.commit()
        self.db.refresh(task)
        return task

    def start_task(self, user: User, case_id: uuid.UUID, task_id: uuid.UUID) -> CaseTask:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)
        task = self.db.query(CaseTask).filter(CaseTask.id == task_id, CaseTask.case_id == case_id, CaseTask.deleted_at.is_(None)).first()
        if not task:
            raise ResourceNotFoundError("Task not found")

        allowed = self.VALID_TASK_TRANSITIONS.get(task.status, set())
        if TaskStatus.IN_PROGRESS not in allowed:
            raise ValidationError(f"Cannot start task from status {task.status.value}")

        task.status = TaskStatus.IN_PROGRESS
        task.completed_at = None
        self._log_audit("TASK_STARTED", user.id, {"case_id": str(case_id), "task_id": str(task_id)})
        self._record_activity(case_id, user.id, "TASK_STARTED", f"Task '{task.title}' was started")
        self.db.commit()
        self.db.refresh(task)
        return task

    def complete_task(self, user: User, case_id: uuid.UUID, task_id: uuid.UUID) -> CaseTask:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)
        task = self.db.query(CaseTask).filter(CaseTask.id == task_id, CaseTask.case_id == case_id, CaseTask.deleted_at.is_(None)).first()
        if not task:
            raise ResourceNotFoundError("Task not found")

        allowed = self.VALID_TASK_TRANSITIONS.get(task.status, set())
        if TaskStatus.COMPLETED not in allowed:
            raise ValidationError(f"Cannot complete task from status {task.status.value}")

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(UTC)
        self._log_audit("TASK_COMPLETED", user.id, {"case_id": str(case_id), "task_id": str(task_id)})
        self._record_activity(case_id, user.id, "TASK_COMPLETED", f"Task '{task.title}' was marked completed")
        self.db.commit()
        self.db.refresh(task)

        if task.owner_user_id and task.owner_user_id != user.id:
            self.notification_service.create_notification(
                user_id=task.owner_user_id,
                type=NotificationType.TASK_COMPLETED,
                title="Task Completed",
                message=f"Task '{task.title}' was marked completed.",
                case_id=case_id,
                task_id=task.id,
            )

        return task

    def cancel_task(self, user: User, case_id: uuid.UUID, task_id: uuid.UUID) -> CaseTask:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)
        task = self.db.query(CaseTask).filter(CaseTask.id == task_id, CaseTask.case_id == case_id, CaseTask.deleted_at.is_(None)).first()
        if not task:
            raise ResourceNotFoundError("Task not found")

        allowed = self.VALID_TASK_TRANSITIONS.get(task.status, set())
        if TaskStatus.CANCELLED not in allowed:
            raise ValidationError(f"Cannot cancel task from status {task.status.value}")

        task.status = TaskStatus.CANCELLED
        self._log_audit("TASK_CANCELLED", user.id, {"case_id": str(case_id), "task_id": str(task_id)})
        self._record_activity(case_id, user.id, "TASK_CANCELLED", f"Task '{task.title}' was cancelled")
        self.db.commit()
        self.db.refresh(task)
        return task

    def reopen_task(self, user: User, case_id: uuid.UUID, task_id: uuid.UUID) -> CaseTask:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)
        task = self.db.query(CaseTask).filter(CaseTask.id == task_id, CaseTask.case_id == case_id, CaseTask.deleted_at.is_(None)).first()
        if not task:
            raise ResourceNotFoundError("Task not found")

        if task.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            raise ValidationError("Only completed or cancelled tasks can be reopened")

        task.status = TaskStatus.IN_PROGRESS
        task.completed_at = None
        self._log_audit("TASK_REOPENED", user.id, {"case_id": str(case_id), "task_id": str(task_id)})
        self._record_activity(case_id, user.id, "TASK_REOPENED", f"Task '{task.title}' was reopened")
        self.db.commit()
        self.db.refresh(task)
        return task

    def reassign_task(self, user: User, case_id: uuid.UUID, task_id: uuid.UUID, req: CaseTaskReassignRequest) -> CaseTask:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)
        task = self.db.query(CaseTask).filter(CaseTask.id == task_id, CaseTask.case_id == case_id, CaseTask.deleted_at.is_(None)).first()
        if not task:
            raise ResourceNotFoundError("Task not found")

        target_user = self.db.query(User).filter(User.id == req.owner_user_id, User.deleted_at.is_(None)).first()
        if not target_user or target_user.account_status != AccountStatus.ACTIVE:
            raise ValidationError("Assigned user must be an active user")

        assigned_p = _get_case_participant(self.db, case_id, req.owner_user_id)
        if not assigned_p:
            raise ValidationError("Assigned user must be an active participant of this case")

        prev_owner = task.owner_user_id
        task.owner_user_id = req.owner_user_id
        self._log_audit("TASK_REASSIGNED", user.id, {"case_id": str(case_id), "task_id": str(task_id), "previous_owner": str(prev_owner), "new_owner": str(req.owner_user_id)})
        self._record_activity(case_id, user.id, "TASK_REASSIGNED", f"Task '{task.title}' was reassigned")
        self.db.commit()
        self.db.refresh(task)

        if req.owner_user_id != user.id:
            self.notification_service.create_notification(
                user_id=req.owner_user_id,
                type=NotificationType.TASK_ASSIGNED,
                title="Task Reassigned",
                message=f"You were assigned to task: '{task.title}'.",
                case_id=case_id,
                task_id=task.id,
            )

        return task

    def batch_task_operations(self, user: User, case_id: uuid.UUID, req: CaseTaskBatchActionRequest) -> dict[str, Any]:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)

        if not req.task_ids or len(req.task_ids) > 50:
            raise ValidationError("Batch must contain between 1 and 50 tasks")

        tasks = self.db.query(CaseTask).filter(
            CaseTask.id.in_(req.task_ids),
            CaseTask.case_id == case_id,
            CaseTask.deleted_at.is_(None),
        ).all()

        # Fail-closed tenant isolation check
        if len(tasks) != len(req.task_ids):
            raise ResourceNotFoundError("One or more tasks not found in this case")

        if req.action == "REASSIGN":
            if not req.owner_user_id:
                raise ValidationError("owner_user_id required for REASSIGN action")
            assigned_p = _get_case_participant(self.db, case_id, req.owner_user_id)
            if not assigned_p:
                raise ValidationError("Assigned user must be an active participant of this case")
            for t in tasks:
                t.owner_user_id = req.owner_user_id
        elif req.action == "CHANGE_PRIORITY":
            if not req.priority:
                raise ValidationError("priority required for CHANGE_PRIORITY action")
            for t in tasks:
                t.priority = req.priority
        elif req.action == "COMPLETE":
            now = datetime.now(UTC)
            for t in tasks:
                t.status = TaskStatus.COMPLETED
                t.completed_at = now
        elif req.action == "CANCEL":
            for t in tasks:
                t.status = TaskStatus.CANCELLED

        self._log_audit("TASK_BATCH_UPDATED", user.id, {"case_id": str(case_id), "action": req.action, "count": len(tasks)})
        self.db.commit()
        return {
            "action": req.action,
            "updated_count": len(tasks),
            "task_ids": [str(t.id) for t in tasks],
        }

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

        if req.linked_hearing_id is not None:
            hr = self.db.query(CaseHearing).filter(
                CaseHearing.id == req.linked_hearing_id,
                CaseHearing.case_id == case_id,
                CaseHearing.deleted_at.is_(None),
            ).first()
            if not hr:
                raise ValidationError("Linked hearing not found in this case")

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
            linked_hearing_id=req.linked_hearing_id,
            retrieval_method=req.retrieval_method or "MANUAL",
            retrieved_at=datetime.now(UTC),
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

        if req.linked_hearing_id is not None:
            hr = self.db.query(CaseHearing).filter(
                CaseHearing.id == req.linked_hearing_id,
                CaseHearing.case_id == case_id,
                CaseHearing.deleted_at.is_(None),
            ).first()
            if not hr:
                raise ValidationError("Linked hearing not found in this case")
            deadline.linked_hearing_id = req.linked_hearing_id

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

    def complete_deadline(self, user: User, case_id: uuid.UUID, deadline_id: uuid.UUID) -> CaseDeadline:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)
        deadline = (
            self.db.query(CaseDeadline)
            .filter(CaseDeadline.id == deadline_id, CaseDeadline.case_id == case_id, CaseDeadline.deleted_at.is_(None))
            .first()
        )
        if not deadline:
            raise ResourceNotFoundError("Deadline not found")

        deadline.status = DeadlineStatus.COMPLETED
        deadline.completed_at = datetime.now(UTC)
        self._log_audit("DEADLINE_COMPLETED", user.id, {"case_id": str(case_id), "deadline_id": str(deadline.id)})
        self._record_activity(case_id, user.id, "DEADLINE_COMPLETED", f"Deadline '{deadline.title}' was marked completed")
        self.db.commit()
        self.db.refresh(deadline)
        return deadline

    def cancel_deadline(self, user: User, case_id: uuid.UUID, deadline_id: uuid.UUID) -> CaseDeadline:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)
        deadline = (
            self.db.query(CaseDeadline)
            .filter(CaseDeadline.id == deadline_id, CaseDeadline.case_id == case_id, CaseDeadline.deleted_at.is_(None))
            .first()
        )
        if not deadline:
            raise ResourceNotFoundError("Deadline not found")

        deadline.status = DeadlineStatus.CANCELLED
        self._log_audit("DEADLINE_CANCELLED", user.id, {"case_id": str(case_id), "deadline_id": str(deadline.id)})
        self._record_activity(case_id, user.id, "DEADLINE_CANCELLED", f"Deadline '{deadline.title}' was cancelled")
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
    # DETERMINISTIC WORKFLOW TEMPLATES (ZERO AI)
    # --------------------------------------------------------------------------

    def apply_workflow_template(
        self, user: User, case_id: uuid.UUID, req: CaseWorkflowTemplateApplyRequest
    ) -> list[CaseTask]:
        """Applies deterministic procedural operational templates without AI."""
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)

        target_hearing = None
        if req.hearing_id:
            target_hearing = (
                self.db.query(CaseHearing)
                .filter(
                    CaseHearing.id == req.hearing_id,
                    CaseHearing.case_id == case_id,
                    CaseHearing.deleted_at.is_(None),
                )
                .first()
            )
            if not target_hearing:
                raise ValidationError("Specified hearing not found in this case")

        if req.assignee_user_id:
            assigned_p = _get_case_participant(self.db, case_id, req.assignee_user_id)
            if not assigned_p:
                raise ValidationError("Specified assignee is not an active participant of this case")

        now = datetime.now(UTC)
        base_hearing_time = (
            target_hearing.hearing_at.replace(tzinfo=UTC)
            if target_hearing and target_hearing.hearing_at.tzinfo is None
            else (target_hearing.hearing_at if target_hearing else now + timedelta(days=7))
        )

        template_tasks_data: list[dict[str, Any]] = []

        if req.template_name == "HEARING_PREPARATION":
            template_tasks_data = [
                {
                    "title": "Review listing date & courtroom board",
                    "description": "Cross-check court listing on official cause list board and courtroom allocation.",
                    "priority": TaskPriority.HIGH,
                    "due_date": max(now, base_hearing_time - timedelta(days=5)),
                },
                {
                    "title": "Review previous court order & compliance directives",
                    "description": "Audit procedural orders and verify compliance directives before listing.",
                    "priority": TaskPriority.HIGH,
                    "due_date": max(now, base_hearing_time - timedelta(days=4)),
                },
                {
                    "title": "Audit marked case exhibits and version bindings",
                    "description": "Verify all evidence versions are marked with sequential exhibit numbers.",
                    "priority": TaskPriority.HIGH,
                    "due_date": max(now, base_hearing_time - timedelta(days=3)),
                },
                {
                    "title": "Compile and finalize court evidentiary bundle with Bates numbering",
                    "description": "Generate immutable evidentiary bundle PDF with cover page, index, and Bates stamps.",
                    "priority": TaskPriority.URGENT,
                    "due_date": max(now, base_hearing_time - timedelta(days=2)),
                },
                {
                    "title": "Prepare and verify BSA Section 63 electronic record certificate draft",
                    "description": "Prepare statutory electronic record certificate draft under Bharatiya Sakshya Adhiniyam, 2023.",
                    "priority": TaskPriority.HIGH,
                    "due_date": max(now, base_hearing_time - timedelta(days=1)),
                },
                {
                    "title": "Client briefing & hearing appearance logistics confirmation",
                    "description": "Confirm client briefing, video link credentials or physical courtroom attendance.",
                    "priority": TaskPriority.MEDIUM,
                    "due_date": max(now, base_hearing_time - timedelta(hours=12)),
                },
            ]
        elif req.template_name == "POST_HEARING_FOLLOWUP":
            template_tasks_data = [
                {
                    "title": "Record bench proceedings and daily order synopsis",
                    "description": "Draft concise matter synopsis of proceedings, judge queries, and interim directions.",
                    "priority": TaskPriority.HIGH,
                    "due_date": now + timedelta(days=1),
                },
                {
                    "title": "Upload certified court order to Evidence Locker",
                    "description": "Obtain certified copy of order and upload to Evidence Locker with SHA-256 integrity.",
                    "priority": TaskPriority.HIGH,
                    "due_date": now + timedelta(days=2),
                },
                {
                    "title": "Update next hearing date and cause list tracking",
                    "description": "Record next adjourned date on case calendar and configure reminder notifications.",
                    "priority": TaskPriority.MEDIUM,
                    "due_date": now + timedelta(days=2),
                },
                {
                    "title": "Schedule compliance filings and client updates",
                    "description": "Send procedural update to client and calendar any compliance deadlines ordered by the bench.",
                    "priority": TaskPriority.MEDIUM,
                    "due_date": now + timedelta(days=3),
                },
            ]
        elif req.template_name == "EVIDENCE_PREPARATION":
            template_tasks_data = [
                {
                    "title": "Collect source digital evidence and verify chain of custody",
                    "description": "Retrieve native files, emails, or digital records from client with original timestamps.",
                    "priority": TaskPriority.MEDIUM,
                    "due_date": now + timedelta(days=3),
                },
                {
                    "title": "Upload original documents to Evidence Locker and verify SHA-256 integrity",
                    "description": "Deposit files into private Evidence Locker; perform malware scanning and SHA-256 hashing.",
                    "priority": TaskPriority.HIGH,
                    "due_date": now + timedelta(days=5),
                },
                {
                    "title": "Mark formal exhibits with sequential letter designations",
                    "description": "Assign Exhibit A, Exhibit B ... and bind to specific evidence versions.",
                    "priority": TaskPriority.HIGH,
                    "due_date": now + timedelta(days=7),
                },
            ]
        elif req.template_name == "NEW_CONSULTATION":
            template_tasks_data = [
                {
                    "title": "Review client intake information and matter summary",
                    "description": "Review intake facts, dispute background, and key party relationships.",
                    "priority": TaskPriority.MEDIUM,
                    "due_date": now + timedelta(days=1),
                },
                {
                    "title": "Request required identity and foundational contract documents",
                    "description": "Dispatch document request to client for Aadhaar/PAN and foundational agreements.",
                    "priority": TaskPriority.HIGH,
                    "due_date": now + timedelta(days=2),
                },
                {
                    "title": "Conduct legal consultation and prepare matter brief",
                    "description": "Hold consultation session and summarize actionable legal strategy.",
                    "priority": TaskPriority.HIGH,
                    "due_date": now + timedelta(days=3),
                },
            ]

        created_tasks: list[CaseTask] = []
        for item in template_tasks_data:
            task = CaseTask(
                id=generate_uuid7(),
                case_id=case_id,
                title=item["title"],
                description=item["description"],
                priority=item["priority"],
                due_date=item["due_date"],
                owner_user_id=req.assignee_user_id,
                created_by_user_id=user.id,
                status=TaskStatus.PENDING,
                source_type=TaskSourceType.MANUAL,
                source_reference=f"template:{req.template_name}",
                is_confirmed=True,
                linked_hearing_id=req.hearing_id,
            )
            self.db.add(task)
            created_tasks.append(task)

        self._log_audit(
            "WORKFLOW_TEMPLATE_APPLIED",
            user.id,
            {
                "case_id": str(case_id),
                "template_name": req.template_name,
                "tasks_count": len(created_tasks),
                "hearing_id": str(req.hearing_id) if req.hearing_id else None,
            },
        )
        self._record_activity(
            case_id,
            user.id,
            "WORKFLOW_TEMPLATE_APPLIED",
            f"Workflow template '{req.template_name}' was applied ({len(created_tasks)} tasks generated)",
        )
        self.db.commit()

        for t in created_tasks:
            self.db.refresh(t)

        return created_tasks

    # --------------------------------------------------------------------------
    # CASE HEALTH SUMMARY & TELEMETRY (DETERMINISTIC)
    # --------------------------------------------------------------------------

    def get_case_health_summary(self, user: User, case_id: uuid.UUID) -> CaseHealthSummaryResponse:
        """Calculates deterministic operational case health indicators."""
        authorize_case_access(self.db, user, case_id)

        now = datetime.now(UTC)

        # 1. Next upcoming hearing
        next_hearing = (
            self.db.query(CaseHearing)
            .filter(
                CaseHearing.case_id == case_id,
                CaseHearing.deleted_at.is_(None),
                CaseHearing.status == HearingStatus.SCHEDULED,
                CaseHearing.hearing_at >= now,
            )
            .order_by(CaseHearing.hearing_at.asc())
            .first()
        )

        # 2. Overdue tasks count
        overdue_tasks_count = (
            self.db.query(CaseTask)
            .filter(
                CaseTask.case_id == case_id,
                CaseTask.deleted_at.is_(None),
                CaseTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]),
                CaseTask.due_date.isnot(None),
                CaseTask.due_date < now,
            )
            .count()
        )

        # 3. Upcoming deadlines count
        upcoming_deadlines_count = (
            self.db.query(CaseDeadline)
            .filter(
                CaseDeadline.case_id == case_id,
                CaseDeadline.deleted_at.is_(None),
                CaseDeadline.status.in_([DeadlineStatus.UPCOMING, DeadlineStatus.DUE]),
                CaseDeadline.deadline_at >= now,
            )
            .count()
        )

        # 4. Unreviewed evidence count (active evidence not marked as exhibit or without tags)
        unreviewed_evidence_count = (
            self.db.query(Evidence)
            .filter(
                Evidence.case_id == case_id,
                Evidence.deleted_at.is_(None),
                Evidence.status == "ACTIVE",
            )
            .count()
        )

        # 5. Latest activity timestamp
        latest_event = (
            self.db.query(CaseTimelineEvent)
            .filter(CaseTimelineEvent.case_id == case_id)
            .order_by(CaseTimelineEvent.created_at.desc())
            .first()
        )

        return CaseHealthSummaryResponse(
            case_id=case_id,
            has_upcoming_hearing=next_hearing is not None,
            next_hearing_date=next_hearing.hearing_at if next_hearing else None,
            next_hearing_court=next_hearing.court_name if next_hearing else None,
            overdue_tasks_count=overdue_tasks_count,
            upcoming_deadlines_count=upcoming_deadlines_count,
            unreviewed_evidence_count=unreviewed_evidence_count,
            latest_activity_at=latest_event.created_at if latest_event else None,
        )

    # --------------------------------------------------------------------------
    # FILTERED SEARCH METHODS
    # --------------------------------------------------------------------------

    def get_filtered_tasks(
        self,
        user: User,
        case_id: uuid.UUID,
        q: str | None = None,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        owner_user_id: uuid.UUID | None = None,
        linked_hearing_id: uuid.UUID | None = None,
        linked_evidence_id: uuid.UUID | None = None,
        is_overdue: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Server-side filtered and paginated search for case tasks."""
        authorize_case_access(self.db, user, case_id)
        limit = min(max(limit, 1), 100)

        query = self.db.query(CaseTask).filter(
            CaseTask.case_id == case_id, CaseTask.deleted_at.is_(None)
        )

        if q:
            term = f"%{q.strip()}%"
            query = query.filter(
                sa_or(CaseTask.title.ilike(term), CaseTask.description.ilike(term))
            )

        if status is not None:
            query = query.filter(CaseTask.status == status)

        if priority is not None:
            query = query.filter(CaseTask.priority == priority)

        if owner_user_id is not None:
            query = query.filter(CaseTask.owner_user_id == owner_user_id)

        if linked_hearing_id is not None:
            query = query.filter(CaseTask.linked_hearing_id == linked_hearing_id)

        if linked_evidence_id is not None:
            query = query.filter(CaseTask.linked_evidence_id == linked_evidence_id)

        if is_overdue is not None:
            now = datetime.now(UTC)
            if is_overdue:
                query = query.filter(
                    CaseTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]),
                    CaseTask.due_date.isnot(None),
                    CaseTask.due_date < now,
                )
            else:
                query = query.filter(
                    sa_or(CaseTask.due_date.is_(None), CaseTask.due_date >= now)
                )

        query = query.order_by(CaseTask.created_at.desc(), CaseTask.id.desc())
        total = query.count()
        tasks = query.offset(skip).limit(limit).all()
        return {"items": tasks, "total": total, "skip": skip, "limit": limit}

    def get_filtered_deadlines(
        self,
        user: User,
        case_id: uuid.UUID,
        q: str | None = None,
        status: DeadlineStatus | None = None,
        deadline_type: DeadlineType | None = None,
        linked_hearing_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Server-side filtered and paginated search for case deadlines."""
        authorize_case_access(self.db, user, case_id)
        limit = min(max(limit, 1), 100)

        query = self.db.query(CaseDeadline).filter(
            CaseDeadline.case_id == case_id, CaseDeadline.deleted_at.is_(None)
        )

        if q:
            term = f"%{q.strip()}%"
            query = query.filter(
                sa_or(CaseDeadline.title.ilike(term), CaseDeadline.description.ilike(term))
            )

        if status is not None:
            query = query.filter(CaseDeadline.status == status)

        if deadline_type is not None:
            query = query.filter(CaseDeadline.deadline_type == deadline_type)

        if linked_hearing_id is not None:
            query = query.filter(CaseDeadline.linked_hearing_id == linked_hearing_id)

        query = query.order_by(CaseDeadline.deadline_at.asc(), CaseDeadline.id.asc())
        total = query.count()
        deadlines = query.offset(skip).limit(limit).all()
        return {"items": deadlines, "total": total, "skip": skip, "limit": limit}

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
            court_number=req.court_number,
            hearing_type=req.hearing_type,
            next_date=req.next_date,
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
        if req.court_number is not None:
            hearing.court_number = req.court_number
        if req.hearing_type is not None:
            hearing.hearing_type = req.hearing_type
        if req.next_date is not None:
            hearing.next_date = req.next_date
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

    def adjourn_hearing(
        self, user: User, case_id: uuid.UUID, hearing_id: uuid.UUID, req: CaseHearingAdjournRequest
    ) -> CaseHearing:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)

        hearing = (
            self.db.query(CaseHearing)
            .filter(CaseHearing.id == hearing_id, CaseHearing.case_id == case_id, CaseHearing.deleted_at.is_(None))
            .first()
        )
        if not hearing:
            raise ResourceNotFoundError("Hearing not found")

        hearing.status = HearingStatus.ADJOURNED
        next_dt = req.next_date.replace(tzinfo=UTC) if req.next_date.tzinfo is None else req.next_date
        hearing.next_date = next_dt
        if req.purpose:
            hearing.purpose = req.purpose
        if req.notes:
            hearing.notes = f"{hearing.notes}\n[Adjournment Note]: {req.notes}" if hearing.notes else req.notes

        self._log_audit("HEARING_ADJOURNED", user.id, {"case_id": str(case_id), "hearing_id": str(hearing.id), "next_date": next_dt.isoformat()})
        self._record_activity(
            case_id,
            user.id,
            "HEARING_ADJOURNED",
            f"Hearing at '{hearing.court_name}' adjourned to {next_dt.strftime('%d %b %Y')}",
        )
        self.db.commit()
        self.db.refresh(hearing)
        return hearing

    def complete_hearing(
        self, user: User, case_id: uuid.UUID, hearing_id: uuid.UUID, req: CaseHearingCompleteRequest
    ) -> CaseHearing:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)

        hearing = (
            self.db.query(CaseHearing)
            .filter(CaseHearing.id == hearing_id, CaseHearing.case_id == case_id, CaseHearing.deleted_at.is_(None))
            .first()
        )
        if not hearing:
            raise ResourceNotFoundError("Hearing not found")

        hearing.status = HearingStatus.CONCLUDED
        if req.notes:
            hearing.notes = f"{hearing.notes}\n[Proceedings Concluded]: {req.notes}" if hearing.notes else req.notes

        self._log_audit("HEARING_COMPLETED", user.id, {"case_id": str(case_id), "hearing_id": str(hearing.id)})
        self._record_activity(
            case_id,
            user.id,
            "HEARING_COMPLETED",
            f"Hearing at '{hearing.court_name}' concluded",
        )
        self.db.commit()
        self.db.refresh(hearing)
        return hearing

    def import_ecourts_hearing(
        self, user: User, case_id: uuid.UUID, req: CaseHearingECourtsImportRequest
    ) -> CaseHearing:
        authorize_case_modification(self.db, user, case_id)
        self._check_case_active_for_mutations(case_id)

        from app.domain.ai.legal_source_providers.ecourts_provider import ECourtsProvider
        processed = ECourtsProvider.process_imported_hearing(req.model_dump(), str(user.id))

        hearing_at = req.hearing_at.replace(tzinfo=UTC) if req.hearing_at.tzinfo is None else req.hearing_at

        hearing = CaseHearing(
            id=generate_uuid7(),
            case_id=case_id,
            court_name=req.court_name,
            hearing_at=hearing_at,
            purpose=req.purpose,
            bench_or_coram=req.bench_or_coram,
            court_number=req.court_number,
            hearing_type=req.hearing_type,
            notes=req.notes,
            status=HearingStatus.SCHEDULED,
            source_type=HearingSourceType.CAUSE_LIST,
            source_reference=req.source_reference,
            is_confirmed=True,
            created_by_user_id=user.id,
            metadata_={
                "source": processed["source"],
                "retrieval_method": processed["retrieval_method"],
                "disclaimer": processed["disclaimer"],
            },
        )
        self.db.add(hearing)
        self.db.flush()

        self._log_audit("HEARING_IMPORTED_ECOURTS", user.id, {"case_id": str(case_id), "hearing_id": str(hearing.id), "source_ref": req.source_reference})
        self._record_activity(
            case_id,
            user.id,
            "HEARING_SCHEDULED",
            f"Hearing at {hearing.court_name} listed from official cause list ({req.source_reference})",
        )
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
