import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import AuthorizationError, ResourceNotFoundError, ValidationError
from app.models.consultation import Consultation, ConsultationStatus
from app.models.user import AccountStatus, User, UserRole

logger = logging.getLogger(__name__)

# Valid state transitions
VALID_TRANSITIONS: dict[AccountStatus, set[AccountStatus]] = {
    AccountStatus.REGISTERED: {AccountStatus.VERIFIED, AccountStatus.RESTRICTED, AccountStatus.SUSPENDED, AccountStatus.DEACTIVATED},
    AccountStatus.VERIFIED: {AccountStatus.ACTIVE, AccountStatus.RESTRICTED, AccountStatus.SUSPENDED, AccountStatus.DEACTIVATED},
    AccountStatus.ACTIVE: {AccountStatus.RESTRICTED, AccountStatus.SUSPENDED, AccountStatus.DEACTIVATED},
    AccountStatus.RESTRICTED: {AccountStatus.ACTIVE, AccountStatus.SUSPENDED, AccountStatus.DEACTIVATED},
    AccountStatus.SUSPENDED: {AccountStatus.ACTIVE, AccountStatus.DEACTIVATED},
    AccountStatus.DEACTIVATED: set(),  # Terminal state
}


class LifecycleService:
    """
    Phase XX Customer Lifecycle Maturity Service.
    Enforces state transitions: REGISTERED -> VERIFIED -> ACTIVE -> RESTRICTED -> SUSPENDED -> DEACTIVATED.
    Auditability is strictly preserved; historical records are never deleted on deactivation.
    """

    def __init__(self, db: Session):
        self.db = db

    def transition_user_status(
        self,
        user_id: uuid.UUID,
        target_status: AccountStatus,
        reason: str,
        operator: User | None = None,
    ) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ResourceNotFoundError(f"User {user_id} not found")

        current_status = user.account_status or AccountStatus.REGISTERED

        # Self-deactivation allowed for the user themselves, other status changes require ADMIN or SYSTEM
        if target_status != AccountStatus.DEACTIVATED:
            if operator and operator.role != UserRole.ADMIN:
                raise AuthorizationError("Only administrators can modify user lifecycle status.")

        if target_status == current_status:
            return user

        allowed_targets = VALID_TRANSITIONS.get(current_status, set())
        if target_status not in allowed_targets:
            raise ValidationError(
                f"Invalid lifecycle transition from {current_status.value} to {target_status.value}. "
                f"Allowed transitions: {[s.value for s in allowed_targets]}"
            )

        previous_status = current_status
        user.account_status = target_status

        # Enforcement side-effects on restriction, suspension, or deactivation
        if target_status in (AccountStatus.SUSPENDED, AccountStatus.DEACTIVATED, AccountStatus.RESTRICTED):
            # Invalidate active sessions by revoking refresh tokens
            from app.models.auth import RefreshTokenSession
            now = datetime.now(UTC)
            self.db.query(RefreshTokenSession).filter(
                RefreshTokenSession.user_id == user.id,
                RefreshTokenSession.revoked_at.is_(None),
            ).update({"revoked_at": now}, synchronize_session=False)

            # Cancel any pending/unstarted consultations
            self.db.query(Consultation).filter(
                (Consultation.client_id == user.id) | (Consultation.lawyer_id == user.id),
                Consultation.status.in_([ConsultationStatus.REQUESTED, ConsultationStatus.ACCEPTED]),
            ).update({"status": ConsultationStatus.CANCELLED}, synchronize_session=False)

        self.db.commit()
        self.db.refresh(user)

        # Audit log creation
        from app.services.auth_service import AuthService
        auth_svc = AuthService(self.db)
        auth_svc.log_audit_event(
            "USER_LIFECYCLE_TRANSITION",
            user.id,
            {
                "previous_status": previous_status.value,
                "target_status": target_status.value,
                "reason": reason,
                "operator_id": str(operator.id) if operator else "SYSTEM",
            },
            action="lifecycle_transition",
        )

        logger.info(
            f"User {user.id} lifecycle transitioned from {previous_status.value} to {target_status.value}. Reason: '{reason}'"
        )
        return user
