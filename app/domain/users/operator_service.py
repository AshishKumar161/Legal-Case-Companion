import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import AppException, NotFoundError
from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.operator import OperationalPermission, UserOperatorPermission
from app.models.user import User, UserRole


class OperatorService:
    """Manages fine-grained operational permissions for administrators and platform operators."""

    def __init__(self, db: Session):
        self.db = db

    def grant_permission(
        self,
        granter: User,
        target_user_id: uuid.UUID,
        permission: OperationalPermission,
    ) -> UserOperatorPermission:
        target = (
            self.db.query(User)
            .filter(User.id == target_user_id, User.deleted_at.is_(None))
            .first()
        )
        if not target:
            raise NotFoundError("Target user not found")
        if target.role != UserRole.ADMIN:
            raise AppException(
                status_code=400,
                code="INVALID_TARGET_ROLE",
                message="Operational permissions can only be granted to ADMIN accounts",
            )

        # Check if already active
        existing = (
            self.db.query(UserOperatorPermission)
            .filter(
                UserOperatorPermission.user_id == target_user_id,
                UserOperatorPermission.permission == permission,
                UserOperatorPermission.revoked_at.is_(None),
            )
            .first()
        )
        if existing:
            return existing

        grant = UserOperatorPermission(
            id=generate_uuid7(),
            user_id=target_user_id,
            permission=permission,
            granted_by_user_id=granter.id,
            created_at=datetime.now(UTC),
            revoked_at=None,
        )
        self.db.add(grant)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=granter.id,
            event_type="OPERATOR_PERMISSION_GRANTED",
            entity_type="USER_OPERATOR_PERMISSION",
            entity_id=grant.id,
            action="GRANT",
            timestamp=datetime.now(UTC),
            metadata_={
                "target_user_id": str(target_user_id),
                "permission": permission.value,
                "granter_email": granter.email,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(grant)
        return grant

    def revoke_permission(
        self,
        revoker: User,
        target_user_id: uuid.UUID,
        permission: OperationalPermission,
    ) -> None:
        grant = (
            self.db.query(UserOperatorPermission)
            .filter(
                UserOperatorPermission.user_id == target_user_id,
                UserOperatorPermission.permission == permission,
                UserOperatorPermission.revoked_at.is_(None),
            )
            .first()
        )
        if not grant:
            raise NotFoundError("Active permission grant not found")

        grant.revoked_at = datetime.now(UTC)
        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=revoker.id,
            event_type="OPERATOR_PERMISSION_REVOKED",
            entity_type="USER_OPERATOR_PERMISSION",
            entity_id=grant.id,
            action="REVOKE",
            timestamp=datetime.now(UTC),
            metadata_={
                "target_user_id": str(target_user_id),
                "permission": permission.value,
                "revoker_email": revoker.email,
            },
        )
        self.db.add(audit)
        self.db.commit()

    def list_user_permissions(self, user_id: uuid.UUID) -> list[OperationalPermission]:
        grants = (
            self.db.query(UserOperatorPermission)
            .filter(
                UserOperatorPermission.user_id == user_id,
                UserOperatorPermission.revoked_at.is_(None),
            )
            .all()
        )
        return [g.permission for g in grants]
