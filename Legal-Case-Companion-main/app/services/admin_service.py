import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.exceptions import AuthorizationError, ResourceNotFoundError
from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.case import Case, CaseStatus, ParticipantRole
from app.models.consultation import Consultation, ConsultationStatus
from app.models.document import Document, DocumentSecurityStatus
from app.models.notification import NotificationType
from app.models.payment import Payment, PaymentStatus
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.schemas.admin import (
    AdminCaseResponse,
    AdminConsultationResponse,
    AdminDocumentSecurityResponse,
    AdminOverviewResponse,
    AdminPaymentResponse,
    AdminSecurityEventResponse,
    AdminUserResponse,
)
from app.services.notification_service import NotificationService


class AdminService:
    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db)

    def _verify_admin(self, user: User) -> None:
        if user.role != UserRole.ADMIN:
            raise AuthorizationError("Only administrators can perform this action")

    def _get_user_full_name(self, user: User) -> str:
        if user.client_profile and user.client_profile.full_name:
            return user.client_profile.full_name
        if user.lawyer_profile and user.lawyer_profile.full_name:
            return user.lawyer_profile.full_name
        return user.email.split("@")[0]

    def get_operational_overview(self, admin_user: User) -> AdminOverviewResponse:
        self._verify_admin(admin_user)

        total_users = self.db.query(func.count(User.id)).scalar() or 0
        active_users = (
            self.db.query(func.count(User.id))
            .filter(User.account_status == AccountStatus.ACTIVE)
            .scalar()
            or 0
        )
        suspended_users = (
            self.db.query(func.count(User.id))
            .filter(User.account_status == AccountStatus.SUSPENDED)
            .scalar()
            or 0
        )

        total_lawyers = (
            self.db.query(func.count(User.id))
            .filter(User.role == UserRole.LAWYER)
            .scalar()
            or 0
        )
        pending_verifications = (
            self.db.query(func.count(LawyerVerification.id))
            .filter(
                LawyerVerification.status.in_(
                    [VerificationStatus.PENDING, VerificationStatus.UNDER_REVIEW]
                )
            )
            .scalar()
            or 0
        )
        verified_lawyers = (
            self.db.query(func.count(LawyerVerification.id))
            .filter(LawyerVerification.status == VerificationStatus.APPROVED)
            .scalar()
            or 0
        )

        total_cases = (
            self.db.query(func.count(Case.id))
            .filter(Case.deleted_at.is_(None))
            .scalar()
            or 0
        )
        active_cases = (
            self.db.query(func.count(Case.id))
            .filter(Case.deleted_at.is_(None), Case.status != CaseStatus.CLOSED)
            .scalar()
            or 0
        )
        closed_cases = (
            self.db.query(func.count(Case.id))
            .filter(Case.deleted_at.is_(None), Case.status == CaseStatus.CLOSED)
            .scalar()
            or 0
        )

        total_consultations = (
            self.db.query(func.count(Consultation.id))
            .filter(Consultation.deleted_at.is_(None))
            .scalar()
            or 0
        )
        paid_consultations = (
            self.db.query(func.count(Consultation.id))
            .filter(
                Consultation.deleted_at.is_(None),
                Consultation.status == ConsultationStatus.PAID,
            )
            .scalar()
            or 0
        )
        scheduled_consultations = (
            self.db.query(func.count(Consultation.id))
            .filter(
                Consultation.deleted_at.is_(None),
                Consultation.status == ConsultationStatus.SCHEDULED,
            )
            .scalar()
            or 0
        )

        total_payments = self.db.query(func.count(Payment.id)).scalar() or 0
        succeeded_payments = (
            self.db.query(func.count(Payment.id))
            .filter(Payment.status == PaymentStatus.SUCCEEDED)
            .scalar()
            or 0
        )
        total_revenue_inr = (
            self.db.query(func.sum(Payment.amount))
            .filter(Payment.status == PaymentStatus.SUCCEEDED)
            .scalar()
            or 0.0
        )

        total_documents = (
            self.db.query(func.count(Document.id))
            .filter(Document.deleted_at.is_(None))
            .scalar()
            or 0
        )
        quarantined_documents = (
            self.db.query(func.count(Document.id))
            .filter(
                Document.deleted_at.is_(None),
                Document.security_status == DocumentSecurityStatus.QUARANTINED,
            )
            .scalar()
            or 0
        )
        rejected_documents = (
            self.db.query(func.count(Document.id))
            .filter(
                Document.deleted_at.is_(None),
                Document.security_status == DocumentSecurityStatus.REJECTED,
            )
            .scalar()
            or 0
        )

        security_event_count = (
            self.db.query(func.count(AuditEvent.id))
            .filter(
                or_(
                    AuditEvent.event_type.like("%SUSPEND%"),
                    AuditEvent.event_type.like("%REJECT%"),
                    AuditEvent.event_type.like("%SECURITY%"),
                    AuditEvent.event_type.like("%BREACH%"),
                    AuditEvent.event_type.like("%FAIL%"),
                )
            )
            .scalar()
            or 0
        )

        return AdminOverviewResponse(
            total_users=total_users,
            active_users=active_users,
            suspended_users=suspended_users,
            total_lawyers=total_lawyers,
            pending_verifications=pending_verifications,
            verified_lawyers=verified_lawyers,
            total_cases=total_cases,
            active_cases=active_cases,
            closed_cases=closed_cases,
            total_consultations=total_consultations,
            paid_consultations=paid_consultations,
            scheduled_consultations=scheduled_consultations,
            total_payments=total_payments,
            succeeded_payments=succeeded_payments,
            total_revenue_inr=float(total_revenue_inr),
            total_documents=total_documents,
            quarantined_documents=quarantined_documents,
            rejected_documents=rejected_documents,
            security_event_count=security_event_count,
        )

    def list_users(
        self,
        admin_user: User,
        role: UserRole | None = None,
        account_status: AccountStatus | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        self._verify_admin(admin_user)
        limit = min(max(limit, 1), 100)

        query = (
            self.db.query(User)
            .outerjoin(ClientProfile, User.id == ClientProfile.user_id)
            .outerjoin(LawyerProfile, User.id == LawyerProfile.user_id)
        )
        if role:
            query = query.filter(User.role == role)
        if account_status:
            query = query.filter(User.account_status == account_status)
        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    User.email.ilike(search_pattern),
                    ClientProfile.full_name.ilike(search_pattern),
                    LawyerProfile.full_name.ilike(search_pattern),
                )
            )

        total = query.count()
        items = (
            query.order_by(User.created_at.desc(), User.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return {
            "items": [
                AdminUserResponse(
                    id=u.id,
                    email=u.email,
                    full_name=self._get_user_full_name(u),
                    role=u.role,
                    account_status=u.account_status,
                    created_at=u.created_at,
                    updated_at=u.updated_at,
                )
                for u in items
            ],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def get_user(self, admin_user: User, user_id: uuid.UUID) -> AdminUserResponse:
        self._verify_admin(admin_user)
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ResourceNotFoundError("User not found")
        return AdminUserResponse(
            id=user.id,
            email=user.email,
            full_name=self._get_user_full_name(user),
            role=user.role,
            account_status=user.account_status,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def get_pending_verifications(
        self,
        admin_user: User,
        status: VerificationStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        self._verify_admin(admin_user)
        limit = min(max(limit, 1), 100)

        query = self.db.query(LawyerVerification)
        if status:
            query = query.filter(LawyerVerification.status == status)
        else:
            query = query.filter(
                LawyerVerification.status.in_(
                    [VerificationStatus.PENDING, VerificationStatus.UNDER_REVIEW]
                )
            )

        total = query.count()
        items = (
            query.order_by(LawyerVerification.created_at.asc(), LawyerVerification.id.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def review_verification(
        self,
        admin_user: User,
        verification_id: uuid.UUID,
        approve: bool,
        reason: str | None = None,
    ) -> LawyerVerification:
        self._verify_admin(admin_user)

        verif = (
            self.db.query(LawyerVerification)
            .filter(LawyerVerification.id == verification_id)
            .first()
        )
        if not verif:
            raise ResourceNotFoundError("Verification request not found")

        if verif.status in [VerificationStatus.APPROVED, VerificationStatus.REJECTED]:
            raise AuthorizationError(
                "This verification request has already been processed"
            )

        verif.status = (
            VerificationStatus.APPROVED if approve else VerificationStatus.REJECTED
        )
        verif.reviewed_by = admin_user.id
        verif.reviewed_at = datetime.now(UTC)

        # Notify lawyer
        lawyer_profile = (
            self.db.query(LawyerProfile)
            .filter(LawyerProfile.id == verif.lawyer_profile_id)
            .first()
        )
        if lawyer_profile:
            msg = (
                "Your advocate verification application has been APPROVED by platform administration."
                if approve
                else f"Your advocate verification application was REJECTED. Reason: {reason or 'Credentials could not be confirmed.'}"
            )
            self.notification_service.create_notification(
                user_id=lawyer_profile.user_id,
                type=NotificationType.CONSULTATION_REQUESTED,  # system notification
                title=f"Bar Council Verification {'Approved' if approve else 'Rejected'}",
                message=msg,
                metadata={"verification_id": str(verif.id)},
                event_id=f"verif_review_{verif.id}",
            )

        action_type = "APPROVED" if approve else "REJECTED"
        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=admin_user.id,
            event_type=f"LAWYER_VERIFICATION_{action_type}",
            entity_type="lawyer_verification",
            entity_id=verif.id,
            action="admin_mutation",
            timestamp=datetime.now(UTC),
            metadata_={
                "verification_id": str(verif.id),
                "lawyer_profile_id": str(verif.lawyer_profile_id),
                "reason": reason or "",
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(verif)

        return verif

    def suspend_user(
        self, admin_user: User, user_id: uuid.UUID, reason: str | None = None
    ) -> User:
        self._verify_admin(admin_user)

        if admin_user.id == user_id:
            raise AuthorizationError("Administrators cannot suspend their own account")

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ResourceNotFoundError("User not found")

        prev_status = user.account_status
        user.account_status = AccountStatus.SUSPENDED

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=admin_user.id,
            event_type="USER_ACCOUNT_SUSPENDED",
            entity_type="user",
            entity_id=user.id,
            action="suspend_account",
            timestamp=datetime.now(UTC),
            metadata_={
                "previous_status": prev_status.value,
                "target_user_role": user.role.value,
                "reason": reason or "Administrative suspension",
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(user)
        return user

    def reactivate_user(self, admin_user: User, user_id: uuid.UUID) -> User:
        self._verify_admin(admin_user)

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ResourceNotFoundError("User not found")

        prev_status = user.account_status
        user.account_status = AccountStatus.ACTIVE

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=admin_user.id,
            event_type="USER_ACCOUNT_REACTIVATED",
            entity_type="user",
            entity_id=user.id,
            action="reactivate_account",
            timestamp=datetime.now(UTC),
            metadata_={
                "previous_status": prev_status.value,
                "target_user_role": user.role.value,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(user)
        return user

    def list_cases(
        self,
        admin_user: User,
        status: CaseStatus | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        self._verify_admin(admin_user)
        limit = min(max(limit, 1), 100)

        query = self.db.query(Case).filter(Case.deleted_at.is_(None))
        if status:
            query = query.filter(Case.status == status)
        if search:
            query = query.filter(Case.title.ilike(f"%{search.strip()}%"))

        total = query.count()
        cases = (
            query.order_by(Case.created_at.desc(), Case.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        items: list[AdminCaseResponse] = []
        for c in cases:
            # Find owner email
            owner_participant = next(
                (p for p in c.participants if p.participant_role == ParticipantRole.OWNER), None
            )
            owner_user = (
                self.db.query(User).filter(User.id == owner_participant.user_id).first()
                if owner_participant
                else None
            )
            items.append(
                AdminCaseResponse(
                    id=c.id,
                    title=c.title,
                    description=c.description,
                    status=c.status,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                    participant_count=len(c.participants),
                    document_count=len([d for d in c.documents if d.deleted_at is None]),
                    owner_email=owner_user.email if owner_user else None,
                )
            )

        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def list_consultations(
        self,
        admin_user: User,
        status: ConsultationStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        self._verify_admin(admin_user)
        limit = min(max(limit, 1), 100)

        query = self.db.query(Consultation).filter(Consultation.deleted_at.is_(None))
        if status:
            query = query.filter(Consultation.status == status)

        total = query.count()
        consultations = (
            query.order_by(Consultation.created_at.desc(), Consultation.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        items = [
            AdminConsultationResponse(
                id=c.id,
                client_id=c.client_id,
                lawyer_id=c.lawyer_id,
                case_id=c.case_id,
                status=c.status,
                fee_amount=float(c.fee_amount),
                currency=c.currency,
                scheduled_at=c.scheduled_at,
                duration_minutes=c.duration_minutes,
                rejection_reason=c.rejection_reason,
                created_at=c.created_at,
            )
            for c in consultations
        ]
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def list_payments(
        self,
        admin_user: User,
        status: PaymentStatus | None = None,
        provider: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        self._verify_admin(admin_user)
        limit = min(max(limit, 1), 100)

        query = self.db.query(Payment)
        if status:
            query = query.filter(Payment.status == status)
        if provider:
            query = query.filter(Payment.provider == provider)

        total = query.count()
        payments = (
            query.order_by(Payment.created_at.desc(), Payment.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        items = [AdminPaymentResponse.model_validate(p) for p in payments]
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def list_document_security(
        self,
        admin_user: User,
        security_status: DocumentSecurityStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        self._verify_admin(admin_user)
        limit = min(max(limit, 1), 100)

        query = self.db.query(Document).filter(Document.deleted_at.is_(None))
        if security_status:
            query = query.filter(Document.security_status == security_status)

        total = query.count()
        documents = (
            query.order_by(Document.created_at.desc(), Document.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        items = [
            AdminDocumentSecurityResponse(
                id=d.id,
                case_id=d.case_id,
                filename=d.filename,
                mime_type=d.mime_type,
                file_size=d.file_size,
                security_status=d.security_status,
                created_at=d.created_at,
            )
            for d in documents
        ]
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def list_audit_logs(
        self,
        admin_user: User,
        event_type: str | None = None,
        actor_user_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        self._verify_admin(admin_user)
        limit = min(max(limit, 1), 100)
        query = self.db.query(AuditEvent)

        if event_type:
            query = query.filter(AuditEvent.event_type == event_type)
        if actor_user_id:
            query = query.filter(AuditEvent.actor_user_id == actor_user_id)
        if entity_type:
            query = query.filter(AuditEvent.entity_type == entity_type)

        total = query.count()
        items = (
            query.order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def list_security_events(
        self,
        admin_user: User,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        self._verify_admin(admin_user)
        limit = min(max(limit, 1), 100)

        query = self.db.query(AuditEvent).filter(
            or_(
                AuditEvent.event_type.like("%SUSPEND%"),
                AuditEvent.event_type.like("%REJECT%"),
                AuditEvent.event_type.like("%SECURITY%"),
                AuditEvent.event_type.like("%BREACH%"),
                AuditEvent.event_type.like("%FAIL%"),
                AuditEvent.event_type.like("%REPLAY%"),
                AuditEvent.event_type.like("%MALWARE%"),
                AuditEvent.event_type.like("%DENIAL%"),
            )
        )

        total = query.count()
        events = (
            query.order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        items = [
            AdminSecurityEventResponse(
                id=e.id,
                actor_user_id=e.actor_user_id,
                event_type=e.event_type,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                action=e.action,
                timestamp=e.timestamp,
                metadata=e.metadata_ or {},
            )
            for e in events
        ]
        return {"items": items, "total": total, "skip": skip, "limit": limit}
