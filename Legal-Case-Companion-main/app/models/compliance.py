import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.identifiers import generate_uuid7
from app.models.base import Base, TimestampMixin


class ComplianceItemStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    CONDITIONALLY_APPROVED = "CONDITIONALLY_APPROVED"
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ComplianceRegistryItem(Base, TimestampMixin):
    __tablename__ = "compliance_registry_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    compliance_item_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    requirement_question: Mapped[str] = mapped_column(Text, nullable=False)
    technical_control: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    legal_reviewer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[ComplianceItemStatus] = mapped_column(
        Enum(ComplianceItemStatus, name="complianceitemstatus"),
        default=ComplianceItemStatus.OPEN,
        nullable=False,
    )
    technical_readiness: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    contractual_readiness: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    policy_readiness: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    legal_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(255), nullable=True)
    follow_up: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_compliance_status", "status"),
        Index("ix_compliance_owner", "owner"),
    )
