import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.user import User


class CaseNoteVisibility(str, enum.Enum):
    CLIENT_PRIVATE = "CLIENT_PRIVATE"
    LAWYER_PRIVATE = "LAWYER_PRIVATE"
    SHARED = "SHARED"


class CaseNote(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "case_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[CaseNoteVisibility] = mapped_column(
        Enum(CaseNoteVisibility, name="casenotevisibility"),
        default=CaseNoteVisibility.SHARED,
        nullable=False,
        index=True,
    )
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="notes")
    author: Mapped["User"] = relationship("User")
