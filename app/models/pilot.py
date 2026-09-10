import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, TimestampMixin
from app.models.user import UserRole


class AllowlistIdentifierType(str, enum.Enum):
    EMAIL = "EMAIL"
    DOMAIN = "DOMAIN"
    USER_ID = "USER_ID"
    ORGANIZATION = "ORGANIZATION"


class AllowlistStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class PilotAllowlistEntry(Base, TimestampMixin):
    """Represents an approved entity authorized to register or access the platform during controlled pilot mode."""

    __tablename__ = "pilot_allowlist"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    identifier: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    identifier_type: Mapped[AllowlistIdentifierType] = mapped_column(
        Enum(AllowlistIdentifierType, name="allowlistidentifiertype"),
        default=AllowlistIdentifierType.EMAIL,
        nullable=False,
    )
    role_target: Mapped[UserRole | None] = mapped_column(
        Enum(UserRole, name="userrole"),
        nullable=True,
    )
    status: Mapped[AllowlistStatus] = mapped_column(
        Enum(AllowlistStatus, name="allowliststatus"),
        default=AllowlistStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    added_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    added_by_user = relationship("User", foreign_keys=[added_by_user_id])
