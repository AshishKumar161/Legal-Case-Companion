import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, TimestampMixin


class OperationalPermission(str, enum.Enum):
    USER_SUPPORT = "USER_SUPPORT"
    USER_MANAGEMENT = "USER_MANAGEMENT"
    SEC_OPS = "SEC_OPS"
    INCIDENT_MANAGE = "INCIDENT_MANAGE"
    COMPLIANCE_OPERATIONS = "COMPLIANCE_OPERATIONS"
    EVIDENCE_OPERATIONS = "EVIDENCE_OPERATIONS"
    BILLING_OPERATIONS = "BILLING_OPERATIONS"
    SYSTEM_OPERATIONS = "SYSTEM_OPERATIONS"
    PILOT_GOVERNANCE = "PILOT_GOVERNANCE"


class UserOperatorPermission(Base, TimestampMixin):
    """Associates fine-grained operational permissions with platform administrators and operators."""

    __tablename__ = "user_operator_permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission: Mapped[OperationalPermission] = mapped_column(
        Enum(OperationalPermission, name="operationalpermission"),
        nullable=False,
        index=True,
    )
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    granted_by_user = relationship("User", foreign_keys=[granted_by_user_id])
