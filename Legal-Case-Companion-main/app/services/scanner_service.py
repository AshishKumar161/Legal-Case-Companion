import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError, ValidationError
from app.models.document import Document, DocumentSecurityStatus
from app.models.job import JobType
from app.services.auth_service import AuthService
from app.services.job_service import JobService

logger = logging.getLogger(__name__)


class ScannerService:
    """DEVELOPMENT ONLY - Malware Scanning Stub.

    In production, this would be replaced by an async worker triggered
    by an S3 event notification or a message queue consumer.

    DEVELOPMENT/TEST STUB: This simulates malware scanning.
    Do NOT use in production for real malware protection.
    """

    def __init__(self, db: Session):
        self.db = db

    def simulate_scan(self, document_id: UUID, is_safe: bool = True):
        """Simulates the async malware scanning process or acts as the webhook handler.

        Lifecycle: QUARANTINED -> VALIDATING -> SCANNING -> SAFE / REJECTED
        """
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ResourceNotFoundError("Document not found")

        if document.deleted_at is not None:
            logger.warning(
                f"Webhook received for deleted document {document_id}. Ignoring."
            )
            return

        # Idempotency check: if already processed, just return successfully
        if document.security_status in (
            DocumentSecurityStatus.SAFE,
            DocumentSecurityStatus.REJECTED,
        ):
            logger.info(
                f"Document {document_id} already in terminal state {document.security_status.name}. Ignoring."
            )
            return

        valid_prior_states = (
            DocumentSecurityStatus.QUARANTINED,
            DocumentSecurityStatus.VALIDATING,
            DocumentSecurityStatus.SCANNING,
        )
        if document.security_status not in valid_prior_states:
            logger.error(
                f"Invalid state transition for document {document_id} from {document.security_status.name}."
            )
            raise ValidationError(
                f"Invalid state transition from {document.security_status.name}"
            )

        auth_svc = AuthService(self.db)

        # We only log VALIDATING and SCANNING if we are coming from QUARANTINED
        # to prevent duplicate audit logs in case of retries.
        if document.security_status == DocumentSecurityStatus.QUARANTINED:
            document.security_status = DocumentSecurityStatus.VALIDATING
            self.db.commit()
            auth_svc.log_audit_event(
                event_type="DOCUMENT_VALIDATION_STARTED",
                user_id=document.uploaded_by,
                metadata={"resource_type": "document", "resource_id": str(document.id)},
                action="document_mutation",
            )
            document.security_status = DocumentSecurityStatus.SCANNING
            self.db.commit()
            auth_svc.log_audit_event(
                event_type="DOCUMENT_SCANNING_STARTED",
                user_id=document.uploaded_by,
                metadata={"resource_type": "document", "resource_id": str(document.id)},
                action="document_mutation",
            )

        if is_safe:
            document.security_status = DocumentSecurityStatus.SAFE
            action = "DOCUMENT_SAFE"
        else:
            document.security_status = DocumentSecurityStatus.REJECTED
            action = "DOCUMENT_REJECTED"

        self.db.commit()
        auth_svc.log_audit_event(
            event_type=action,
            user_id=document.uploaded_by,
            metadata={"resource_type": "document", "resource_id": str(document.id)},
            action="document_mutation",
        )

        # Trigger document processing if safe (e.g. text extraction)
        if is_safe:
            job_svc = JobService(self.db)
            job_svc.enqueue_job(
                job_type=JobType.DOCUMENT_PROCESSING,
                payload={"document_id": str(document.id), "generate_embeddings": True},
                idempotency_key=f"doc_proc_{document.id}_v{document.version}",
                case_id=document.case_id,
                created_by_user_id=document.uploaded_by,
            )

            auth_svc.log_audit_event(
                event_type="DOCUMENT_PROCESSING_ENQUEUED",
                user_id=document.uploaded_by,
                metadata={
                    "resource_type": "document",
                    "resource_id": str(document.id),
                    "version": document.version,
                },
                action="document_mutation",
            )
