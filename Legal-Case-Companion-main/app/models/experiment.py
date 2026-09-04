import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ExperimentStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"


class PilotExperiment(Base, TimestampMixin, SoftDeleteMixin):
    """Structured pilot experiment model governing controlled feature and workflow hypotheses."""

    __tablename__ = "pilot_experiments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    experiment_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    cohort: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    success_metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    failure_metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[ExperimentStatus] = mapped_column(
        Enum(ExperimentStatus, name="experimentstatus"),
        default=ExperimentStatus.PLANNED,
        nullable=False,
        index=True,
    )
    decision: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    owner: Mapped["User | None"] = relationship("User")

    __table_args__ = (
        Index("ix_pilot_experiments_cohort_status", "cohort", "status"),
    )
