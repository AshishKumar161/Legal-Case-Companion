import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, TimestampMixin


class IncidentSeverity(str, enum.Enum):
    SEV1_CRITICAL = "SEV1_CRITICAL"
    SEV2_HIGH = "SEV2_HIGH"
    SEV3_MEDIUM = "SEV3_MEDIUM"
    SEV4_LOW = "SEV4_LOW"


class IncidentCategory(str, enum.Enum):
    SECURITY = "SECURITY"
    ABUSE = "ABUSE"
    SYSTEM_OUTAGE = "SYSTEM_OUTAGE"
    DATA_INTEGRITY = "DATA_INTEGRITY"
    AI_SAFETY = "AI_SAFETY"
    COMPLIANCE = "COMPLIANCE"
    PAYMENT = "PAYMENT"


class IncidentStatus(str, enum.Enum):
    DETECTED = "DETECTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    MITIGATED = "MITIGATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class IncidentDetector(str, enum.Enum):
    AUTOMATED_MONITOR = "AUTOMATED_MONITOR"
    OPERATOR = "OPERATOR"
    USER_REPORT = "USER_REPORT"
    AUDIT_WATCHER = "AUDIT_WATCHER"
    EXTERNAL = "EXTERNAL"


class ProductionIncident(Base, TimestampMixin):
    """Represents an operational, security, or compliance incident in production."""

    __tablename__ = "production_incidents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    incident_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(IncidentSeverity, name="incidentseverity"),
        nullable=False,
        index=True,
    )
    category: Mapped[IncidentCategory] = mapped_column(
        Enum(IncidentCategory, name="incidentcategory"),
        nullable=False,
        index=True,
    )
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus, name="incidentstatus"),
        default=IncidentStatus.DETECTED,
        nullable=False,
        index=True,
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mitigated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    affected_scope: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detected_by: Mapped[IncidentDetector] = mapped_column(
        Enum(IncidentDetector, name="incidentdetector"),
        default=IncidentDetector.AUTOMATED_MONITOR,
        nullable=False,
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    mitigation: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    postmortem_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    postmortem_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    assigned_to_user = relationship("User", foreign_keys=[assigned_to_user_id])
    timeline_events = relationship(
        "IncidentTimelineEvent",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentTimelineEvent.timestamp.asc()",
    )


class IncidentTimelineEvent(Base):
    """Chronological event log for an incident timeline."""

    __tablename__ = "incident_timeline_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("production_incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Relationships
    incident = relationship("ProductionIncident", back_populates="timeline_events")
    actor_user = relationship("User", foreign_keys=[actor_user_id])
