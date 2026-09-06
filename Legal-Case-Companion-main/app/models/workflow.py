import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.evidence import CaseExhibit
    from app.models.user import User


class TaskSourceType(str, enum.Enum):
    MANUAL = "MANUAL"
    EVIDENCE_GAP = "EVIDENCE_GAP"
    AI_SUGGESTED = "AI_SUGGESTED"
    CHRONOLOGY_EVENT = "CHRONOLOGY_EVENT"
    COURT_ORDER = "COURT_ORDER"


class DeadlineType(str, enum.Enum):
    STATUTORY_LIMITATION = "STATUTORY_LIMITATION"
    COURT_FILING = "COURT_FILING"
    REPLY_NOTICE = "REPLY_NOTICE"
    COMPLIANCE = "COMPLIANCE"
    CONSULTATION = "CONSULTATION"
    GENERAL = "GENERAL"


class DeadlineStatus(str, enum.Enum):
    UPCOMING = "UPCOMING"
    DUE = "DUE"
    OVERDUE = "OVERDUE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DeadlineSourceType(str, enum.Enum):
    COURT_ORDER = "COURT_ORDER"
    LEGAL_AUTHORITY = "LEGAL_AUTHORITY"
    CASE_DOCUMENT = "CASE_DOCUMENT"
    USER_REPORTED = "USER_REPORTED"
    AI_SUGGESTED = "AI_SUGGESTED"
    MANUAL = "MANUAL"


class HearingStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    ADJOURNED = "ADJOURNED"
    CONCLUDED = "CONCLUDED"
    COMPLETED = "COMPLETED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"


class HearingSourceType(str, enum.Enum):
    COURT_ORDER = "COURT_ORDER"
    CAUSE_LIST = "CAUSE_LIST"
    CASE_DOCUMENT = "CASE_DOCUMENT"
    USER_REPORTED = "USER_REPORTED"
    AI_SUGGESTED = "AI_SUGGESTED"
    MANUAL = "MANUAL"


class ReminderTargetType(str, enum.Enum):
    TASK = "TASK"
    DEADLINE = "DEADLINE"
    HEARING = "HEARING"


class ReminderStatus(str, enum.Enum):
    PENDING = "PENDING"
    TRIGGERED = "TRIGGERED"
    DISMISSED = "DISMISSED"


class CaseDeadline(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "case_deadlines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    deadline_type: Mapped[DeadlineType] = mapped_column(
        Enum(DeadlineType, name="deadlinetype"),
        default=DeadlineType.GENERAL,
        nullable=False,
    )
    status: Mapped[DeadlineStatus] = mapped_column(
        Enum(DeadlineStatus, name="deadlinestatus"),
        default=DeadlineStatus.UPCOMING,
        nullable=False,
        index=True,
    )
    source_type: Mapped[DeadlineSourceType] = mapped_column(
        Enum(DeadlineSourceType, name="deadlinesourcetype"),
        default=DeadlineSourceType.MANUAL,
        nullable=False,
    )
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    linked_hearing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("case_hearings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    retrieval_method: Mapped[str | None] = mapped_column(String(50), default="MANUAL", nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case")
    created_by: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_user_id])
    linked_hearing: Mapped["CaseHearing | None"] = relationship("CaseHearing", foreign_keys=[linked_hearing_id])
    confirmed_by: Mapped["User | None"] = relationship("User", foreign_keys=[confirmed_by_user_id])


class CaseHearing(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "case_hearings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    court_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hearing_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[HearingStatus] = mapped_column(
        Enum(HearingStatus, name="hearingstatus"),
        default=HearingStatus.SCHEDULED,
        nullable=False,
        index=True,
    )
    bench_or_coram: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[HearingSourceType] = mapped_column(
        Enum(HearingSourceType, name="hearingsourcetype"),
        default=HearingSourceType.MANUAL,
        nullable=False,
    )
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    court_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hearing_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    next_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case")
    created_by: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_user_id])
    exhibits: Mapped[list["CaseExhibit"]] = relationship("CaseExhibit", back_populates="hearing")


class CaseReminder(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "case_reminders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[ReminderTargetType] = mapped_column(
        Enum(ReminderTargetType, name="remindertargettype"),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    remind_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus, name="reminderstatus"),
        default=ReminderStatus.PENDING,
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case")
    created_by: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_user_id])
