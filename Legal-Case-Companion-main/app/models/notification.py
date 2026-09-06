import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.consultation import Consultation
    from app.models.document import Document
    from app.models.task import CaseTask
    from app.models.user import User
    from app.models.workflow import CaseDeadline, CaseHearing


class NotificationType(str, enum.Enum):
    # Case events
    CASE_CREATED = "CASE_CREATED"
    CASE_STATUS_CHANGED = "CASE_STATUS_CHANGED"
    PARTICIPANT_ADDED = "PARTICIPANT_ADDED"
    LAWYER_ASSIGNED = "LAWYER_ASSIGNED"

    # Task events
    TASK_ASSIGNED = "TASK_ASSIGNED"
    TASK_DUE_SOON = "TASK_DUE_SOON"
    TASK_OVERDUE = "TASK_OVERDUE"
    TASK_COMPLETED = "TASK_COMPLETED"

    # Deadline & Hearing events
    DEADLINE_APPROACHING = "DEADLINE_APPROACHING"
    DEADLINE_OVERDUE = "DEADLINE_OVERDUE"
    HEARING_REMINDER = "HEARING_REMINDER"

    # Document & Intelligence events
    DOCUMENT_READY = "DOCUMENT_READY"
    DOCUMENT_PROCESSING_FAILED = "DOCUMENT_PROCESSING_FAILED"
    AI_REVIEW_REQUIRED = "AI_REVIEW_REQUIRED"

    # Consultation events
    CONSULTATION_REQUESTED = "CONSULTATION_REQUESTED"
    CONSULTATION_ACCEPTED = "CONSULTATION_ACCEPTED"
    CONSULTATION_REJECTED = "CONSULTATION_REJECTED"
    CONSULTATION_SCHEDULED = "CONSULTATION_SCHEDULED"
    CONSULTATION_CANCELLED = "CONSULTATION_CANCELLED"
    CONSULTATION_COMPLETED = "CONSULTATION_COMPLETED"

    # Payment events
    PAYMENT_CREATED = "PAYMENT_CREATED"
    PAYMENT_SUCCEEDED = "PAYMENT_SUCCEEDED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_REFUNDED = "PAYMENT_REFUNDED"

    # Collaboration & Request events
    MATTER_REQUEST_CREATED = "MATTER_REQUEST_CREATED"
    MATTER_REQUEST_SUBMITTED = "MATTER_REQUEST_SUBMITTED"
    MATTER_REQUEST_REVIEWED = "MATTER_REQUEST_REVIEWED"
    MATTER_MESSAGE_RECEIVED = "MATTER_MESSAGE_RECEIVED"

    # Phase 9: Deterministic Delta & Reminder events
    HEARING_DATE_CHANGED = "HEARING_DATE_CHANGED"
    COURT_STATUS_CHANGED = "COURT_STATUS_CHANGED"
    NEW_COURT_ORDER = "NEW_COURT_ORDER"
    DOCUMENT_REQUESTED = "DOCUMENT_REQUESTED"
    LAWYER_MESSAGE_RECEIVED = "LAWYER_MESSAGE_RECEIVED"
    CONSULTATION_REMINDER = "CONSULTATION_REMINDER"
    PAYMENT_REMINDER = "PAYMENT_REMINDER"
    DOCUMENT_REMINDER = "DOCUMENT_REMINDER"


class Notification(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notificationtype"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    consultation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("consultations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("case_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    deadline_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("case_deadlines.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    hearing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("case_hearings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    event_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    case: Mapped["Case | None"] = relationship("Case")
    consultation: Mapped["Consultation | None"] = relationship("Consultation")
    task: Mapped["CaseTask | None"] = relationship("CaseTask")
    deadline: Mapped["CaseDeadline | None"] = relationship("CaseDeadline")
    hearing: Mapped["CaseHearing | None"] = relationship("CaseHearing")
    document: Mapped["Document | None"] = relationship("Document")

    __table_args__ = (
        Index(
            "ix_notifications_user_is_read_created", "user_id", "is_read", "created_at"
        ),
        Index("ix_notifications_user_event_type", "user_id", "event_id", "type"),
    )


class UserNotificationPreference(Base, TimestampMixin):
    __tablename__ = "user_notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    case_updates: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    task_updates: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    consultation_updates: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User")
