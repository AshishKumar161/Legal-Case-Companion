import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.metrics import metrics_collector
from app.middleware.correlation_id import correlation_id_ctx
from app.models.job import JobType
from app.models.outbox import OutboxEvent, OutboxStatus
from app.services.job_service import JobService

logger = logging.getLogger(__name__)


class OutboxService:
    """Transactional Outbox service ensuring durable asynchronous event dispatch."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def emit_event(
        db: Session,
        event_type: str,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        payload: dict[str, Any],
        headers: dict[str, Any] | None = None,
    ) -> OutboxEvent:
        """Emits an outbox event atomically within the caller's active database transaction."""
        req_id = correlation_id_ctx.get()
        effective_headers = headers or {}
        if "correlation_id" not in effective_headers:
            effective_headers["correlation_id"] = req_id

        event = OutboxEvent(
            id=generate_uuid7(),
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            headers=effective_headers,
            status=OutboxStatus.PENDING,
            attempt_count=0,
            max_attempts=5,
            scheduled_at=datetime.now(UTC),
        )
        db.add(event)
        # Note: We do NOT commit here so the event commits atomically with the caller's business transaction.
        return event

    def claim_pending_batch(self, limit: int = 20) -> list[OutboxEvent]:
        """Atomically claims a batch of pending/retryable outbox events."""
        now = datetime.now(UTC)
        query = (
            self.db.query(OutboxEvent)
            .filter(
                OutboxEvent.status.in_([OutboxStatus.PENDING, OutboxStatus.FAILED]),
                OutboxEvent.scheduled_at <= now,
                OutboxEvent.attempt_count < OutboxEvent.max_attempts,
            )
            .order_by(OutboxEvent.scheduled_at.asc())
            .limit(limit)
        )

        # On PostgreSQL, skip locked rows to allow parallel outbox workers
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)

        events = query.all()
        for evt in events:
            evt.status = OutboxStatus.PROCESSING
            evt.attempt_count += 1

        if events:
            self.db.commit()
            for evt in events:
                self.db.refresh(evt)

        return events

    def dispatch_event(self, event: OutboxEvent) -> bool:
        """Dispatches an individual outbox event to its downstream subsystem."""
        try:
            job_svc = JobService(self.db)
            event_type = event.event_type

            if event_type == "EVIDENCE_UPLOADED":
                # Enqueue background scanning and activation
                version_id = event.payload.get("version_id")
                case_id_str = event.payload.get("case_id")
                case_id = uuid.UUID(case_id_str) if case_id_str else None
                job_svc.enqueue_job(
                    job_type=JobType.EVIDENCE_SCAN_AND_ACTIVATE,
                    payload={
                        "evidence_id": str(event.aggregate_id),
                        "version_id": str(version_id),
                        "case_id": str(case_id) if case_id else None,
                        "_correlation_id": event.headers.get("correlation_id", "-"),
                    },
                    idempotency_key=f"scan_ev_{event.aggregate_id}_{version_id}",
                    case_id=case_id,
                )

            elif event_type == "NOTIFICATION_DISPATCH":
                # Enqueue asynchronous notification delivery
                job_svc.enqueue_job(
                    job_type=JobType.NOTIFICATION_DELIVERY,
                    payload=event.payload,
                    idempotency_key=f"notif_{event.id}",
                )

            # Mark as successfully published
            event.status = OutboxStatus.PUBLISHED
            event.processed_at = datetime.now(UTC)
            event.last_error = None
            event.error_category = None
            self.db.commit()

            metrics_collector.record_outbox_event(event.event_type, "PUBLISHED")
            return True

        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Outbox dispatch error for event {event.id} ({event.event_type}): {exc}")
            now = datetime.now(UTC)
            event.last_error = str(exc)

            if event.attempt_count >= event.max_attempts:
                event.status = OutboxStatus.DEAD_LETTER
                event.error_category = "EXHAUSTED"
                metrics_collector.record_outbox_event(event.event_type, "DEAD_LETTER")
            else:
                event.status = OutboxStatus.FAILED
                backoff_sec = (2 ** event.attempt_count) * 5
                event.scheduled_at = now + timedelta(seconds=backoff_sec)
                event.error_category = "RETRYABLE"
                metrics_collector.record_outbox_event(event.event_type, "RETRYING")

            self.db.commit()
            return False

    def process_outbox_batch(self, limit: int = 20) -> int:
        """Claims and dispatches a batch of outbox events."""
        events = self.claim_pending_batch(limit=limit)
        success_count = 0
        for evt in events:
            if self.dispatch_event(evt):
                success_count += 1
        return success_count
