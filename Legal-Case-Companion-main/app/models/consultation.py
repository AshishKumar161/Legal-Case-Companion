import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.consultation_document import ConsultationDocument
    from app.models.consultation_note import ConsultationNote
    from app.models.message import Message
    from app.models.payment import Payment
    from app.models.user import ClientProfile, LawyerProfile
    from app.models.video_meeting import VideoMeeting
    from app.models.video_recording import VideoRecording, VideoRecordingConsent


class ConsultationStatus(str, enum.Enum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    CLIENT_AUTHORIZED = "CLIENT_AUTHORIZED"
    LAWYER_ACCEPTED = "LAWYER_ACCEPTED"
    MUTUAL_CONSENT = "MUTUAL_CONSENT"
    IN_PROGRESS = "IN_PROGRESS"
    ENDED = "ENDED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    NO_SHOW = "NO_SHOW"
    REQUESTED = "REQUESTED"
    PAID = "PAID"
    ACCEPTED = "ACCEPTED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"


class Consultation(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "consultations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("client_profiles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    lawyer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lawyer_profiles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), nullable=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    is_instant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    fee_amount: Mapped[float] = mapped_column(Numeric, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[ConsultationStatus] = mapped_column(
        Enum(ConsultationStatus, name="consultationstatus"),
        default=ConsultationStatus.REQUESTED,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index("ix_consultations_lawyer_scheduled", "lawyer_id", "scheduled_at"),
        Index("ix_consultations_status", "status"),
        Index("ix_consultations_is_instant", "is_instant"),
    )

    client: Mapped["ClientProfile"] = relationship("ClientProfile", back_populates="consultations")
    lawyer: Mapped["LawyerProfile"] = relationship("LawyerProfile", back_populates="consultations")
    case: Mapped["Case | None"] = relationship("Case", back_populates="consultations")
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="consultation", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="consultation", cascade="all, delete-orphan"
    )
    video_meeting: Mapped["VideoMeeting | None"] = relationship(
        "VideoMeeting", back_populates="consultation", uselist=False, cascade="all, delete-orphan"
    )
    notes: Mapped[list["ConsultationNote"]] = relationship(
        "ConsultationNote", back_populates="consultation", cascade="all, delete-orphan"
    )
    documents: Mapped[list["ConsultationDocument"]] = relationship(
        "ConsultationDocument", back_populates="consultation", cascade="all, delete-orphan"
    )
    recordings: Mapped[list["VideoRecording"]] = relationship(
        "VideoRecording", back_populates="consultation", cascade="all, delete-orphan"
    )
    recording_consents: Mapped[list["VideoRecordingConsent"]] = relationship(
        "VideoRecordingConsent", back_populates="consultation", cascade="all, delete-orphan"
    )
