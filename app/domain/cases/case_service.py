import uuid
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from sqlalchemy import and_, func, or_
from sqlalchemy import case as sql_case
from sqlalchemy import false as sql_false
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import (
    _get_case_participant,
    authorize_case_access,
    authorize_case_deletion,
    authorize_case_modification,
    authorize_participant_management,
)
from app.core.exceptions import (
    AuthorizationError,
    ResourceNotFoundError,
    ValidationError,
)
from app.core.identifiers import generate_uuid7
from app.models.case import (
    Case,
    CaseParticipant,
    CaseStatus,
    CaseTimelineEvent,
    ParticipantRole,
    ParticipantStatus,
)
from app.models.case_intelligence import (
    CaseEvidenceGap,
    CaseFact,
    CaseRiskIndicator,
    LegalIssue,
    RiskSeverity,
)
from app.models.consultation import Consultation, ConsultationStatus
from app.models.document import Document, DocumentSecurityStatus
from app.models.note import CaseNote, CaseNoteVisibility
from app.models.notification import NotificationType
from app.models.task import CaseTask, TaskPriority, TaskSourceType, TaskStatus
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole
from app.models.workflow import CaseDeadline, DeadlineStatus
from app.schemas.case import (
    CaseCreate,
    CaseUpdate,
    GrantLawyerAccessRequest,
    ParticipantAdd,
    ParticipantUpdate,
)
from app.schemas.note import CaseNoteCreate, CaseNoteUpdate
from app.schemas.task import CaseTaskCreate, CaseTaskUpdate
from app.domain.auth.auth_service import AuthService
from app.domain.notifications.notification_service import NotificationService
from app.domain.users.user_service import UserService

ALLOWED_CASE_TRANSITIONS: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.OPEN: {
        CaseStatus.OPEN,
        CaseStatus.IN_PROGRESS,
        CaseStatus.CLOSED,
        CaseStatus.CANCELLED,
    },
    CaseStatus.IN_PROGRESS: {
        CaseStatus.IN_PROGRESS,
        CaseStatus.CLOSED,
        CaseStatus.CANCELLED,
    },
    CaseStatus.CLOSED: {CaseStatus.CLOSED},
    CaseStatus.CANCELLED: {CaseStatus.CANCELLED},
}


