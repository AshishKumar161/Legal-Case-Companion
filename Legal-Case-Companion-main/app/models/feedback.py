import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class FeedbackCategory(str, enum.Enum):
    BUG = "BUG"
    CONFUSING_UX = "CONFUSING_UX"
    MISSING_CAPABILITY = "MISSING_CAPABILITY"
    AI_ISSUE = "AI_ISSUE"
    DOCUMENT_ISSUE = "DOCUMENT_ISSUE"
    OTHER = "OTHER"


class PilotFeedback(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "pilot_feedback"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[FeedbackCategory] = mapped_column(
        Enum(FeedbackCategory, name="feedbackcategory"),
        default=FeedbackCategory.OTHER,
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    page_url: Mapped[str] = mapped_column(String(500), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="NEW", nullable=False)
    priority: Mapped[str | None] = mapped_column(String(20), default="P2", nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User | None"] = relationship("User")


Feedback = PilotFeedback

from app.models.user import User
