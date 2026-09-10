import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.consultation import Consultation
    from app.models.user import User


class ConsultationDocument(Base, TimestampMixin):
    """
    Stores documents uploaded and shared between client and lawyer during or for a consultation session.
    """
    __tablename__ = "consultation_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    consultation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploader_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False, default="application/pdf")
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    consultation: Mapped["Consultation"] = relationship(
        "Consultation", back_populates="documents"
    )
    uploader: Mapped["User"] = relationship("User")
