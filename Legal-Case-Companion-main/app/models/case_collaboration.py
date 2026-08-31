import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.document import Document
    from app.models.task import CaseTask
    from app.models.user import User


class CaseMessageType(str, enum.Enum):
    GENERAL = "GENERAL"
    FORMAL_NOTICE = "FORMAL_NOTICE"
    STATUS_UPDATE = "STATUS_UPDATE"
    DOCUMENT_SUBMISSION = "DOCUMENT_SUBMISSION"
    ACTION_REQUEST = "ACTION_REQUEST"


class MatterRequestType(str, enum.Enum):
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    INFORMATION_REQUEST = "INFORMATION_REQUEST"
    CONFIRMATION = "CONFIRMATION"
    REVIEW = "REVIEW"


class MatterRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    REVIEWED = "REVIEWED"
    CANCELLED = "CANCELLED"


class CaseMessage(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "case_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[CaseMessageType] = mapped_column(
        Enum(CaseMessageType, name="casemessagetype"),
        default=CaseMessageType.GENERAL,
        nullable=False,
    )
    linked_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    linked_task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("case_tasks.id", ondelete="SET NULL"), nullable=True
    )
    is_counsel_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    case: Mapped["Case"] = relationship("Case")
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])
    linked_document: Mapped["Document | None"] = relationship("Document", foreign_keys=[linked_document_id])
    linked_task: Mapped["CaseTask | None"] = relationship("CaseTask", foreign_keys=[linked_task_id])

    __table_args__ = (
        Index("ix_case_messages_case_created", "case_id", "created_at"),
    )


class MatterRequest(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "matter_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requesting_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    request_type: Mapped[MatterRequestType] = mapped_column(
        Enum(MatterRequestType, name="matterrequesttype"),
        default=MatterRequestType.DOCUMENT_UPLOAD,
        nullable=False,
    )
    status: Mapped[MatterRequestStatus] = mapped_column(
        Enum(MatterRequestStatus, name="matterrequeststatus"),
        default=MatterRequestStatus.PENDING,
        nullable=False,
        index=True,
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Response / Submission state
    submitted_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    response_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Review state
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case")
    requesting_user: Mapped["User"] = relationship("User", foreign_keys=[requesting_user_id])
    assigned_user: Mapped["User | None"] = relationship("User", foreign_keys=[assigned_user_id])
    submitted_document: Mapped["Document | None"] = relationship("Document", foreign_keys=[submitted_document_id])
    reviewed_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[reviewed_by_user_id])

    __table_args__ = (
        Index("ix_matter_requests_case_status", "case_id", "status"),
    )
