import logging
import socket
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ResourceNotFoundError, ScannerUnavailableError, ValidationError
from app.core.file_validation import validate_file_magic_bytes
from app.core.storage import get_storage_provider
from app.models.document import Document, DocumentSecurityStatus
from app.models.job import JobType
from app.services.auth_service import AuthService
from app.services.job_service import JobService

logger = logging.getLogger(__name__)

# EICAR test string bytes for deterministic antivirus verification
EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


class MalwareScanner(Protocol):
    """Protocol for pluggable malware scanners (ClamAV daemon, AWS GuardDuty, Heuristic)."""

    def scan_bytes(self, file_bytes: bytes, filename: str) -> tuple[bool, str | None]:
        """Returns (is_safe: bool, threat_details: str | None)."""
        ...


class HeuristicSignatureScanner:
    """Deterministic pattern and heuristic scanner for legal document containers.

    Detects EICAR test viruses, PE/ELF executable headers, embedded PDF JavaScript macros,
    and script tags in document containers.
    """

    def scan_bytes(self, file_bytes: bytes, filename: str) -> tuple[bool, str | None]:
        if not file_bytes:
            return True, None

        # 1. EICAR Standard Antivirus Test Signature
        if EICAR_SIGNATURE in file_bytes:
            return False, "EICAR-Standard-AV-Test-Signature detected"

        # 2. Executable markers
        if file_bytes.startswith(b"MZ"):
            return False, "Windows PE Executable header detected (Win32/Trojan signature)"
        if file_bytes.startswith(b"\x7fELF"):
            return False, "Linux ELF Executable header detected"

        # 3. PDF embedded malicious execution vectors
        lower_bytes = file_bytes.lower()
        if b"%pdf" in lower_bytes[:1024]:
            if b"/javascript" in lower_bytes or b"/js " in lower_bytes:
                return False, "Embedded JavaScript detected inside PDF container"
            if b"/launch" in lower_bytes:
                return False, "Embedded Launch action detected inside PDF container"

        # 4. Embedded active HTML/Script execution in text or office files
        if b"<script" in lower_bytes or b"javascript:" in lower_bytes or b"vbscript:" in lower_bytes:
            return False, "Embedded active script execution payload detected"

        return True, None


class ClamAVScanner:
    """Production ClamAV daemon scanner communicating via TCP streaming socket protocol."""

    def __init__(self, host: str | None = None, port: int | None = None):
        self.host = host or getattr(settings, "CLAMAV_HOST", None)
        self.port = port or getattr(settings, "CLAMAV_PORT", 3310)

    def scan_bytes(self, file_bytes: bytes, filename: str) -> tuple[bool, str | None]:
        if not self.host:
            # ClamAV daemon host is not configured; pass through to secondary scanner
            return True, None

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(10.0)
                sock.connect((self.host, self.port))

                # Send zINSTREAM command
                sock.sendall(b"zINSTREAM\0")

                # Stream file bytes in 4KB chunks preceded by length
                chunk_size = 4096
                for i in range(0, len(file_bytes), chunk_size):
                    chunk = file_bytes[i : i + chunk_size]
                    chunk_len = len(chunk).to_bytes(4, byteorder="big")
                    sock.sendall(chunk_len + chunk)

                # Send terminal 0-length chunk
                sock.sendall(b"\x00\x00\x00\x00")

                response = sock.recv(1024).decode("utf-8", errors="replace").strip()
                if "FOUND" in response:
                    return False, f"ClamAV threat detected: {response}"
                return True, None
        except Exception as e:
            logger.error(f"ClamAV daemon connection failed ({self.host}:{self.port}): {e}")
            raise ScannerUnavailableError(
                f"ClamAV daemon connection failed at {self.host}:{self.port}: {e}"
            ) from e


class DefaultMalwareScanner:
    """Composite malware scanner combining deterministic heuristics with ClamAV daemon."""

    def __init__(self):
        self.heuristic_scanner = HeuristicSignatureScanner()
        self.clamav_scanner = ClamAVScanner()

    def scan_bytes(self, file_bytes: bytes, filename: str) -> tuple[bool, str | None]:
        # 1. First run deterministic signature/heuristic checks
        is_safe, reason = self.heuristic_scanner.scan_bytes(file_bytes, filename)
        if not is_safe:
            return False, reason

        # 2. Then invoke ClamAV daemon if enabled
        is_safe, reason = self.clamav_scanner.scan_bytes(file_bytes, filename)
        if not is_safe:
            return False, reason

        return True, None


