import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.user import User


class ProductEventType(str, enum.Enum):
    USER_REGISTERED = "USER_REGISTERED"
    CASE_CREATED = "CASE_CREATED"
    CASE_UPDATED = "CASE_UPDATED"
    LAWYER_SEARCHED = "LAWYER_SEARCHED"
    LAWYER_SELECTED = "LAWYER_SELECTED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_PROCESSED = "DOCUMENT_PROCESSED"
    INTELLIGENCE_VIEWED = "INTELLIGENCE_VIEWED"
    COPILOT_QUERIED = "COPILOT_QUERIED"
    TASK_CREATED = "TASK_CREATED"
    TASK_COMPLETED = "TASK_COMPLETED"
    MATTER_REQUEST_CREATED = "MATTER_REQUEST_CREATED"
    MATTER_REQUEST_SUBMITTED = "MATTER_REQUEST_SUBMITTED"
    DECISION_RECORDED = "DECISION_RECORDED"
    HEARING_SCHEDULED = "HEARING_SCHEDULED"
    CONSULTATION_REQUESTED = "CONSULTATION_REQUESTED"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    CONSULTATION_COMPLETED = "CONSULTATION_COMPLETED"
    AI_REQUESTED = "AI_REQUESTED"
    # Phase XIX Funnel & Workflow Additions
    ONBOARDING_COMPLETED = "ONBOARDING_COMPLETED"
    EVIDENCE_UPLOADED = "EVIDENCE_UPLOADED"
    EVIDENCE_REVIEWED = "EVIDENCE_REVIEWED"
    CASE_MILESTONE_REACHED = "CASE_MILESTONE_REACHED"
    LAWYER_VERIFICATION_SUBMITTED = "LAWYER_VERIFICATION_SUBMITTED"
    LAWYER_VERIFICATION_COMPLETED = "LAWYER_VERIFICATION_COMPLETED"
    LAWYER_PROFILE_COMPLETED = "LAWYER_PROFILE_COMPLETED"
    LAWYER_AVAILABILITY_CONFIGURED = "LAWYER_AVAILABILITY_CONFIGURED"
    CONSULTATION_ACCEPTED = "CONSULTATION_ACCEPTED"
    ACCOUNT_DELETED = "ACCOUNT_DELETED"


class ProductEvent(Base):
    __tablename__ = "product_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    event_type: Mapped[ProductEventType] = mapped_column(
        Enum(ProductEventType, name="producteventtype"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=True
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    user: Mapped["User | None"] = relationship("User")
    case: Mapped["Case | None"] = relationship("Case")
