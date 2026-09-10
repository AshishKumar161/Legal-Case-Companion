import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.incident import ProductionIncident
    from app.models.user import User


class FeedbackCategory(str, enum.Enum):
    BUG = "BUG"
    CONFUSING_UX = "CONFUSING_UX"
    MISSING_CAPABILITY = "MISSING_CAPABILITY"
    AI_ISSUE = "AI_ISSUE"
    DOCUMENT_ISSUE = "DOCUMENT_ISSUE"
    OTHER = "OTHER"


class FeedbackType(str, enum.Enum):
    BUG = "BUG"
    USABILITY = "USABILITY"
    FEATURE_REQUEST = "FEATURE_REQUEST"
    LEGAL_RISK = "LEGAL_RISK"
    SECURITY_CONCERN = "SECURITY_CONCERN"
    AI_QUALITY = "AI_QUALITY"
    OPERATIONAL = "OPERATIONAL"


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
    feedback_type: Mapped[FeedbackType] = mapped_column(
        Enum(FeedbackType, name="feedbacktype"),
        default=FeedbackType.USABILITY,
        nullable=False,
        index=True,
    )
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)  # SEV1..SEV4
    workflow: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    sentiment: Mapped[str | None] = mapped_column(String(50), nullable=True)  # POSITIVE, NEUTRAL, NEGATIVE
    reproducibility: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ALWAYS, SOMETIMES, RARE

    description: Mapped[str] = mapped_column(Text, nullable=False)
    page_url: Mapped[str] = mapped_column(String(500), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="NEW", nullable=False, index=True)
    priority: Mapped[str | None] = mapped_column(String(20), default="P2", nullable=True)
    product_priority: Mapped[str | None] = mapped_column(String(20), default="P2", nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    linked_incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("production_incidents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    linked_release_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Relationships
    user: Mapped["User | None"] = relationship("User")
    linked_incident: Mapped["ProductionIncident | None"] = relationship("ProductionIncident")

    __table_args__ = (
        Index("ix_pilot_feedback_type_status", "feedback_type", "status"),
    )


Feedback = PilotFeedback
