import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.authorization import authorize_case_access
from app.core.exceptions import (
    AuthorizationError,
    ResourceNotFoundError,
    ValidationError,
)
from app.core.identifiers import generate_uuid7
from app.models.case import CaseParticipant, ParticipantRole, ParticipantStatus
from app.models.case_collaboration import (
    CaseMessage,
    CaseMessageType,
    MatterRequest,
    MatterRequestStatus,
)
from app.models.direct_message import DirectMessage
from app.models.document import Document
from app.models.notification import NotificationType
from app.models.task import CaseTask, TaskPriority, TaskSourceType, TaskStatus
from app.models.user import User, UserRole
from app.models.workflow import CaseHearing, HearingStatus
from app.schemas.collaboration import (
    CaseMessageCreate,
    CaseMessageResponse,
    MatterBriefResponse,
    MatterParticipantDetailResponse,
    MatterRequestCreate,
    MatterRequestResponse,
    MatterRequestReview,
    MatterRequestSubmit,
)
from app.domain.notifications.notification_service import NotificationService


class CollaborationService:
    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db)

    def _resolve_user_display_name(self, user_id: uuid.UUID | None) -> str:
        if not user_id:
            return "Unassigned"
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return "Unknown User"
        if user.client_profile and user.client_profile.full_name:
            return user.client_profile.full_name
        if user.lawyer_profile and user.lawyer_profile.full_name:
            return user.lawyer_profile.full_name
        return user.email.split("@")[0].capitalize()

    # --------------------------------------------------------------------------
    # CASE MESSAGES & FORMAL NOTICES
    # --------------------------------------------------------------------------

    def send_case_message(
        self, user: User, case_id: uuid.UUID, req: CaseMessageCreate
    ) -> CaseMessageResponse:
        authorize_case_access(self.db, user, case_id)

        participant = (
            self.db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.user_id == user.id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .first()
        )
        if user.role != UserRole.ADMIN and not participant:
            raise AuthorizationError("Only active participants may send messages to this matter.")

        # Counsel-only check: only lawyers/admins can mark messages as counsel-only
        if req.is_counsel_only and user.role != UserRole.ADMIN and (
            not participant or participant.participant_role != ParticipantRole.LAWYER
        ):
            raise AuthorizationError("Only legal counsel may send counsel-only matter messages.")

        # Validate linked document if provided
        linked_doc_title = None
        if req.linked_document_id:
            doc = (
                self.db.query(Document)
                .filter(
                    Document.id == req.linked_document_id,
                    Document.case_id == case_id,
                    Document.deleted_at.is_(None),
                )
                .first()
            )
            if not doc:
                raise ValidationError("Linked document does not belong to this matter.")
            linked_doc_title = doc.filename

        # Validate linked task if provided
        linked_task_title = None
        if req.linked_task_id:
            task = (
                self.db.query(CaseTask)
                .filter(
                    CaseTask.id == req.linked_task_id,
                    CaseTask.case_id == case_id,
                    CaseTask.deleted_at.is_(None),
                )
                .first()
            )
            if not task:
                raise ValidationError("Linked task does not belong to this matter.")
            linked_task_title = task.title

        msg = CaseMessage(
            id=generate_uuid7(),
            case_id=case_id,
            sender_id=user.id,
            content=req.content.strip(),
            message_type=req.message_type,
            linked_document_id=req.linked_document_id,
            linked_task_id=req.linked_task_id,
            is_counsel_only=req.is_counsel_only,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)

        # Notify other relevant participants
        all_participants = (
            self.db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .all()
        )

        sender_name = self._resolve_user_display_name(user.id)
        role_label = participant.participant_role.value if participant else user.role.value

        for p in all_participants:
            if p.user_id == user.id:
                continue
            if req.is_counsel_only and p.participant_role != ParticipantRole.LAWYER:
                continue

            self.notification_service.create_notification(
                user_id=p.user_id,
                type=NotificationType.MATTER_MESSAGE_RECEIVED,
                title=f"Matter Update: {sender_name}",
                message=f"New matter communication ({req.message_type.value}): {req.content[:120]}...",
                case_id=case_id,
            )

            # Mirror to DirectMessage so messages sent in the case workspace appear in /messages
            dm = DirectMessage(
                id=generate_uuid7(),
                sender_id=user.id,
                recipient_id=p.user_id,
                content=req.content.strip(),
                is_read=False,
            )
            self.db.add(dm)

        self.db.commit()

        return CaseMessageResponse(
            id=msg.id,
            case_id=msg.case_id,
            sender_id=msg.sender_id,
            sender_name=sender_name,
            sender_role=role_label,
            content=msg.content,
            message_type=msg.message_type,
            linked_document_id=msg.linked_document_id,
            linked_document_title=linked_doc_title,
            linked_task_id=msg.linked_task_id,
            linked_task_title=linked_task_title,
            is_counsel_only=msg.is_counsel_only,
            created_at=msg.created_at,
        )

    def get_case_messages(
        self, user: User, case_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> list[CaseMessageResponse]:
        authorize_case_access(self.db, user, case_id)

        participant = (
            self.db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.user_id == user.id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .first()
        )

        query = self.db.query(CaseMessage).filter(
            CaseMessage.case_id == case_id,
            CaseMessage.deleted_at.is_(None),
        )

        # Clients and viewers cannot see counsel-only messages
        if user.role != UserRole.ADMIN and (not participant or participant.participant_role != ParticipantRole.LAWYER):
            query = query.filter(CaseMessage.is_counsel_only.is_(False))

        messages = (
            query.order_by(CaseMessage.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        results: list[CaseMessageResponse] = []
        for m in messages:
            s_name = self._resolve_user_display_name(m.sender_id)
            sender_user = self.db.query(User).filter(User.id == m.sender_id).first()
            sender_role_str = sender_user.role.value if sender_user else "PARTICIPANT"
            
            doc_title = m.linked_document.filename if m.linked_document else None
            task_title = m.linked_task.title if m.linked_task else None

            results.append(
                CaseMessageResponse(
                    id=m.id,
                    case_id=m.case_id,
                    sender_id=m.sender_id,
                    sender_name=s_name,
                    sender_role=sender_role_str,
                    content=m.content,
                    message_type=m.message_type,
                    linked_document_id=m.linked_document_id,
                    linked_document_title=doc_title,
                    linked_task_id=m.linked_task_id,
                    linked_task_title=task_title,
                    is_counsel_only=m.is_counsel_only,
                    created_at=m.created_at,
                )
            )

        return results

    # --------------------------------------------------------------------------
    # STRUCTURED MATTER REQUESTS
    # --------------------------------------------------------------------------

    def create_matter_request(
        self, user: User, case_id: uuid.UUID, req: MatterRequestCreate
    ) -> MatterRequestResponse:
        authorize_case_access(self.db, user, case_id)

        participant = (
            self.db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.user_id == user.id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .first()
        )
        if user.role != UserRole.ADMIN and (not participant or participant.participant_role == ParticipantRole.VIEWER):
            raise AuthorizationError("Viewers cannot create matter requests.")

        assigned_id = req.assigned_user_id
        if not assigned_id:
            # By default assign to case owner/client if created by lawyer, or lead lawyer if created by client
            if participant and participant.participant_role == ParticipantRole.LAWYER:
                owner = (
                    self.db.query(CaseParticipant)
                    .filter(
                        CaseParticipant.case_id == case_id,
                        CaseParticipant.participant_role == ParticipantRole.OWNER,
                        CaseParticipant.status == ParticipantStatus.ACTIVE,
                    )
                    .first()
                )
                if owner:
                    assigned_id = owner.user_id
            else:
                lawyer_p = (
                    self.db.query(CaseParticipant)
                    .filter(
                        CaseParticipant.case_id == case_id,
                        CaseParticipant.participant_role == ParticipantRole.LAWYER,
                        CaseParticipant.status == ParticipantStatus.ACTIVE,
                    )
                    .first()
                )
                if lawyer_p:
                    assigned_id = lawyer_p.user_id

        matter_req = MatterRequest(
            id=generate_uuid7(),
            case_id=case_id,
            requesting_user_id=user.id,
            assigned_user_id=assigned_id,
            title=req.title.strip(),
            description=req.description.strip(),
            request_type=req.request_type,
            status=MatterRequestStatus.PENDING,
            due_date=req.due_date,
        )
        self.db.add(matter_req)

        # Synchronize corresponding operational task in CaseTask
        task = CaseTask(
            id=generate_uuid7(),
            case_id=case_id,
            title=f"Request: {req.title.strip()}",
            description=req.description.strip(),
            priority=TaskPriority.HIGH if req.due_date else TaskPriority.MEDIUM,
            due_date=req.due_date,
            owner_user_id=assigned_id,
            created_by_user_id=user.id,
            status=TaskStatus.PENDING,
            source_type=TaskSourceType.MANUAL,
            source_reference=f"matter_request:{matter_req.id}",
            is_confirmed=True,
        )
        self.db.add(task)

        # Also post an automatic announcement in CaseMessage
        announcement = CaseMessage(
            id=generate_uuid7(),
            case_id=case_id,
            sender_id=user.id,
            content=f"**New Matter Request**: {req.title.strip()}\n\n{req.description.strip()}",
            message_type=CaseMessageType.ACTION_REQUEST,
            linked_task_id=task.id,
            is_counsel_only=False,
        )
        self.db.add(announcement)

        self.db.commit()
        self.db.refresh(matter_req)

        # Notify assignee
        if assigned_id and assigned_id != user.id:
            self.notification_service.create_notification(
                user_id=assigned_id,
                type=NotificationType.MATTER_REQUEST_CREATED,
                title="Action Required: Matter Request",
                message=f"{self._resolve_user_display_name(user.id)} requested: '{req.title}'",
                case_id=case_id,
            )

        return self._build_request_response(matter_req)

    def submit_matter_request(
        self, user: User, case_id: uuid.UUID, request_id: uuid.UUID, req: MatterRequestSubmit
    ) -> MatterRequestResponse:
        authorize_case_access(self.db, user, case_id)

        matter_req = (
            self.db.query(MatterRequest)
            .filter(
                MatterRequest.id == request_id,
                MatterRequest.case_id == case_id,
                MatterRequest.deleted_at.is_(None),
            )
            .first()
        )
        if not matter_req:
            raise ResourceNotFoundError("Matter request not found.")

        # Ensure document belongs to this case if provided
        if req.submitted_document_id:
            doc = (
                self.db.query(Document)
                .filter(
                    Document.id == req.submitted_document_id,
                    Document.case_id == case_id,
                    Document.deleted_at.is_(None),
                )
                .first()
            )
            if not doc:
                raise ValidationError("Submitted document does not belong to this matter.")
            matter_req.submitted_document_id = req.submitted_document_id

        matter_req.response_notes = req.response_notes.strip() if req.response_notes else None
        matter_req.status = MatterRequestStatus.SUBMITTED
        matter_req.submitted_at = datetime.now(UTC)

        # Auto-post a submission message into the case stream
        doc_note = f" Attached document: {doc.filename}" if req.submitted_document_id and doc else ""
        sub_msg = CaseMessage(
            id=generate_uuid7(),
            case_id=case_id,
            sender_id=user.id,
            content=f"**Submitted Response for**: {matter_req.title}\n{req.response_notes or 'Submitted requested items.'}{doc_note}",
            message_type=CaseMessageType.DOCUMENT_SUBMISSION if req.submitted_document_id else CaseMessageType.STATUS_UPDATE,
            linked_document_id=req.submitted_document_id,
            is_counsel_only=False,
        )
        self.db.add(sub_msg)

        self.db.commit()
        self.db.refresh(matter_req)

        # Notify the requesting user
        if matter_req.requesting_user_id != user.id:
            self.notification_service.create_notification(
                user_id=matter_req.requesting_user_id,
                type=NotificationType.MATTER_REQUEST_SUBMITTED,
                title="Response Submitted: Matter Request",
                message=f"{self._resolve_user_display_name(user.id)} submitted items for '{matter_req.title}'",
                case_id=case_id,
            )

        return self._build_request_response(matter_req)

    def review_matter_request(
        self, user: User, case_id: uuid.UUID, request_id: uuid.UUID, req: MatterRequestReview
    ) -> MatterRequestResponse:
        authorize_case_access(self.db, user, case_id)

        participant = (
            self.db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.user_id == user.id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .first()
        )
        if user.role != UserRole.ADMIN and (not participant or participant.participant_role == ParticipantRole.VIEWER):
            raise AuthorizationError("Only counsel or case owner can mark requests reviewed.")

        matter_req = (
            self.db.query(MatterRequest)
            .filter(
                MatterRequest.id == request_id,
                MatterRequest.case_id == case_id,
                MatterRequest.deleted_at.is_(None),
            )
            .first()
        )
        if not matter_req:
            raise ResourceNotFoundError("Matter request not found.")

        matter_req.status = req.mark_status
        matter_req.reviewed_at = datetime.now(UTC)
        matter_req.reviewed_by_user_id = user.id

        # Update linked task if exists
        task = (
            self.db.query(CaseTask)
            .filter(
                CaseTask.case_id == case_id,
                CaseTask.source_reference == f"matter_request:{matter_req.id}",
                CaseTask.deleted_at.is_(None),
            )
            .first()
        )
        if task and req.mark_status == MatterRequestStatus.REVIEWED:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(UTC)

        self.db.commit()
        self.db.refresh(matter_req)

        # Notify assignee that review is complete
        if matter_req.assigned_user_id and matter_req.assigned_user_id != user.id:
            self.notification_service.create_notification(
                user_id=matter_req.assigned_user_id,
                type=NotificationType.MATTER_REQUEST_REVIEWED,
                title="Matter Request Completed",
                message=f"Your submission for '{matter_req.title}' has been reviewed.",
                case_id=case_id,
            )

        return self._build_request_response(matter_req)

    def get_matter_requests(
        self, user: User, case_id: uuid.UUID, status: MatterRequestStatus | None = None
    ) -> list[MatterRequestResponse]:
        authorize_case_access(self.db, user, case_id)

        query = self.db.query(MatterRequest).filter(
            MatterRequest.case_id == case_id,
            MatterRequest.deleted_at.is_(None),
        )
        if status:
            query = query.filter(MatterRequest.status == status)

        requests = query.order_by(MatterRequest.created_at.desc()).all()
        return [self._build_request_response(r) for r in requests]

    def _build_request_response(self, r: MatterRequest) -> MatterRequestResponse:
        doc_title = r.submitted_document.filename if r.submitted_document else None
        doc_status = (
            r.submitted_document.security_status.value
            if r.submitted_document and hasattr(r.submitted_document.security_status, "value")
            else None
        )

        return MatterRequestResponse(
            id=r.id,
            case_id=r.case_id,
            requesting_user_id=r.requesting_user_id,
            requesting_user_name=self._resolve_user_display_name(r.requesting_user_id),
            assigned_user_id=r.assigned_user_id,
            assigned_user_name=self._resolve_user_display_name(r.assigned_user_id) if r.assigned_user_id else None,
            title=r.title,
            description=r.description,
            request_type=r.request_type,
            status=r.status,
            due_date=r.due_date,
            submitted_document_id=r.submitted_document_id,
            submitted_document_title=doc_title,
            submitted_document_status=doc_status,
            response_notes=r.response_notes,
            submitted_at=r.submitted_at,
            reviewed_at=r.reviewed_at,
            reviewed_by_user_id=r.reviewed_by_user_id,
            reviewed_by_user_name=self._resolve_user_display_name(r.reviewed_by_user_id) if r.reviewed_by_user_id else None,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )

    # --------------------------------------------------------------------------
    # PARTICIPANTS DIRECTORY & MATTER BRIEF
    # --------------------------------------------------------------------------

    def get_matter_participants_detailed(
        self, user: User, case_id: uuid.UUID
    ) -> list[MatterParticipantDetailResponse]:
        authorize_case_access(self.db, user, case_id)

        participants = (
            self.db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .order_by(CaseParticipant.joined_at.asc())
            .all()
        )

        details: list[MatterParticipantDetailResponse] = []
        for p in participants:
            u = p.user
            full_name = self._resolve_user_display_name(p.user_id)
            phone = u.phone if u else None

            bar_num = None
            spec = None
            firm = None
            org = None

            if u and u.lawyer_profile:
                lp = u.lawyer_profile
                if lp.verifications:
                    bar_num = lp.verifications[0].enrollment_number
                spec = ", ".join(lp.practice_areas) if lp.practice_areas else None
                firm = lp.location
            elif u and u.client_profile:
                org = u.client_profile.location

            details.append(
                MatterParticipantDetailResponse(
                    id=p.id,
                    user_id=p.user_id,
                    case_id=p.case_id,
                    participant_role=p.participant_role.value,
                    status=p.status.value,
                    full_name=full_name,
                    email=u.email if u else "redacted@lcc.internal",
                    phone=phone,
                    lawyer_bar_number=bar_num,
                    lawyer_specialization=spec,
                    lawyer_firm_name=firm,
                    client_organization=org,
                    joined_at=p.joined_at,
                )
            )

        return details

    def get_matter_brief(self, user: User, case_id: uuid.UUID) -> MatterBriefResponse:
        case_obj = authorize_case_access(self.db, user, case_id)

        participants = (
            self.db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .all()
        )

        lead_counsel = next(
            (p for p in participants if p.participant_role == ParticipantRole.LAWYER),
            None,
        )
        lead_counsel_name = self._resolve_user_display_name(lead_counsel.user_id) if lead_counsel else None

        open_requests_count = (
            self.db.query(MatterRequest)
            .filter(
                MatterRequest.case_id == case_id,
                MatterRequest.status.in_([MatterRequestStatus.PENDING, MatterRequestStatus.SUBMITTED]),
                MatterRequest.deleted_at.is_(None),
            )
            .count()
        )

        pending_tasks_count = (
            self.db.query(CaseTask)
            .filter(
                CaseTask.case_id == case_id,
                CaseTask.status != TaskStatus.COMPLETED,
                CaseTask.deleted_at.is_(None),
            )
            .count()
        )

        next_hearing = (
            self.db.query(CaseHearing)
            .filter(
                CaseHearing.case_id == case_id,
                CaseHearing.status == HearingStatus.SCHEDULED,
                CaseHearing.hearing_at >= datetime.now(UTC),
                CaseHearing.deleted_at.is_(None),
            )
            .order_by(CaseHearing.hearing_at.asc())
            .first()
        )

        recent_docs_count = (
            self.db.query(Document)
            .filter(
                Document.case_id == case_id,
                Document.deleted_at.is_(None),
            )
            .count()
        )

        return MatterBriefResponse(
            case_id=case_obj.id,
            title=case_obj.title,
            status=case_obj.status.value,
            created_at=case_obj.created_at,
            lead_counsel_name=lead_counsel_name,
            participants_count=len(participants),
            open_requests_count=open_requests_count,
            next_hearing_date=next_hearing.hearing_at if next_hearing else None,
            next_hearing_court=next_hearing.court_name if next_hearing else None,
            recent_documents_count=recent_docs_count,
            pending_tasks_count=pending_tasks_count,
        )
