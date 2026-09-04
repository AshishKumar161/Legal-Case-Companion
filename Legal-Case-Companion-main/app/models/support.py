import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.incident import ProductionIncident
    from app.models.user import User


class SupportCaseSeverity(str, enum.Enum):
    SEV1_CRITICAL = "SEV1_CRITICAL"
    SEV2_HIGH = "SEV2_HIGH"
    SEV3_MEDIUM = "SEV3_MEDIUM"
    SEV4_LOW = "SEV4_LOW"


class SupportCaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    PENDING_USER = "PENDING_USER"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class SupportCase(Base, TimestampMixin, SoftDeleteMixin):
    """Structured customer support case record governed under strict zero-trust boundaries."""

    __tablename__ = "support_cases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    support_case_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[SupportCaseSeverity] = mapped_column(
        Enum(SupportCaseSeverity, name="supportcaseseverity"),
        default=SupportCaseSeverity.SEV3_MEDIUM,
        nullable=False,
        index=True,
    )
    user_scope: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # CLIENT, LAWYER, OPERATOR
    workflow: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # ONBOARDING, CONSULTATION, etc.

    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[SupportCaseStatus] = mapped_column(
        Enum(SupportCaseStatus, name="supportcasestatus"),
        default=SupportCaseStatus.OPEN,
        nullable=False,
        index=True,
    )
    resolution_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    linked_incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("production_incidents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    linked_release_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    user: Mapped["User | None"] = relationship("User", foreign_keys=[user_id])
    assigned_to: Mapped["User | None"] = relationship("User", foreign_keys=[assigned_to_user_id])
    linked_incident: Mapped["ProductionIncident | None"] = relationship("ProductionIncident")

    __table_args__ = (
        Index("ix_support_cases_status_severity", "status", "severity"),
    )
