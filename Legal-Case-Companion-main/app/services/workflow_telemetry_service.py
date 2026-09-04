import enum
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.analytics import ProductEvent, ProductEventType
from app.models.user import User, UserRole


class WorkflowType(str, enum.Enum):
    REGISTRATION = "REGISTRATION"
    AUTHENTICATION = "AUTHENTICATION"
    CASE_CREATION = "CASE_CREATION"
    PARTICIPANT_OPERATIONS = "PARTICIPANT_OPERATIONS"
    LAWYER_DISCOVERY = "LAWYER_DISCOVERY"
    CONSULTATION_BOOKING = "CONSULTATION_BOOKING"
    CONSULTATION_ACCEPTANCE = "CONSULTATION_ACCEPTANCE"
    VIDEO_INITIATION = "VIDEO_INITIATION"
    EVIDENCE_UPLOAD = "EVIDENCE_UPLOAD"
    EVIDENCE_ACTIVATION = "EVIDENCE_ACTIVATION"
    EVIDENCE_DOWNLOAD = "EVIDENCE_DOWNLOAD"
    EVIDENCE_SHARING = "EVIDENCE_SHARING"
    AI_RETRIEVAL = "AI_RETRIEVAL"
    AI_RESPONSE = "AI_RESPONSE"
    FEEDBACK_SUBMISSION = "FEEDBACK_SUBMISSION"
    ACCOUNT_DELETION = "ACCOUNT_DELETION"


class WorkflowExecutionStatus(str, enum.Enum):
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    EXPECTED_FAILURE = "EXPECTED_FAILURE"  # e.g., validation error, insufficient capacity
    UNEXPECTED_FAILURE = "UNEXPECTED_FAILURE"  # e.g., 500 error, DB exception
    ABANDONED = "ABANDONED"


class WorkflowTelemetryService:
    """Instruments core legal workflows, computes funnel drop-offs, and enforces analytics privacy."""

    # Sensitive keys strictly stripped from telemetry payloads (Part T)
    SENSITIVE_KEYS = {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "authorization",
        "raw_content",
        "content",
        "document_text",
        "case_description",
        "legal_notes",
        "consultation_notes",
        "pii",
    }

    def __init__(self, db: Session):
        self.db = db

    def _sanitize_metadata(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        """Ensures product analytics do not become a secondary sensitive-data store."""
        if not metadata:
            return {}
        sanitized = {}
        for k, v in metadata.items():
            k_lower = str(k).lower()
            if any(sens in k_lower for sens in self.SENSITIVE_KEYS):
                continue
            if isinstance(v, (str, int, float, bool)) or v is None:
                if isinstance(v, str) and len(v) > 200:
                    sanitized[k] = v[:200] + "...[TRUNCATED]"
                else:
                    sanitized[k] = v
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize_metadata(v)
            elif isinstance(v, (list, tuple)):
                sanitized[k] = [
                    self._sanitize_metadata(item) if isinstance(item, dict) else str(item)[:100]
                    for item in v[:10]
                ]
        return sanitized

    def record_workflow_event(
        self,
        workflow: WorkflowType,
        status: WorkflowExecutionStatus,
        user_id: uuid.UUID | None = None,
        case_id: uuid.UUID | None = None,
        duration_ms: float | None = None,
        error_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProductEvent:
        now = datetime.now(UTC)
        safe_meta = self._sanitize_metadata(metadata)
        safe_meta.update({
            "workflow": workflow.value,
            "status": status.value,
            "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
            "error_code": error_code,
        })

        # Map to matching ProductEventType if available
        type_mapping = {
            WorkflowType.REGISTRATION: ProductEventType.USER_REGISTERED,
            WorkflowType.CASE_CREATION: ProductEventType.CASE_CREATED,
            WorkflowType.LAWYER_DISCOVERY: ProductEventType.LAWYER_SEARCHED,
            WorkflowType.CONSULTATION_BOOKING: ProductEventType.CONSULTATION_REQUESTED,
            WorkflowType.CONSULTATION_ACCEPTANCE: ProductEventType.CONSULTATION_ACCEPTED,
            WorkflowType.EVIDENCE_UPLOAD: ProductEventType.EVIDENCE_UPLOADED,
            WorkflowType.AI_RETRIEVAL: ProductEventType.COPILOT_QUERIED,
            WorkflowType.ACCOUNT_DELETION: ProductEventType.ACCOUNT_DELETED,
        }
        event_type = type_mapping.get(workflow, ProductEventType.INTELLIGENCE_VIEWED)

        event = ProductEvent(
            id=generate_uuid7(),
            event_type=event_type,
            user_id=user_id,
            case_id=case_id,
            timestamp=now,
            metadata_=safe_meta,
        )
        self.db.add(event)
        self.db.commit()
        return event

    def get_funnel_summary(self) -> dict[str, Any]:
        """Calculates conversion drop-offs across both Client and Lawyer journey funnels."""
        total_registered_clients = (
            self.db.query(func.count(User.id))
            .filter(User.role == UserRole.CLIENT, User.deleted_at.is_(None))
            .scalar()
            or 0
        )
        total_registered_lawyers = (
            self.db.query(func.count(User.id))
            .filter(User.role == UserRole.LAWYER, User.deleted_at.is_(None))
            .scalar()
            or 0
        )

        def count_events(event_type: ProductEventType) -> int:
            return (
                self.db.query(func.count(ProductEvent.id))
                .filter(ProductEvent.event_type == event_type)
                .scalar()
                or 0
            )

        client_funnel = {
            "registered": total_registered_clients,
            "first_case_created": count_events(ProductEventType.CASE_CREATED),
            "lawyer_searched": count_events(ProductEventType.LAWYER_SEARCHED),
            "consultation_requested": count_events(ProductEventType.CONSULTATION_REQUESTED),
            "consultation_completed": count_events(ProductEventType.CONSULTATION_COMPLETED),
            "evidence_uploaded": count_events(ProductEventType.EVIDENCE_UPLOADED),
            "ai_interaction": count_events(ProductEventType.COPILOT_QUERIED),
        }

        lawyer_funnel = {
            "registered": total_registered_lawyers,
            "verification_submitted": count_events(ProductEventType.LAWYER_VERIFICATION_SUBMITTED),
            "availability_configured": count_events(ProductEventType.LAWYER_AVAILABILITY_CONFIGURED),
            "consultation_accepted": count_events(ProductEventType.CONSULTATION_ACCEPTED),
            "consultation_completed": count_events(ProductEventType.CONSULTATION_COMPLETED),
            "evidence_reviewed": count_events(ProductEventType.EVIDENCE_REVIEWED),
        }

        return {
            "client_funnel": client_funnel,
            "lawyer_funnel": lawyer_funnel,
            "sample_confidence": "HIGH" if (total_registered_clients + total_registered_lawyers) >= 30 else "INSUFFICIENT_SAMPLE_SIZE",
        }
