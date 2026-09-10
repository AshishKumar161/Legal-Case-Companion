import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.identifiers import generate_uuid7
from app.models.base import Base, TimestampMixin


class WebhookProcessingStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class ProcessedWebhookEvent(Base, TimestampMixin):
    __tablename__ = "processed_webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    event_id: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="STRIPE")
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[WebhookProcessingStatus] = mapped_column(
        Enum(WebhookProcessingStatus, name="webhookprocessingstatus"),
        default=WebhookProcessingStatus.PROCESSED,
        nullable=False,
    )
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_processed_webhook_events_provider_event", "provider", "event_id"),
    )
