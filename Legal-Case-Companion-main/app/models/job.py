import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.user import User


class JobType(str, enum.Enum):
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    DOCUMENT_INDEXING = "DOCUMENT_INDEXING"
    CASE_INTELLIGENCE_REFRESH = "CASE_INTELLIGENCE_REFRESH"
    DEADLINE_REMINDER_SCAN = "DEADLINE_REMINDER_SCAN"
    TASK_OVERDUE_SCAN = "TASK_OVERDUE_SCAN"
    STALE_JOB_RECOVERY = "STALE_JOB_RECOVERY"
    NOTIFICATION_DELIVERY = "NOTIFICATION_DELIVERY"
    LEGAL_AUTHORITY_INGESTION = "LEGAL_AUTHORITY_INGESTION"
    LEGAL_AUTHORITY_REINDEX = "LEGAL_AUTHORITY_REINDEX"
    EVIDENCE_SCAN_AND_ACTIVATE = "EVIDENCE_SCAN_AND_ACTIVATE"
    EVIDENCE_INTEGRITY_AUDIT = "EVIDENCE_INTEGRITY_AUDIT"
    EVIDENCE_ORPHAN_RECONCILIATION = "EVIDENCE_ORPHAN_RECONCILIATION"
    ABANDONED_UPLOAD_CLEANUP = "ABANDONED_UPLOAD_CLEANUP"
    OUTBOX_DISPATCH = "OUTBOX_DISPATCH"


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"
    DEAD_LETTER = "DEAD_LETTER"


class BackgroundJob(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "background_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    job_type: Mapped[JobType] = mapped_column(
        Enum(JobType, name="jobtype"), nullable=False, index=True
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="jobstatus"),
        default=JobStatus.PENDING,
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    locked_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    result_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    case: Mapped["Case | None"] = relationship("Case")
    created_by: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_user_id])

    __table_args__ = (
        Index("ix_background_jobs_status_scheduled", "status", "scheduled_at"),
        Index("ix_background_jobs_claim", "status", "scheduled_at", "locked_until"),
    )
