import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class DataQualityRunType(str, enum.Enum):
    AUDIT_ONLY = "AUDIT_ONLY"
    AUDIT_AND_REPAIR = "AUDIT_AND_REPAIR"


class DataQualityRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED_CLEAN = "COMPLETED_CLEAN"
    COMPLETED_WITH_ANOMALIES = "COMPLETED_WITH_ANOMALIES"
    COMPLETED_WITH_REPAIRS = "COMPLETED_WITH_REPAIRS"
    FAILED = "FAILED"


class DataQualityRun(Base, TimestampMixin):
    """Auditable log of database consistency, entity integrity, and automated reconciliation runs."""

    __tablename__ = "data_quality_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    run_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    run_type: Mapped[DataQualityRunType] = mapped_column(
        Enum(DataQualityRunType, name="dataqualityruntype"), nullable=False
    )
    status: Mapped[DataQualityRunStatus] = mapped_column(
        Enum(DataQualityRunStatus, name="dataqualityrunstatus"),
        default=DataQualityRunStatus.RUNNING,
        nullable=False,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    entities_audited: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    anomalies_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    repairs_executed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    anomaly_breakdown: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    repair_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_automated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    triggered_by: Mapped["User | None"] = relationship("User")
