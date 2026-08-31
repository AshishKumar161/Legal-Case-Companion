import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import AuthorizationError, ResourceNotFoundError
from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.user import (
    AccountStatus,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)


class AdminService:
    def __init__(self, db: Session):
        self.db = db

    def get_pending_verifications(
        self, admin_user: User, skip: int = 0, limit: int = 20
    ) -> dict:
        if admin_user.role != UserRole.ADMIN:
            raise AuthorizationError(
                "Only administrators can view the verification queue"
            )

        limit = min(max(limit, 1), 100)
        query = (
            self.db.query(LawyerVerification)
            .filter(
                LawyerVerification.status.in_(
                    [VerificationStatus.PENDING, VerificationStatus.UNDER_REVIEW]
                )
            )
            .order_by(LawyerVerification.created_at.asc(), LawyerVerification.id.asc())
        )

        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def review_verification(
        self, admin_user: User, verification_id: uuid.UUID, approve: bool
    ) -> LawyerVerification:
        if admin_user.role != UserRole.ADMIN:
            raise AuthorizationError("Only administrators can review verifications")

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
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(verif)

        return verif

    def suspend_user(self, admin_user: User, user_id: uuid.UUID) -> User:
        if admin_user.role != UserRole.ADMIN:
            raise AuthorizationError("Only administrators can suspend users")

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
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(user)
        return user

    def reactivate_user(self, admin_user: User, user_id: uuid.UUID) -> User:
        if admin_user.role != UserRole.ADMIN:
            raise AuthorizationError("Only administrators can reactivate users")

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

    def list_audit_logs(
        self,
        admin_user: User,
        event_type: str | None = None,
        actor_user_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        if admin_user.role != UserRole.ADMIN:
            raise AuthorizationError("Only administrators can view audit logs")

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
