import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.ai import AIConversation, AIMessage
    from app.models.incident import ProductionIncident
    from app.models.user import User


class AIReviewCategory(str, enum.Enum):
    HALLUCINATION = "HALLUCINATION"
    MISSING_CITATION = "MISSING_CITATION"
    INCORRECT_CITATION = "INCORRECT_CITATION"
    WRONG_JURISDICTION = "WRONG_JURISDICTION"
    OUTDATED_LAW = "OUTDATED_LAW"
    UNSAFE_RECOMMENDATION = "UNSAFE_RECOMMENDATION"
    EXCESSIVE_CONFIDENCE = "EXCESSIVE_CONFIDENCE"
    FAILURE_TO_REFUSE = "FAILURE_TO_REFUSE"
    UNNECESSARY_REFUSAL = "UNNECESSARY_REFUSAL"
    RETRIEVAL_FAILURE = "RETRIEVAL_FAILURE"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    ACCEPTABLE = "ACCEPTABLE"


class AIReviewSeverity(str, enum.Enum):
    SEV1_CRITICAL = "SEV1_CRITICAL"
    SEV2_HIGH = "SEV2_HIGH"
    SEV3_MEDIUM = "SEV3_MEDIUM"
    SEV4_LOW = "SEV4_LOW"


class AIReviewOutcome(str, enum.Enum):
    CONFIRMED_DEFECT = "CONFIRMED_DEFECT"
    FALSE_ALARM = "FALSE_ALARM"
    BENIGN_DISCREPANCY = "BENIGN_DISCREPANCY"
    TRAINING_GAP = "TRAINING_GAP"


class AIReviewStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    ACTIONED = "ACTIONED"
    DISMISSED = "DISMISSED"


class AIReviewRecord(Base, TimestampMixin, SoftDeleteMixin):
    """Human-in-the-loop review ledger for AI legal outputs, grounding verification, and safety auditing."""

    __tablename__ = "ai_human_reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    review_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    category: Mapped[AIReviewCategory] = mapped_column(
        Enum(AIReviewCategory, name="aireviewcategory"), nullable=False, index=True
    )
    severity: Mapped[AIReviewSeverity] = mapped_column(
        Enum(AIReviewSeverity, name="aireviewseverity"),
        default=AIReviewSeverity.SEV3_MEDIUM,
        nullable=False,
        index=True,
    )
    review_outcome: Mapped[AIReviewOutcome] = mapped_column(
        Enum(AIReviewOutcome, name="aireviewoutcome"),
        default=AIReviewOutcome.CONFIRMED_DEFECT,
        nullable=False,
        index=True,
    )
    status: Mapped[AIReviewStatus] = mapped_column(
        Enum(AIReviewStatus, name="aireviewstatus"),
        default=AIReviewStatus.PENDING,
        nullable=False,
        index=True,
    )

    original_prompt_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_answer_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)

    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    retrieval_config_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    linked_release_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    linked_incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("production_incidents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    reviewer: Mapped["User | None"] = relationship("User")
    message: Mapped["AIMessage | None"] = relationship("AIMessage")
    conversation: Mapped["AIConversation | None"] = relationship("AIConversation")
    linked_incident: Mapped["ProductionIncident | None"] = relationship("ProductionIncident")

    __table_args__ = (
        Index("ix_ai_reviews_cat_outcome", "category", "review_outcome"),
    )
