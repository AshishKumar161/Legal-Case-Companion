import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.message import Message
    from app.models.payment import Payment
    from app.models.user import ClientProfile, LawyerProfile


class ConsultationStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    ACCEPTED = "ACCEPTED"
    PAID = "PAID"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    NO_SHOW = "NO_SHOW"


class Consultation(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "consultations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("client_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    lawyer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lawyer_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), nullable=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    fee_amount: Mapped[float] = mapped_column(Numeric, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[ConsultationStatus] = mapped_column(
        Enum(ConsultationStatus, name="consultationstatus"),
        default=ConsultationStatus.REQUESTED,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    client: Mapped["ClientProfile"] = relationship(
        "ClientProfile", back_populates="consultations"
    )
    lawyer: Mapped["LawyerProfile"] = relationship(
        "LawyerProfile", back_populates="consultations"
    )
    case: Mapped["Case | None"] = relationship("Case", back_populates="consultations")
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="consultation", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="consultation", cascade="all, delete-orphan"
    )
