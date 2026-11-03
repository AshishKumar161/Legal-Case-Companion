import logging
import re
import socket
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    AuthorizationError,
    ResourceNotFoundError,
    ScannerUnavailableError,
    ValidationError,
)
from app.core.file_validation import validate_file_magic_bytes
from app.core.storage import get_storage_provider
from app.models.document import Document, DocumentSecurityStatus
from app.models.job import JobType
from app.models.user import User, UserRole
from app.domain.auth.auth_service import AuthService
from app.domain.jobs.job_service import JobService

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
        is_prod = getattr(settings, "ENVIRONMENT", "").lower() in ("production", "staging")
        if not self.host:
            if is_prod:
                logger.error("ClamAV daemon host is not configured in production environment!")
                raise ScannerUnavailableError(
                    "ClamAV daemon host is not configured. Production environment prohibits heuristic-only certification."
                )
            # ClamAV daemon host is not configured; pass through to secondary scanner in local dev/test
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

                # Read complete streaming response until null byte, newline, or EOF
                response_chunks: list[bytes] = []
                while True:
                    data = sock.recv(1024)
                    if not data:
                        break
                    response_chunks.append(data)
                    if b"\0" in data or b"\n" in data:
                        break

                raw_bytes = b"".join(response_chunks)
                if not raw_bytes:
                    raise ScannerUnavailableError(
                        f"ClamAV daemon returned empty or incomplete response for {filename}."
                    )

                response = raw_bytes.decode("utf-8", errors="replace").strip().strip("\0").strip()
                if not response:
                    raise ScannerUnavailableError(
                        f"ClamAV daemon returned blank response for {filename}."
                    )

                if "ERROR" in response:
                    logger.error(f"ClamAV daemon reported scan error for {filename}: {response}")
                    raise ScannerUnavailableError(f"ClamAV daemon scan error: {response}")

                if "FOUND" in response:
                    match = re.search(r":\s*(.+?)\s+FOUND", response)
                    threat = match.group(1) if match else response
                    return False, f"ClamAV threat detected: {threat}"

                if response == "stream: OK" or response.endswith(": OK") or response == "OK":
                    return True, None

                # Reject malformed or unexpected response format
                logger.error(f"Malformed or unexpected ClamAV response for {filename}: {response!r}")
                raise ScannerUnavailableError(
                    f"Malformed ClamAV response: expected ': OK' or 'FOUND', got {response!r}"
                )
        except socket.timeout as te:
            logger.error(f"ClamAV daemon timed out during scan of {filename} ({self.host}:{self.port}): {te}")
            raise ScannerUnavailableError(
                f"ClamAV daemon timed out after 10.0s scanning {filename} at {self.host}:{self.port}"
            ) from te
        except ScannerUnavailableError:
            raise
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
        is_prod = getattr(settings, "ENVIRONMENT", "").lower() in ("production", "staging")

        # 1. First run deterministic signature/heuristic checks
        is_safe, reason = self.heuristic_scanner.scan_bytes(file_bytes, filename)
        if not is_safe:
            return False, reason

        # 2. In production or staging, heuristic scanner must NOT independently certify arbitrary files
        if is_prod and not self.clamav_scanner.host:
            raise ScannerUnavailableError(
                "ClamAV daemon host is not configured in production environment. "
                "Heuristic scanning cannot independently certify files as malware-free."
            )

        # 3. Then invoke ClamAV daemon
        is_safe, reason = self.clamav_scanner.scan_bytes(file_bytes, filename)
        if not is_safe:
            return False, reason

        return True, None

    def is_clamav_available(self) -> bool:
        """Returns True if ClamAV daemon is configured and reachable."""
        if not self.clamav_scanner.host:
            return False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2.0)
                sock.connect((self.clamav_scanner.host, self.clamav_scanner.port))
                sock.sendall(b"zPING\0")
                resp = sock.recv(16)
                return b"PONG" in resp
        except Exception:
            return False


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
            current_attempts = 1
            if document.processing_error and "attempt " in document.processing_error:
                match = re.search(r"attempt (\d+)", document.processing_error)
                if match:
                    current_attempts = int(match.group(1)) + 1

            max_retries = getattr(settings, "MALWARE_SCAN_MAX_RETRIES", 3)
            document.security_status = DocumentSecurityStatus.QUARANTINED
            document.processing_error = (
                f"Malware scanner service is temporarily unavailable (attempt {current_attempts}/{max_retries}). "
                "Document remains quarantined."
            )
            auth_svc.log_audit_event(
                event_type="DOCUMENT_SCAN_UNAVAILABLE",
                user_id=document.uploaded_by,
                metadata={
                    "document_id": str(document.id),
                    "attempt": current_attempts,
                    "max_retries": max_retries,
                    "error": str(scan_err),
                },
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

    def retry_quarantined_documents(
        self,
        max_retries: int = 3,
        batch_size: int = 50,
    ) -> dict[str, int]:
        """Scans documents stuck in QUARANTINED state due to scanner unavailability.
        Implements bounded retry logic (max_retries) and failure monitoring.
        If max_retries is reached, marks the document as permanently failed quarantine
        for administrator audit and manual review.
        """
        auth_svc = AuthService(self.db)
        quarantined_docs = (
            self.db.query(Document)
            .filter(
                Document.security_status == DocumentSecurityStatus.QUARANTINED,
                Document.deleted_at.is_(None),
            )
            .order_by(Document.created_at.asc())
            .limit(batch_size)
            .all()
        )

        results = {
            "evaluated": len(quarantined_docs),
            "succeeded": 0,
            "failed_rejection": 0,
            "retry_failed": 0,
            "exhausted": 0,
            "still_quarantined": 0,
        }

        for doc in quarantined_docs:
            current_attempts = 0
            if doc.processing_error and "attempt " in doc.processing_error:
                match = re.search(r"attempt (\d+)", doc.processing_error)
                if match:
                    current_attempts = int(match.group(1))

            if current_attempts >= max_retries:
                results["exhausted"] += 1
                doc.processing_error = (
                    f"Quarantine scan retry limit reached ({current_attempts}/{max_retries}). "
                    "Document quarantined indefinitely pending manual administrator security review."
                )
                auth_svc.log_audit_event(
                    event_type="DOCUMENT_SCAN_RETRY_EXHAUSTED",
                    user_id=doc.uploaded_by,
                    metadata={
                        "document_id": str(doc.id),
                        "attempts": current_attempts,
                        "max_retries": max_retries,
                    },
                    action="document_mutation",
                )
                self.db.commit()
                continue

            try:
                scanned_doc = self.scan_document(doc.id)
                if scanned_doc.security_status == DocumentSecurityStatus.SAFE:
                    results["succeeded"] += 1
                elif scanned_doc.security_status == DocumentSecurityStatus.REJECTED:
                    results["failed_rejection"] += 1
                else:
                    results["still_quarantined"] += 1
            except ScannerUnavailableError as err:
                results["retry_failed"] += 1
                results["still_quarantined"] += 1
                logger.warning(
                    f"Retry failed for document {doc.id} (attempt {current_attempts + 1}/{max_retries}): {err}"
                )
            except Exception as e:
                logger.error(f"Unexpected error during quarantine retry for {doc.id}: {e}")
                results["retry_failed"] += 1
                results["still_quarantined"] += 1

        return results

    def reprocess_quarantined_document(
        self,
        document_id: UUID,
        admin_user: User,
        force: bool = False,
    ) -> Document:
        """
        Manually reprocesses a quarantined document after automatic retry exhaustion.
        Strictly requires ADMIN authorization and logs an authoritative audit event.
        Maintains fail-closed behavior: if scanning fails or scanner is unavailable,
        the document remains QUARANTINED and raises ScannerUnavailableError.
        """
        if admin_user.role != UserRole.ADMIN:
            raise AuthorizationError("Only administrators can manually reprocess quarantined documents.")

        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ResourceNotFoundError("Document not found")

        if document.security_status != DocumentSecurityStatus.QUARANTINED:
            raise ValidationError(
                f"Cannot reprocess document in state '{document.security_status.name}'. Only QUARANTINED documents can be reprocessed."
            )

        auth_svc = AuthService(self.db)
        auth_svc.log_audit_event(
            event_type="DOCUMENT_QUARANTINE_MANUALLY_REPROCESSED",
            user_id=admin_user.id,
            metadata={
                "document_id": str(document.id),
                "admin_id": str(admin_user.id),
                "force": force,
                "prior_error": document.processing_error,
            },
            action="document_mutation",
        )

        if force:
            document.processing_error = None
            self.db.commit()

        # Re-execute byte validation and malware scan (fail-closed)
        return self.scan_document(document.id)