class ScannerService:
    """Production-grade document validation and malware scanning service."""

    def __init__(self, db: Session, scanner: MalwareScanner | None = None):
        self.db = db
        self.scanner = scanner or DefaultMalwareScanner()
        self.storage = get_storage_provider()

    def scan_document(self, document_id: UUID) -> Document:
        """Executes real byte verification and malware scanning on a quarantined document.

        Lifecycle: QUARANTINED -> VALIDATING -> SCANNING -> SAFE / REJECTED
        """
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ResourceNotFoundError("Document not found")

        if document.deleted_at is not None:
            logger.warning(f"Skipping scan for soft-deleted document {document_id}")
            return document

        if document.security_status in (DocumentSecurityStatus.SAFE, DocumentSecurityStatus.REJECTED):
            return document

        auth_svc = AuthService(self.db)

        # 1. State transition to VALIDATING
        document.security_status = DocumentSecurityStatus.VALIDATING
        self.db.commit()
        auth_svc.log_audit_event(
            event_type="DOCUMENT_VALIDATION_STARTED",
            user_id=document.uploaded_by,
            metadata={"document_id": str(document.id), "filename": document.filename},
            action="document_mutation",
        )

        # 2. Retrieve bytes from private storage
        file_bytes = self.storage.get_object_bytes(document.storage_key)
        if file_bytes is None:
            document.security_status = DocumentSecurityStatus.REJECTED
            document.processing_error = "Storage object not found or empty"
            self.db.commit()
            auth_svc.log_audit_event(
                event_type="DOCUMENT_REJECTED",
                user_id=document.uploaded_by,
                metadata={"document_id": str(document.id), "reason": "Missing storage object"},
                action="document_mutation",
            )
            return document

        # 3. Content signature validation (magic bytes against declared MIME type)
        try:
            validate_file_magic_bytes(file_bytes, document.mime_type)
        except ValidationError as val_err:
            document.security_status = DocumentSecurityStatus.REJECTED
            document.processing_error = f"Content signature mismatch: {val_err}"
            self.db.commit()
            auth_svc.log_audit_event(
                event_type="DOCUMENT_REJECTED",
                user_id=document.uploaded_by,
                metadata={"document_id": str(document.id), "reason": str(val_err)},
                action="document_mutation",
            )
            return document

        # 4. State transition to SCANNING
        document.security_status = DocumentSecurityStatus.SCANNING
        self.db.commit()
        auth_svc.log_audit_event(
            event_type="DOCUMENT_SCANNING_STARTED",
            user_id=document.uploaded_by,
            metadata={"document_id": str(document.id)},
            action="document_mutation",
        )

        # 5. Execute malware scan
        try:
            is_safe, threat_reason = self.scanner.scan_bytes(file_bytes, document.filename)
        except ScannerUnavailableError as scan_err:
            document.security_status = DocumentSecurityStatus.QUARANTINED
            document.processing_error = (
                "Malware scanner service is temporarily unavailable. Document remains quarantined."
            )
            auth_svc.log_audit_event(
                event_type="DOCUMENT_SCAN_UNAVAILABLE",
                user_id=document.uploaded_by,
                metadata={"document_id": str(document.id), "error": str(scan_err)},
                action="document_mutation",
            )
            self.db.commit()
            self.db.refresh(document)
            raise

        if is_safe:
            document.security_status = DocumentSecurityStatus.SAFE
            document.processing_error = None
            action = "DOCUMENT_SAFE"
        else:
            document.security_status = DocumentSecurityStatus.REJECTED
            document.processing_error = threat_reason or "Malware detected"
            action = "DOCUMENT_REJECTED"

        self.db.commit()
        self.db.refresh(document)

        auth_svc.log_audit_event(
            event_type=action,
            user_id=document.uploaded_by,
            metadata={"document_id": str(document.id), "threat_reason": threat_reason},
            action="document_mutation",
        )

        # 6. If SAFE, enqueue background processing
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
                metadata={"document_id": str(document.id), "version": document.version},
                action="document_mutation",
            )

        return document

    def simulate_scan(self, document_id: UUID, is_safe: bool = True):
        """Simulates the async malware scanning process for backward compatibility with testing."""
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ResourceNotFoundError("Document not found")

        if document.deleted_at is not None:
            return

        if document.security_status in (DocumentSecurityStatus.SAFE, DocumentSecurityStatus.REJECTED):
            return

        valid_prior_states = (
            DocumentSecurityStatus.QUARANTINED,
            DocumentSecurityStatus.VALIDATING,
            DocumentSecurityStatus.SCANNING,
        )
        if document.security_status not in valid_prior_states:
            raise ValidationError(f"Invalid state transition from {document.security_status.name}")

        auth_svc = AuthService(self.db)

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

        if is_safe:
            job_svc = JobService(self.db)
            job_svc.enqueue_job(
                job_type=JobType.DOCUMENT_PROCESSING,
                payload={"document_id": str(document.id), "generate_embeddings": True},
                idempotency_key=f"doc_proc_{document.id}_v{document.version}",
                case_id=document.case_id,
                created_by_user_id=document.uploaded_by,
            )
