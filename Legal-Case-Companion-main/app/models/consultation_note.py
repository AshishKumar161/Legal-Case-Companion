import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.consultation import Consultation
    from app.models.user import User


class ConsultationNote(Base, TimestampMixin):
    """
    Stores consultation summaries, advocate notes, and recommended action items.
    
    LEGAL NOTICE: Consultation notes represent professional work-product and record-keeping
    summaries documented by legal practitioners. They do not constitute automated or
    algorithmically verified legal opinions by the LCC platform.
    """
    __tablename__ = "consultation_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    consultation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    action_items: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    client_shared: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    consultation: Mapped["Consultation"] = relationship(
        "Consultation", back_populates="notes"
    )
    author: Mapped["User"] = relationship("User")
