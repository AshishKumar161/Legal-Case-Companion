import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.ai import DocumentChunk
    from app.models.consultation import Consultation
    from app.models.document import Document
    from app.models.note import CaseNote
    from app.models.task import CaseTask
    from app.models.user import User


class CaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class ParticipantRole(str, enum.Enum):
    OWNER = "OWNER"
    LAWYER = "LAWYER"
    VIEWER = "VIEWER"


class ParticipantStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Case(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, name="casestatus"), default=CaseStatus.OPEN, nullable=False
    )

    # Relationships
    participants: Mapped[list["CaseParticipant"]] = relationship(
        "CaseParticipant", back_populates="case", cascade="all, delete-orphan"
    )
    timeline_events: Mapped[list["CaseTimelineEvent"]] = relationship(
        "CaseTimelineEvent", back_populates="case", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="case", cascade="all, delete-orphan"
    )
    consultations: Mapped[list["Consultation"]] = relationship(
        "Consultation", back_populates="case", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["CaseTask"]] = relationship(
        "CaseTask", back_populates="case", cascade="all, delete-orphan"
    )
    notes: Mapped[list["CaseNote"]] = relationship(
        "CaseNote", back_populates="case", cascade="all, delete-orphan"
    )
    document_chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="case", cascade="all, delete-orphan"
    )


class CaseParticipant(Base, TimestampMixin):
    __tablename__ = "case_participants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    participant_role: Mapped[ParticipantRole] = mapped_column(
        Enum(ParticipantRole, name="participantrole"), nullable=False
    )
    status: Mapped[ParticipantStatus] = mapped_column(
        Enum(ParticipantStatus, name="participantstatus"),
        default=ParticipantStatus.ACTIVE,
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="participants")
    user: Mapped["User"] = relationship("User", back_populates="case_participants")

    __table_args__ = (
        UniqueConstraint("case_id", "user_id", name="uq_case_participant_case_user"),
    )


class CaseTimelineEvent(Base, TimestampMixin):
    __tablename__ = "case_timeline_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="timeline_events")
    actor: Mapped["User | None"] = relationship("User")