class CaseService:
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
        self.notification_service = NotificationService(db)

    def _log_audit(self, event_type: str, user_id: uuid.UUID, metadata: dict):
        self.auth_service.log_audit_event(
            event_type, user_id, metadata, action="case_mutation"
        )

    def create_case(self, user: User, req: CaseCreate) -> Case:
        case_id = generate_uuid7()
        now = datetime.now(UTC)
        new_case = Case(
            id=case_id,
            title=req.title,
            description=req.description,
            status=CaseStatus.OPEN,
        )
        self.db.add(new_case)

        # Add creator as OWNER participant
        participant = CaseParticipant(
            id=generate_uuid7(),
            case_id=case_id,
            user_id=user.id,
            participant_role=ParticipantRole.OWNER,
            status=ParticipantStatus.ACTIVE,
            joined_at=now,
        )
        self.db.add(participant)
        self.db.commit()
        self.db.refresh(new_case)

        self._log_audit("CASE_CREATED", user.id, {"case_id": str(case_id)})
        self.record_case_activity(case_id, user.id, "CASE_CREATED", "Case was created")
        self.notification_service.create_notification(
            user_id=user.id,
            type=NotificationType.CASE_CREATED,
            title="Case Created",
            message=f"Case '{new_case.title}' was created successfully.",
            case_id=case_id,
        )
        return new_case

    def get_cases(
        self,
        user: User,
        status: CaseStatus | None = None,
        search: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        limit = min(max(limit, 1), 100)
        if user.role == UserRole.ADMIN:
            query = self.db.query(Case).filter(Case.deleted_at.is_(None))
        else:
            query = (
                self.db.query(Case)
                .join(CaseParticipant)
                .filter(
                    CaseParticipant.user_id == user.id,
                    CaseParticipant.status == ParticipantStatus.ACTIVE,
                    Case.deleted_at.is_(None),
                )
            )

        if status is not None:
            query = query.filter(Case.status == status)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(Case.title.ilike(term), Case.description.ilike(term))
            )

        if created_after is not None:
            query = query.filter(Case.created_at >= created_after)

        if created_before is not None:
            query = query.filter(Case.created_at <= created_before)

        total = query.count()
        query = query.order_by(Case.created_at.desc(), Case.id.desc())
        cases = query.offset(skip).limit(limit).all()
        return {"items": cases, "total": total, "skip": skip, "limit": limit}

    def get_case_by_id(self, user: User, case_id: uuid.UUID) -> Case:
        return authorize_case_access(self.db, user, case_id)

    def get_workspace(self, user: User, case_id: uuid.UUID) -> dict:
        case_ = authorize_case_access(self.db, user, case_id)

        # Participants
        participants = (
            self.db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .all()
        )

        # Role determination
        current_participant = next(
            (p for p in participants if p.user_id == user.id), None
        )
        role = current_participant.participant_role if current_participant else None
        if user.role == UserRole.ADMIN:
            role = ParticipantRole.OWNER

        # Permissions calculation
        permissions = []
        if case_.status in (CaseStatus.OPEN, CaseStatus.IN_PROGRESS):
            if role == ParticipantRole.OWNER:
                permissions.extend(
                    [
                        "UPDATE_CASE",
                        "DELETE_CASE",
                        "MANAGE_PARTICIPANTS",
                        "UPLOAD_DOCUMENT",
                        "DELETE_DOCUMENT",
                        "REQUEST_CONSULTATION",
                        "CREATE_TASK",
                        "UPDATE_TASK",
                        "DELETE_TASK",
                        "CREATE_NOTE",
                        "UPDATE_NOTE",
                        "DELETE_NOTE",
                    ]
                )
            elif role == ParticipantRole.LAWYER:
                permissions.extend(
                    [
                        "UPLOAD_DOCUMENT",
                        "CREATE_TASK",
                        "UPDATE_TASK",
                        "CREATE_NOTE",
                        "UPDATE_NOTE",
                    ]
                )

        if (
            role
            in (ParticipantRole.OWNER, ParticipantRole.LAWYER, ParticipantRole.VIEWER)
            or user.role == UserRole.ADMIN
        ):
            permissions.extend(
                ["VIEW_DOCUMENTS", "VIEW_TASKS", "VIEW_NOTES", "VIEW_TIMELINE"]
            )

        # Lawyer profile if any
        lawyer = None
        lawyer_participant = next(
            (p for p in participants if p.participant_role == ParticipantRole.LAWYER),
            None,
        )
        if lawyer_participant:
            lawyer = (
                self.db.query(LawyerProfile)
                .filter(LawyerProfile.user_id == lawyer_participant.user_id)
                .first()
            )

        # Document metrics & summary
        docs_rows = (
            self.db.query(Document.security_status, Document.document_type)
            .filter(Document.case_id == case_id, Document.deleted_at.is_(None))
            .all()
        )
        doc_count = len(docs_rows)
        safe_docs = sum(1 for d in docs_rows if d[0] == DocumentSecurityStatus.SAFE)
        pending_docs = sum(1 for d in docs_rows if d[0] in (DocumentSecurityStatus.PENDING, DocumentSecurityStatus.VALIDATING))
        quarantined_docs = sum(1 for d in docs_rows if d[0] in (DocumentSecurityStatus.QUARANTINED, DocumentSecurityStatus.SCANNING))
        rejected_docs = sum(1 for d in docs_rows if d[0] == DocumentSecurityStatus.REJECTED)
        by_category: dict[str, int] = {}
        for d in docs_rows:
            cat_str = d[1].value if hasattr(d[1], "value") else str(d[1])
            by_category[cat_str] = by_category.get(cat_str, 0) + 1

        documents_summary = {
            "total": doc_count,
            "safe": safe_docs,
            "pending": pending_docs,
            "quarantined": quarantined_docs,
            "rejected": rejected_docs,
            "by_category": by_category,
        }

        # Task summary breakdown using a single SQL aggregation query
        task_row = (
            self.db.query(
                func.count(CaseTask.id).label("total"),
                func.count(
                    sql_case((CaseTask.status == TaskStatus.PENDING, CaseTask.id))
                ).label("pending"),
                func.count(
                    sql_case((CaseTask.status == TaskStatus.IN_PROGRESS, CaseTask.id))
                ).label("in_progress"),
                func.count(
                    sql_case((CaseTask.status == TaskStatus.COMPLETED, CaseTask.id))
                ).label("completed"),
                func.count(
                    sql_case((CaseTask.status == TaskStatus.CANCELLED, CaseTask.id))
                ).label("cancelled"),
            )
            .filter(CaseTask.case_id == case_id, CaseTask.deleted_at.is_(None))
            .first()
        )
        tasks_summary = {
            "total": task_row.total if task_row else 0,
            "pending": task_row.pending if task_row else 0,
            "in_progress": task_row.in_progress if task_row else 0,
            "completed": task_row.completed if task_row else 0,
            "cancelled": task_row.cancelled if task_row else 0,
        }

        # Upcoming deadlines (due tasks and upcoming consultations)
        now = datetime.now(UTC)
        upcoming_tasks = (
            self.db.query(CaseTask)
            .filter(
                CaseTask.case_id == case_id,
                CaseTask.deleted_at.is_(None),
                CaseTask.due_date.isnot(None),
                CaseTask.due_date >= now,
                CaseTask.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
            )
            .order_by(CaseTask.due_date.asc())
            .limit(5)
            .all()
        )
        upcoming_deadlines = [
            {
                "type": "TASK_DUE",
                "id": str(t.id),
                "title": t.title,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "priority": (
                    t.priority.value
                    if hasattr(t.priority, "value")
                    else str(t.priority)
                ),
            }
            for t in upcoming_tasks
        ]

        upcoming_consultations = (
            self.db.query(Consultation)
            .filter(
                Consultation.case_id == case_id,
                Consultation.scheduled_at >= now,
                Consultation.status.in_(
                    [ConsultationStatus.REQUESTED, ConsultationStatus.SCHEDULED]
                ),
            )
            .order_by(Consultation.scheduled_at.asc())
            .limit(3)
            .all()
        )
        for c in upcoming_consultations:
            upcoming_deadlines.append(
                {
                    "type": "CONSULTATION",
                    "id": str(c.id),
                    "title": "Scheduled Consultation",
                    "due_date": c.scheduled_at.isoformat(),
                    "status": c.status.value,
                }
            )

        upcoming_case_deadlines = (
            self.db.query(CaseDeadline)
            .filter(
                CaseDeadline.case_id == case_id,
                CaseDeadline.deleted_at.is_(None),
                CaseDeadline.deadline_at >= now,
                CaseDeadline.status.in_([DeadlineStatus.UPCOMING, DeadlineStatus.DUE]),
            )
            .order_by(CaseDeadline.deadline_at.asc())
            .limit(5)
            .all()
        )
        for cd in upcoming_case_deadlines:
            upcoming_deadlines.append(
                {
                    "type": "CASE_DEADLINE",
                    "id": str(cd.id),
                    "title": cd.title,
                    "due_date": cd.deadline_at.isoformat(),
                    "deadline_type": cd.deadline_type.value if hasattr(cd.deadline_type, "value") else str(cd.deadline_type),
                }
            )

        # Notes count visible to current user
        notes_query = self.db.query(CaseNote).filter(
            CaseNote.case_id == case_id, CaseNote.deleted_at.is_(None)
        )
        notes_query = self._apply_note_visibility_filter(notes_query, user, case_id)
        notes_count = notes_query.count()

        # Intelligence summary from persisted records (zero LLM calls)
        facts_count = self.db.query(func.count(CaseFact.id)).filter(CaseFact.case_id == case_id, CaseFact.deleted_at.is_(None)).scalar() or 0
        issues_count = self.db.query(func.count(LegalIssue.id)).filter(LegalIssue.case_id == case_id, LegalIssue.deleted_at.is_(None)).scalar() or 0
        gaps_count = self.db.query(func.count(CaseEvidenceGap.id)).filter(CaseEvidenceGap.case_id == case_id, CaseEvidenceGap.deleted_at.is_(None)).scalar() or 0
        risks_count = self.db.query(func.count(CaseRiskIndicator.id)).filter(CaseRiskIndicator.case_id == case_id, CaseRiskIndicator.deleted_at.is_(None)).scalar() or 0
        critical_risks_count = self.db.query(func.count(CaseRiskIndicator.id)).filter(CaseRiskIndicator.case_id == case_id, CaseRiskIndicator.severity == RiskSeverity.CRITICAL, CaseRiskIndicator.deleted_at.is_(None)).scalar() or 0

        intelligence_summary = {
            "facts_count": facts_count,
            "issues_count": issues_count,
            "evidence_gaps_count": gaps_count,
            "risks_count": risks_count,
            "critical_risks_count": critical_risks_count,
        }

        # Recent activities
        recent_activities = (
            self.db.query(CaseTimelineEvent)
            .filter(CaseTimelineEvent.case_id == case_id)
            .order_by(CaseTimelineEvent.created_at.desc(), CaseTimelineEvent.id.desc())
            .limit(5)
            .all()
        )

        return {
            "case": case_,
            "effective_permissions": permissions,
            "participants": participants,
            "lawyer": lawyer,
            "document_count": doc_count,
            "documents_summary": documents_summary,
            "tasks_summary": tasks_summary,
            "upcoming_deadlines": upcoming_deadlines,
            "notes_count": notes_count,
            "recent_activities": recent_activities,
            "intelligence_summary": intelligence_summary,
        }

    def update_case(self, user: User, case_id: uuid.UUID, req: CaseUpdate) -> Case:
        case_ = authorize_case_modification(self.db, user, case_id)

        updated = {}
        dump = req.model_dump(exclude_unset=True)

        if "status" in dump and dump["status"] is not None:
            try:
                new_status = CaseStatus(dump["status"])
            except ValueError as e:
                raise ValidationError(f"Invalid case status: {dump['status']}") from e

            allowed = ALLOWED_CASE_TRANSITIONS.get(case_.status, {case_.status})
            if new_status not in allowed:
                raise ValidationError(
                    f"Cannot transition case status from '{case_.status.value}' to '{new_status.value}'"
                )

            if new_status != case_.status:
                old_status = case_.status
                case_.status = new_status
                updated["status"] = new_status.value
                self._log_audit(
                    "CASE_STATUS_CHANGED",
                    user.id,
                    {
                        "case_id": str(case_id),
                        "from_status": old_status.value,
                        "to_status": new_status.value,
                    },
                )
                self.record_case_activity(
                    case_id,
                    user.id,
                    "STATUS_CHANGED",
                    f"Case status changed from {old_status.value} to {new_status.value}",
                    {"from_status": old_status.value, "to_status": new_status.value},
                )
                active_ps = (
                    self.db.query(CaseParticipant)
                    .filter(
                        CaseParticipant.case_id == case_id,
                        CaseParticipant.status == ParticipantStatus.ACTIVE,
                    )
                    .all()
                )
                for p in active_ps:
                    if p.user_id != user.id:
                        self.notification_service.create_notification(
                            user_id=p.user_id,
                            type=NotificationType.CASE_STATUS_CHANGED,
                            title="Case Status Updated",
                            message=f"Case status changed to {new_status.value}.",
                            case_id=case_id,
                        )

        if "title" in dump and dump["title"] is not None:
            case_.title = dump["title"]
            updated["title"] = dump["title"]

        if "description" in dump and dump["description"] is not None:
            case_.description = dump["description"]
            updated["description"] = dump["description"]

        if updated:
            self.db.commit()
            self.db.refresh(case_)
            other_fields = [k for k in updated if k != "status"]
            if other_fields:
                self._log_audit(
                    "CASE_UPDATED",
                    user.id,
                    {"case_id": str(case_id), "fields": other_fields},
                )
                self.record_case_activity(
                    case_id,
                    user.id,
                    "CASE_UPDATED",
                    "Case details were updated",
                    {"fields": other_fields},
                )

        return case_

    def delete_case(self, user: User, case_id: uuid.UUID):
        case_ = authorize_case_deletion(self.db, user, case_id)

        now = datetime.now(UTC)
        case_.deleted_at = now
        self.db.commit()

        self._log_audit("CASE_DELETED", user.id, {"case_id": str(case_id)})

    def add_participant(
        self, user: User, case_id: uuid.UUID, req: ParticipantAdd
    ) -> CaseParticipant:
        authorize_participant_management(self.db, user, case_id)

        user_service = UserService(self.db)
        target_user = user_service.get_user_by_id(req.user_id)
        if not target_user:
            raise ResourceNotFoundError("Target user not found")

        try:
            requested_role = ParticipantRole(req.participant_role)
        except ValueError as e:
            raise ValidationError(
                f"Invalid participant role: {req.participant_role}"
            ) from e

        if (
            requested_role == ParticipantRole.LAWYER
            and target_user.role != UserRole.LAWYER
        ):
            raise ValidationError(
                "Only users with the LAWYER role can be added as LAWYER participants"
            )

        if requested_role == ParticipantRole.OWNER and target_user.role not in (
            UserRole.CLIENT,
            UserRole.LAWYER,
        ):
            raise ValidationError(
                "Only CLIENT or LAWYER can be added as OWNER participants"
            )

        if target_user.account_status != AccountStatus.ACTIVE:
            raise ValidationError(
                "Cannot add inactive or suspended user as participant"
            )

        # Check if already a participant
        existing = (
            self.db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.user_id == req.user_id,
            )
            .first()
        )

        now = datetime.now(UTC)
        if existing:
            if existing.status == ParticipantStatus.ACTIVE:
                raise ValidationError("User is already an active participant")
            else:
                existing.status = ParticipantStatus.ACTIVE
                existing.participant_role = requested_role
                existing.ended_at = None
                self.db.commit()
                self.db.refresh(existing)
                self._log_audit(
                    "PARTICIPANT_REACTIVATED",
                    user.id,
                    {"case_id": str(case_id), "target_user_id": str(req.user_id)},
                )
                self.record_case_activity(
                    case_id,
                    user.id,
                    "PARTICIPANT_ADDED",
                    "Participant was added",
                    {"target_user_id": str(req.user_id), "role": requested_role.value},
                )
                if requested_role == ParticipantRole.LAWYER:
                    self.record_case_activity(
                        case_id,
                        user.id,
                        "LAWYER_SELECTED",
                        "Lawyer was selected",
                        {"target_user_id": str(req.user_id)},
                    )
                return existing

        participant = CaseParticipant(
            id=generate_uuid7(),
            case_id=case_id,
            user_id=req.user_id,
            participant_role=requested_role,
            status=ParticipantStatus.ACTIVE,
            joined_at=now,
        )
        self.db.add(participant)
        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            raise ValidationError("User is already an active participant") from e

        self.db.refresh(participant)

        self._log_audit(
            "PARTICIPANT_ADDED",
            user.id,
            {"case_id": str(case_id), "target_user_id": str(req.user_id)},
        )
        self.record_case_activity(
            case_id,
            user.id,
            "PARTICIPANT_ADDED",
            "Participant was added",
            {"target_user_id": str(req.user_id), "role": requested_role.value},
        )
        if requested_role == ParticipantRole.LAWYER:
            self.record_case_activity(
                case_id,
                user.id,
                "LAWYER_SELECTED",
                "Lawyer was selected",
                {"target_user_id": str(req.user_id)},
            )
            self.notification_service.create_notification(
                user_id=req.user_id,
                type=NotificationType.LAWYER_ASSIGNED,
                title="Assigned to Case",
                message="You have been assigned as lawyer to this case.",
                case_id=case_id,
            )
        else:
            self.notification_service.create_notification(
                user_id=req.user_id,
                type=NotificationType.PARTICIPANT_ADDED,
                title="Added to Case",
                message=f"You were added to the case as {requested_role.value}.",
                case_id=case_id,
            )
        return participant

    def grant_lawyer_access(
        self, user: User, case_id: uuid.UUID, req: GrantLawyerAccessRequest
    ) -> CaseParticipant:
        # 1. Authorize: authenticated user must be the case owner (or admin)
        authorize_participant_management(self.db, user, case_id)

        # 2. Target lawyer user validation
        user_service = UserService(self.db)
        target_user = user_service.get_user_by_id(req.lawyer_user_id)
        if not target_user:
            raise ResourceNotFoundError("Target lawyer not found")

        if target_user.role != UserRole.LAWYER:
            raise ValidationError(
                "Only users with the LAWYER role can be granted lawyer access"
            )

        if target_user.account_status != AccountStatus.ACTIVE:
            raise ValidationError("Cannot grant access to an inactive or suspended lawyer")

        # 3. Target lawyer profile & verification status check
        lawyer_profile = (
            self.db.query(LawyerProfile)
            .filter(
                LawyerProfile.user_id == req.lawyer_user_id,
                LawyerProfile.deleted_at.is_(None),
            )
            .first()
        )
        if not lawyer_profile or lawyer_profile.verification_status != "APPROVED":
            raise ValidationError("Case access can only be granted to verified lawyers")

        # 4. Consultation relationship check
        # Must have an existing valid consultation between this client and lawyer, or linked to this case
        client_profile = (
            self.db.query(ClientProfile)
            .filter(ClientProfile.user_id == user.id)
            .first()
        )

        consultation_query = self.db.query(Consultation).filter(
            Consultation.lawyer_id == lawyer_profile.id,
            Consultation.status.in_(
                [
                    ConsultationStatus.ACCEPTED,
                    ConsultationStatus.PAID,
                    ConsultationStatus.SCHEDULED,
                    ConsultationStatus.IN_PROGRESS,
                    ConsultationStatus.COMPLETED,
                ]
            ),
            Consultation.deleted_at.is_(None),
        )

        if req.consultation_id:
            consultation_query = consultation_query.filter(
                Consultation.id == req.consultation_id
            )

        if client_profile:
            consultation_query = consultation_query.filter(
                or_(
                    Consultation.client_id == client_profile.id,
                    Consultation.case_id == case_id,
                )
            )
        else:
            consultation_query = consultation_query.filter(
                Consultation.case_id == case_id
            )

        valid_consultation = consultation_query.first()
        if not valid_consultation:
            raise ValidationError(
                "A confirmed or completed consultation with this lawyer is required before granting case access"
            )

        # 5. Check if already an active participant
        existing = (
            self.db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.user_id == req.lawyer_user_id,
            )
            .first()
        )

        now = datetime.now(UTC)
        if existing:
            if existing.status == ParticipantStatus.ACTIVE:
                raise ValidationError("Lawyer is already an active participant of this case")
            else:
                existing.status = ParticipantStatus.ACTIVE
                existing.participant_role = ParticipantRole.LAWYER
                existing.ended_at = None
                self.db.commit()
                self.db.refresh(existing)
                self._log_audit(
                    "LAWYER_CASE_ACCESS_GRANTED",
                    user.id,
                    {
                        "case_id": str(case_id),
                        "lawyer_user_id": str(req.lawyer_user_id),
                        "consultation_id": str(valid_consultation.id),
                    },
                )
                self.record_case_activity(
                    case_id,
                    user.id,
                    "LAWYER_CASE_ACCESS_GRANTED",
                    f"Lawyer access granted via consultation {valid_consultation.id}",
                    {
                        "lawyer_user_id": str(req.lawyer_user_id),
                        "consultation_id": str(valid_consultation.id),
                    },
                )
                self.notification_service.create_notification(
                    user_id=req.lawyer_user_id,
                    type=NotificationType.LAWYER_ASSIGNED,
                    title="Case Access Granted",
                    message="You have been formally granted lawyer access to this case.",
                    case_id=case_id,
                )
                return existing

        participant = CaseParticipant(
            id=generate_uuid7(),
            case_id=case_id,
            user_id=req.lawyer_user_id,
            participant_role=ParticipantRole.LAWYER,
            status=ParticipantStatus.ACTIVE,
            joined_at=now,
        )
        self.db.add(participant)
        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            raise ValidationError(
                "Lawyer is already an active participant of this case"
            ) from e

        self.db.refresh(participant)

        self._log_audit(
            "LAWYER_CASE_ACCESS_GRANTED",
            user.id,
            {
                "case_id": str(case_id),
                "lawyer_user_id": str(req.lawyer_user_id),
                "consultation_id": str(valid_consultation.id),
            },
        )
        self.record_case_activity(
            case_id,
            user.id,
            "LAWYER_CASE_ACCESS_GRANTED",
            f"Lawyer access granted via consultation {valid_consultation.id}",
            {
                "lawyer_user_id": str(req.lawyer_user_id),
                "consultation_id": str(valid_consultation.id),
            },
        )
        self.notification_service.create_notification(
            user_id=req.lawyer_user_id,
            type=NotificationType.LAWYER_ASSIGNED,
            title="Case Access Granted",
            message="You have been formally granted lawyer access to this case.",
            case_id=case_id,
        )
        return participant

    def get_participants(
        self, user: User, case_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> dict:
        authorize_case_access(self.db, user, case_id)
        limit = min(max(limit, 1), 100)
        query = (
            self.db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .order_by(CaseParticipant.joined_at.desc(), CaseParticipant.id.asc())
        )

        total = query.count()
        participants = query.offset(skip).limit(limit).all()
        return {"items": participants, "total": total, "skip": skip, "limit": limit}

    def update_participant_role(
        self,
        user: User,
        case_id: uuid.UUID,
        target_user_id: uuid.UUID,
        req: ParticipantUpdate,
    ) -> CaseParticipant:
        authorize_participant_management(self.db, user, case_id)

        if user.id == target_user_id:
            raise ValidationError("Owner cannot modify their own participant role.")

        participant = (
            self.db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.user_id == target_user_id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .first()
        )

        if not participant:
            raise ResourceNotFoundError("Participant not found")

        try:
            requested_role = ParticipantRole(req.participant_role)
        except ValueError as e:
            raise ValidationError(
                f"Invalid participant role: {req.participant_role}"
            ) from e

        # Prevent demoting the final owner
        if (
            participant.participant_role == ParticipantRole.OWNER
            and requested_role != ParticipantRole.OWNER
        ):
            active_owners = (
                self.db.query(CaseParticipant)
                .filter(
                    CaseParticipant.case_id == case_id,
                    CaseParticipant.participant_role == ParticipantRole.OWNER,
                    CaseParticipant.status == ParticipantStatus.ACTIVE,
                )
                .count()
            )
            if active_owners <= 1:
                raise ValidationError("Cannot demote the final owner of the case.")

        # Validation matching add_participant
        if requested_role == ParticipantRole.LAWYER:
            user_service = UserService(self.db)
            target_user = user_service.get_user_by_id(target_user_id)
            if target_user and target_user.role != UserRole.LAWYER:
                raise ValidationError(
                    "Only users with the LAWYER role can be assigned as LAWYER participants"
                )

        if requested_role == ParticipantRole.OWNER:
            user_service = UserService(self.db)
            target_user = user_service.get_user_by_id(target_user_id)
            if target_user and target_user.role not in (
                UserRole.CLIENT,
                UserRole.LAWYER,
            ):
                raise ValidationError(
                    "Only CLIENT or LAWYER can be added as OWNER participants"
                )

        participant.participant_role = requested_role
        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            raise ValidationError(
                "Concurrency error while updating participant role"
            ) from e

        self.db.refresh(participant)

        self._log_audit(
            "PARTICIPANT_ROLE_UPDATED",
            user.id,
            {
                "case_id": str(case_id),
                "target_user_id": str(target_user_id),
                "new_role": req.participant_role,
            },
        )
        self.record_case_activity(
            case_id,
            user.id,
            "PARTICIPANT_ROLE_CHANGED",
            "Participant role was changed",
            {"target_user_id": str(target_user_id), "new_role": req.participant_role},
        )
        return participant

    def remove_participant(
        self, user: User, case_id: uuid.UUID, target_user_id: uuid.UUID
    ):
        authorize_participant_management(self.db, user, case_id)

        if user.id == target_user_id:
            raise ValidationError("Owner cannot remove themselves from the case.")

        participant = (
            self.db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.user_id == target_user_id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .first()
        )

        if not participant:
            raise ResourceNotFoundError("Participant not found")

        # Prevent removing the final owner
        if participant.participant_role == ParticipantRole.OWNER:
            active_owners = (
                self.db.query(CaseParticipant)
                .filter(
                    CaseParticipant.case_id == case_id,
                    CaseParticipant.participant_role == ParticipantRole.OWNER,
                    CaseParticipant.status == ParticipantStatus.ACTIVE,
                )
                .count()
            )
            if active_owners <= 1:
                raise ValidationError("Cannot remove the final owner of the case.")

        participant.status = ParticipantStatus.INACTIVE
        participant.ended_at = datetime.now(UTC)
        self.db.commit()

        self._log_audit(
            "PARTICIPANT_REMOVED",
            user.id,
            {"case_id": str(case_id), "target_user_id": str(target_user_id)},
        )
        self.record_case_activity(
            case_id,
            user.id,
            "PARTICIPANT_REMOVED",
            "Participant was removed",
            {"target_user_id": str(target_user_id)},
        )

    def get_timeline(
        self, user: User, case_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> dict:
        authorize_case_access(self.db, user, case_id)
        limit = min(max(limit, 1), 100)
        query = (
            self.db.query(CaseTimelineEvent)
            .filter(CaseTimelineEvent.case_id == case_id)
            .order_by(CaseTimelineEvent.created_at.desc(), CaseTimelineEvent.id.desc())
        )
        total = query.count()
        events = query.offset(skip).limit(limit).all()
        return {"items": events, "total": total, "skip": skip, "limit": limit}

    def record_case_activity(
        self,
        case_id: uuid.UUID,
        actor_id: uuid.UUID | None,
        event_type: str,
        description: str,
        metadata: dict | None = None,
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
        self.db.commit()
        self.db.refresh(event)
        return event

    # --------------------------------------------------------------------------
    # TASKS MANAGEMENT
    # --------------------------------------------------------------------------

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
        },
        TaskStatus.CANCELLED: {
            TaskStatus.CANCELLED,
        },
    }

    def create_task(
        self, user: User, case_id: uuid.UUID, req: CaseTaskCreate
    ) -> CaseTask:
        authorize_case_access(self.db, user, case_id)

        case_obj = self.db.query(Case).filter(Case.id == case_id, Case.deleted_at.is_(None)).first()
        if case_obj and case_obj.status in (CaseStatus.CLOSED, CaseStatus.CANCELLED):
            raise ValidationError("Tasks cannot be created on closed or cancelled cases")

        if user.role != UserRole.ADMIN:
            participant = _get_case_participant(self.db, case_id, user.id)
            if (
                not participant
                or participant.participant_role == ParticipantRole.VIEWER
            ):
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
            target_user = (
                self.db.query(User)
                .filter(User.id == req.owner_user_id, User.deleted_at.is_(None))
                .first()
            )
            if not target_user or target_user.account_status != AccountStatus.ACTIVE:
                raise ValidationError("Assigned user must be an active user")

            assigned_p = _get_case_participant(self.db, case_id, req.owner_user_id)
            if not assigned_p:
                raise ValidationError(
                    "Assigned user must be an active participant of this case"
                )

        priority_val = (
            req.priority
            if isinstance(req.priority, TaskPriority)
            else TaskPriority(req.priority)
        )
        task = CaseTask(
            id=generate_uuid7(),
            case_id=case_id,
            title=req.title,
            description=req.description,
            priority=priority_val,
            due_date=due_date,
            owner_user_id=req.owner_user_id,
            created_by_user_id=user.id,
            status=TaskStatus.PENDING,
            source_type=getattr(req, "source_type", TaskSourceType.MANUAL),
            source_reference=getattr(req, "source_reference", None),
            is_confirmed=getattr(req, "is_confirmed", True),
            linked_evidence_id=getattr(req, "linked_evidence_id", None),
            linked_hearing_id=getattr(req, "linked_hearing_id", None),
            linked_deadline_id=getattr(req, "linked_deadline_id", None),
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        self._log_audit(
            "TASK_CREATED",
            user.id,
            {
                "case_id": str(case_id),
                "task_id": str(task.id),
                "owner_user_id": str(task.owner_user_id) if task.owner_user_id else None,
                "priority": task.priority.value,
            },
        )
        self.record_case_activity(
            case_id,
            user.id,
            "TASK_CREATED",
            f"Task '{task.title}' was created",
            {"task_id": str(task.id)},
        )
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

    def get_tasks(
        self,
        user: User,
        case_id: uuid.UUID,
        status: TaskStatus | None = None,
        owner_user_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        authorize_case_access(self.db, user, case_id)
        limit = min(max(limit, 1), 100)

        query = self.db.query(CaseTask).filter(
            CaseTask.case_id == case_id, CaseTask.deleted_at.is_(None)
        )

        if status is not None:
            query = query.filter(CaseTask.status == status)

        if owner_user_id is not None:
            query = query.filter(CaseTask.owner_user_id == owner_user_id)

        query = query.order_by(CaseTask.created_at.desc(), CaseTask.id.desc())

        total = query.count()
        tasks = query.offset(skip).limit(limit).all()
        return {"items": tasks, "total": total, "skip": skip, "limit": limit}

    def get_task_by_id(
        self, user: User, case_id: uuid.UUID, task_id: uuid.UUID
    ) -> CaseTask:
        authorize_case_access(self.db, user, case_id)
        task = (
            self.db.query(CaseTask)
            .filter(
                CaseTask.id == task_id,
                CaseTask.case_id == case_id,
                CaseTask.deleted_at.is_(None),
            )
            .first()
        )
        if not task:
            raise ResourceNotFoundError("Task not found")
        return task

    def update_task(
        self, user: User, case_id: uuid.UUID, task_id: uuid.UUID, req: CaseTaskUpdate
    ) -> CaseTask:
        authorize_case_access(self.db, user, case_id)

        case_obj = self.db.query(Case).filter(Case.id == case_id, Case.deleted_at.is_(None)).first()
        if case_obj and case_obj.status in (CaseStatus.CLOSED, CaseStatus.CANCELLED):
            raise ValidationError("Tasks cannot be updated on closed or cancelled cases")

        query = self.db.query(CaseTask).filter(
            CaseTask.id == task_id,
            CaseTask.case_id == case_id,
            CaseTask.deleted_at.is_(None),
        )
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            query = query.with_for_update()

        task = query.first()
        if not task:
            raise ResourceNotFoundError("Task not found")

        if user.role != UserRole.ADMIN:
            participant = _get_case_participant(self.db, case_id, user.id)
            if (
                not participant
                or participant.participant_role == ParticipantRole.VIEWER
            ):
                raise AuthorizationError("Viewers cannot update tasks")

        updated = {}
        dump = req.model_dump(exclude_unset=True)

        # Freeze terminal states (COMPLETED and CANCELLED)
        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            if "status" in dump and dump["status"] == task.status and len(dump) == 1:
                return task
            raise ValidationError(
                f"Cannot modify a {task.status.value.lower()} task"
            )

        if "owner_user_id" in dump:
            new_owner = dump["owner_user_id"]
            if new_owner is not None:
                target_user = (
                    self.db.query(User)
                    .filter(User.id == new_owner, User.deleted_at.is_(None))
                    .first()
                )
                if not target_user or target_user.account_status != AccountStatus.ACTIVE:
                    raise ValidationError("Assigned user must be an active user")

                assigned_p = _get_case_participant(self.db, case_id, new_owner)
                if not assigned_p:
                    raise ValidationError(
                        "Assigned user must be an active participant of this case"
                    )

            prev_assignee = task.owner_user_id
            if new_owner != prev_assignee:
                task.owner_user_id = new_owner
                updated["owner_user_id"] = str(new_owner) if new_owner else None
                updated["previous_assignee"] = str(prev_assignee) if prev_assignee else None

        if "priority" in dump and dump["priority"] is not None:
            task.priority = (
                dump["priority"]
                if isinstance(dump["priority"], TaskPriority)
                else TaskPriority(dump["priority"])
            )
            updated["priority"] = str(task.priority.value)

        for field in ("title", "description"):
            if field in dump:
                setattr(task, field, dump[field])
                updated[field] = dump[field]

        for field in ("linked_evidence_id", "linked_hearing_id", "linked_deadline_id"):
            if field in dump:
                setattr(task, field, dump[field])
                updated[field] = str(dump[field]) if dump[field] else None

        if "due_date" in dump:
            new_due = dump["due_date"]
            if new_due is not None:
                if new_due.tzinfo is None:
                    new_due = new_due.replace(tzinfo=UTC)
                if task.created_at:
                    task_created = (
                        task.created_at.replace(tzinfo=UTC)
                        if task.created_at.tzinfo is None
                        else task.created_at
                    )
                    if new_due < task_created - timedelta(minutes=5):
                        raise ValidationError("Task due date cannot be before task creation time")
            task.due_date = new_due
            updated["due_date"] = new_due.isoformat() if new_due else None

        if "status" in dump and dump["status"] is not None:
            new_status = (
                dump["status"]
                if isinstance(dump["status"], TaskStatus)
                else TaskStatus(dump["status"])
            )
            if new_status != task.status:
                if new_status not in self.VALID_TASK_TRANSITIONS[task.status]:
                    raise ValidationError(
                        f"Invalid task status transition from {task.status.value} to {new_status.value}"
                    )
                prev_status = task.status
                task.status = new_status
                updated["status"] = new_status.value
                updated["previous_status"] = prev_status.value
                if new_status == TaskStatus.COMPLETED:
                    task.completed_at = datetime.now(UTC)
                else:
                    task.completed_at = None

        if updated:
            self.db.commit()
            self.db.refresh(task)
            self._log_audit(
                "TASK_UPDATED",
                user.id,
                {
                    "case_id": str(case_id),
                    "task_id": str(task.id),
                    "fields": list(updated.keys()),
                    "previous_status": updated.get("previous_status"),
                    "new_status": updated.get("status"),
                    "previous_assignee": updated.get("previous_assignee"),
                    "new_assignee": updated.get("owner_user_id"),
                },
            )
            self.record_case_activity(
                case_id,
                user.id,
                "TASK_UPDATED",
                f"Task '{task.title}' was updated",
                {"task_id": str(task.id), "fields": list(updated.keys())},
            )

            if "owner_user_id" in updated and task.owner_user_id and task.owner_user_id != user.id:
                self.notification_service.create_notification(
                    user_id=task.owner_user_id,
                    type=NotificationType.TASK_ASSIGNED,
                    title="Task Assigned",
                    message=f"You were assigned to task: '{task.title}'.",
                    case_id=case_id,
                    task_id=task.id,
                )

            if "status" in updated and updated["status"] == TaskStatus.COMPLETED.value:
                self.record_case_activity(
                    case_id,
                    user.id,
                    "TASK_COMPLETED",
                    f"Task '{task.title}' was completed",
                    {"task_id": str(task.id)},
                )
                if task.created_by_user_id and task.created_by_user_id != user.id:
                    self.notification_service.create_notification(
                        user_id=task.created_by_user_id,
                        type=NotificationType.TASK_COMPLETED,
                        title="Task Completed",
                        message=f"Task '{task.title}' was completed.",
                        case_id=case_id,
                        task_id=task.id,
                    )

            if "status" in updated and updated["status"] == TaskStatus.CANCELLED.value:
                self.record_case_activity(
                    case_id,
                    user.id,
                    "TASK_CANCELLED",
                    f"Task '{task.title}' was cancelled",
                    {"task_id": str(task.id)},
                )

        return task

    def delete_task(self, user: User, case_id: uuid.UUID, task_id: uuid.UUID):
        authorize_case_access(self.db, user, case_id)

        task = (
            self.db.query(CaseTask)
            .filter(
                CaseTask.id == task_id,
                CaseTask.case_id == case_id,
                CaseTask.deleted_at.is_(None),
            )
            .first()
        )

        if not task:
            raise ResourceNotFoundError("Task not found")

        if user.role != UserRole.ADMIN:
            participant = _get_case_participant(self.db, case_id, user.id)
            if (
                not participant
                or participant.participant_role == ParticipantRole.VIEWER
            ):
                raise AuthorizationError("Viewers cannot delete tasks")
            if (
                participant.participant_role != ParticipantRole.OWNER
                and task.created_by_user_id != user.id
            ):
                raise AuthorizationError(
                    "Only the task creator or case owner can delete this task"
                )

        task.deleted_at = datetime.now(UTC)
        self.db.commit()

        self._log_audit(
            "TASK_DELETED", user.id, {"case_id": str(case_id), "task_id": str(task.id)}
        )
        self.record_case_activity(
            case_id,
            user.id,
            "TASK_DELETED",
            f"Task '{task.title}' was deleted",
            {"task_id": str(task.id)},
        )

    # --------------------------------------------------------------------------
    # NOTES MANAGEMENT
    # --------------------------------------------------------------------------

    def _apply_note_visibility_filter(self, query, user: User, case_id: uuid.UUID):
        if user.role == UserRole.ADMIN:
            return query

        participant = _get_case_participant(self.db, case_id, user.id)
        if not participant:
            # User is not an active participant on the case
            return query.filter(sql_false())

        if participant.participant_role == ParticipantRole.OWNER:
            # Case Owner can see:
            # - SHARED notes
            # - CLIENT_PRIVATE notes
            # - Any note they authored
            # CANNOT see other lawyers' LAWYER_PRIVATE work-product notes
            return query.filter(
                or_(
                    CaseNote.visibility == CaseNoteVisibility.SHARED,
                    CaseNote.visibility == CaseNoteVisibility.CLIENT_PRIVATE,
                    CaseNote.author_user_id == user.id,
                )
            )
        elif participant.participant_role == ParticipantRole.LAWYER:
            # Assigned Lawyer can see:
            # - SHARED notes
            # - LAWYER_PRIVATE notes authored by THEMSELVES
            # CANNOT see CLIENT_PRIVATE notes or other lawyers' LAWYER_PRIVATE notes
            return query.filter(
                or_(
                    CaseNote.visibility == CaseNoteVisibility.SHARED,
                    and_(
                        CaseNote.visibility == CaseNoteVisibility.LAWYER_PRIVATE,
                        CaseNote.author_user_id == user.id,
                    ),
                )
            )
        elif participant.participant_role == ParticipantRole.VIEWER:
            # Viewer can see ONLY SHARED notes
            return query.filter(CaseNote.visibility == CaseNoteVisibility.SHARED)

        return query.filter(CaseNote.author_user_id == user.id)

    def create_note(
        self, user: User, case_id: uuid.UUID, req: CaseNoteCreate
    ) -> CaseNote:
        authorize_case_access(self.db, user, case_id)

        participant = None
        if user.role != UserRole.ADMIN:
            participant = _get_case_participant(self.db, case_id, user.id)
            if (
                not participant
                or participant.participant_role == ParticipantRole.VIEWER
            ):
                raise AuthorizationError("Viewers cannot create case notes")

        # Determine note visibility
        if req.visibility:
            try:
                visibility = CaseNoteVisibility(req.visibility)
            except ValueError as e:
                raise ValidationError(f"Invalid note visibility: {req.visibility}") from e

            if user.role != UserRole.ADMIN and participant:
                if (
                    participant.participant_role == ParticipantRole.OWNER
                    and visibility == CaseNoteVisibility.LAWYER_PRIVATE
                ):
                    raise ValidationError("Clients cannot create lawyer work-product private notes")
                elif (
                    participant.participant_role == ParticipantRole.LAWYER
                    and visibility == CaseNoteVisibility.CLIENT_PRIVATE
                ):
                    raise ValidationError("Lawyers cannot create client-private notes")
        elif req.is_private is not None:
            if req.is_private:
                if participant and participant.participant_role == ParticipantRole.LAWYER:
                    visibility = CaseNoteVisibility.LAWYER_PRIVATE
                else:
                    visibility = CaseNoteVisibility.CLIENT_PRIVATE
            else:
                visibility = CaseNoteVisibility.SHARED
        else:
            visibility = CaseNoteVisibility.SHARED

        is_private = (visibility != CaseNoteVisibility.SHARED)

        note = CaseNote(
            id=generate_uuid7(),
            case_id=case_id,
            author_user_id=user.id,
            title=req.title,
            content=req.content,
            visibility=visibility,
            is_private=is_private,
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)

        self._log_audit(
            "NOTE_CREATED",
            user.id,
            {
                "case_id": str(case_id),
                "note_id": str(note.id),
                "visibility": visibility.value,
                "is_private": is_private,
            },
        )
        return note

    def get_notes(
        self, user: User, case_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> dict:
        authorize_case_access(self.db, user, case_id)
        limit = min(max(limit, 1), 100)

        query = self.db.query(CaseNote).filter(
            CaseNote.case_id == case_id, CaseNote.deleted_at.is_(None)
        )
        query = self._apply_note_visibility_filter(query, user, case_id)

        query = query.order_by(CaseNote.created_at.desc(), CaseNote.id.desc())
        total = query.count()
        notes = query.offset(skip).limit(limit).all()
        return {"items": notes, "total": total, "skip": skip, "limit": limit}

    def get_note_by_id(
        self, user: User, case_id: uuid.UUID, note_id: uuid.UUID
    ) -> CaseNote:
        authorize_case_access(self.db, user, case_id)

        query = self.db.query(CaseNote).filter(
            CaseNote.id == note_id,
            CaseNote.case_id == case_id,
            CaseNote.deleted_at.is_(None),
        )
        query = self._apply_note_visibility_filter(query, user, case_id)
        note = query.first()

        if not note:
            raise ResourceNotFoundError("Note not found")

        return note

    def update_note(
        self, user: User, case_id: uuid.UUID, note_id: uuid.UUID, req: CaseNoteUpdate
    ) -> CaseNote:
        authorize_case_access(self.db, user, case_id)

        query = self.db.query(CaseNote).filter(
            CaseNote.id == note_id,
            CaseNote.case_id == case_id,
            CaseNote.deleted_at.is_(None),
        )
        query = self._apply_note_visibility_filter(query, user, case_id)
        note = query.first()

        if not note:
            raise ResourceNotFoundError("Note not found")

        participant = None
        if user.role != UserRole.ADMIN:
            participant = _get_case_participant(self.db, case_id, user.id)
            if (
                not participant
                or participant.participant_role == ParticipantRole.VIEWER
            ):
                raise AuthorizationError("Viewers cannot update case notes")

            # Editing permissions:
            # - LAWYER_PRIVATE: ONLY the authoring lawyer
            # - CLIENT_PRIVATE: Author or Case Owner
            # - SHARED: Author or Case Owner
            if note.visibility == CaseNoteVisibility.LAWYER_PRIVATE:
                if note.author_user_id != user.id:
                    raise AuthorizationError(
                        "Only the authoring lawyer can edit a private work-product note"
                    )
            elif (
                note.author_user_id != user.id
                and participant.participant_role != ParticipantRole.OWNER
            ):
                raise AuthorizationError(
                    "Only the author or case owner can edit this note"
                )

        dump = req.model_dump(exclude_unset=True)

        if "visibility" in dump and dump["visibility"] is not None:
            try:
                new_vis = CaseNoteVisibility(dump["visibility"])
            except ValueError as e:
                raise ValidationError(f"Invalid note visibility: {dump['visibility']}") from e

            if user.role != UserRole.ADMIN and participant:
                if (
                    participant.participant_role == ParticipantRole.OWNER
                    and new_vis == CaseNoteVisibility.LAWYER_PRIVATE
                ):
                    raise ValidationError("Clients cannot set visibility to lawyer-private")
                if (
                    participant.participant_role == ParticipantRole.LAWYER
                    and new_vis == CaseNoteVisibility.CLIENT_PRIVATE
                ):
                    raise ValidationError("Lawyers cannot set visibility to client-private")

            note.visibility = new_vis
            note.is_private = (new_vis != CaseNoteVisibility.SHARED)
        elif "is_private" in dump and dump["is_private"] is not None:
            if dump["is_private"]:
                if participant and participant.participant_role == ParticipantRole.LAWYER:
                    note.visibility = CaseNoteVisibility.LAWYER_PRIVATE
                else:
                    note.visibility = CaseNoteVisibility.CLIENT_PRIVATE
                note.is_private = True
            else:
                note.visibility = CaseNoteVisibility.SHARED
                note.is_private = False

        for field in ("title", "content"):
            if field in dump and dump[field] is not None:
                setattr(note, field, dump[field])

        self.db.commit()
        self.db.refresh(note)

        self._log_audit(
            "NOTE_UPDATED",
            user.id,
            {"case_id": str(case_id), "note_id": str(note.id)},
        )
        return note

    def delete_note(self, user: User, case_id: uuid.UUID, note_id: uuid.UUID):
        authorize_case_access(self.db, user, case_id)

        query = self.db.query(CaseNote).filter(
            CaseNote.id == note_id,
            CaseNote.case_id == case_id,
            CaseNote.deleted_at.is_(None),
        )
        query = self._apply_note_visibility_filter(query, user, case_id)
        note = query.first()

        if not note:
            raise ResourceNotFoundError("Note not found")

        if user.role != UserRole.ADMIN:
            participant = _get_case_participant(self.db, case_id, user.id)
            if (
                not participant
                or participant.participant_role == ParticipantRole.VIEWER
            ):
                raise AuthorizationError("Viewers cannot delete case notes")

            # Deletion permissions:
            # - LAWYER_PRIVATE: ONLY the authoring lawyer
            # - CLIENT_PRIVATE: Author or Case Owner
            # - SHARED: Author or Case Owner
            if note.visibility == CaseNoteVisibility.LAWYER_PRIVATE:
                if note.author_user_id != user.id:
                    raise AuthorizationError(
                        "Only the authoring lawyer can delete a private work-product note"
                    )
            elif (
                note.author_user_id != user.id
                and participant.participant_role != ParticipantRole.OWNER
            ):
                raise AuthorizationError(
                    "Only the author or case owner can delete this note"
                )

        note.deleted_at = datetime.now(UTC)
        self.db.commit()

        self._log_audit(
            "NOTE_DELETED",
            user.id,
            {"case_id": str(case_id), "note_id": str(note.id)},
        )
