import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.authorization import (
    authorize_case_access,
    authorize_evidence_access,
    authorize_evidence_management,
)
from app.core.exceptions import (
    AppException,
    ResourceNotFoundError,
    ScannerUnavailableError,
    ValidationError,
)
from app.core.file_validation import (
    validate_file_magic_bytes,
    validate_filename_security,
)
from app.core.identifiers import generate_uuid7
from app.core.metrics import metrics_collector
from app.core.storage import get_storage_provider
from app.models.case import CaseParticipant, ParticipantStatus
from app.models.consultation import Consultation
from app.models.evidence import (
    Evidence,
    EvidenceAccessGrant,
    EvidenceCustodyAction,
    EvidenceCustodyEvent,
    EvidenceIntegrityStatus,
    EvidenceScanStatus,
    EvidenceStatus,
    EvidenceVersion,
)
from app.models.notification import NotificationType
from app.models.user import User, UserRole
from app.schemas.evidence import (
    EvidenceLegalHoldRequest,
    EvidenceRevokeRequest,
    EvidenceShareRequest,
    EvidenceUploadInitRequest,
    EvidenceVersionCreateRequest,
)
from app.services.auth_service import AuthService
from app.services.notification_service import NotificationService
from app.services.outbox_service import OutboxService
from app.services.scanner_service import DefaultMalwareScanner, MalwareScanner

logger = logging.getLogger(__name__)

MAX_EVIDENCE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


class EvidenceService:
    """Service providing high-security Evidence Locker operations, immutable versioning,

    cryptographic verification, unbroken chain of custody, and controlled sharing.
    """

    def __init__(self, db: Session, scanner: MalwareScanner | None = None):
        self.db = db
        self.storage = get_storage_provider()
        self.scanner = scanner or DefaultMalwareScanner()
        self.auth_service = AuthService(db)
        self.notification_service = NotificationService(db)

    def _record_custody_event(
        self,
        evidence_id: uuid.UUID,
        action: EvidenceCustodyAction,
        actor_user_id: uuid.UUID | None = None,
        version_id: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> EvidenceCustodyEvent:
        """Records an immutable chain-of-custody event linking to the previous chronological event."""
        last_event = (
            self.db.query(EvidenceCustodyEvent)
            .filter(EvidenceCustodyEvent.evidence_id == evidence_id)
            .order_by(desc(EvidenceCustodyEvent.timestamp))
            .first()
        )

        event = EvidenceCustodyEvent(
            id=generate_uuid7(),
            evidence_id=evidence_id,
            version_id=version_id,
            actor_user_id=actor_user_id,
            action=action,
            previous_event_id=last_event.id if last_event else None,
            event_metadata=metadata,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def init_upload(
        self,
        user: User,
        case_id: uuid.UUID,
        req: EvidenceUploadInitRequest,
    ) -> tuple[Evidence, EvidenceVersion, str]:
        """Initializes a secure staged evidence upload.

        Validates case access, file size, content characteristics, and generates
        a short-lived presigned upload URL.
        """
        authorize_case_access(self.db, user, case_id)

        # Sanitize filename
        safe_filename = validate_filename_security(req.original_filename)

        if req.size_bytes > MAX_EVIDENCE_SIZE_BYTES:
            raise ValidationError(
                f"Evidence file size exceeds maximum limit of {MAX_EVIDENCE_SIZE_BYTES // (1024 * 1024)}MB"
            )

        evidence_id = generate_uuid7()
        version_id = generate_uuid7()
        storage_key = f"cases/{case_id}/evidence/{evidence_id}/versions/{version_id}"

        evidence = Evidence(
            id=evidence_id,
            case_id=case_id,
            created_by_user_id=user.id,
            current_version_id=None,
            title=req.title,
            description=req.description,
            category=req.category,
            status=EvidenceStatus.UPLOADING,
            sensitivity=req.sensitivity,
            original_filename=safe_filename,
            retention_until=req.retention_until,
        )
        self.db.add(evidence)
        self.db.flush()

        version = EvidenceVersion(
            id=version_id,
            evidence_id=evidence_id,
            version_number=1,
            uploaded_by_user_id=user.id,
            storage_key=storage_key,
            original_filename=safe_filename,
            content_type=req.content_type,
            size_bytes=req.size_bytes,
            sha256="",
            scan_status=EvidenceScanStatus.PENDING,
            integrity_status=EvidenceIntegrityStatus.UNVERIFIED,
        )
        self.db.add(version)
        OutboxService.emit_event(
            db=self.db,
            event_type="EVIDENCE_UPLOADED",
            aggregate_type="evidence",
            aggregate_id=evidence.id,
            payload={
                "evidence_id": str(evidence.id),
                "version_id": str(version.id),
                "case_id": str(case_id),
                "original_filename": version.original_filename,
            },
        )
        self.db.commit()
        self.db.refresh(evidence)
        self.db.refresh(version)
        metrics_collector.record_evidence_operation("UPLOAD_INIT", "SUCCESS")

        upload_url = self.storage.generate_presigned_upload_url(
            object_key=storage_key,
            mime_type=req.content_type,
            expires_in=900,
        )

        return evidence, version, upload_url

    def complete_upload(
        self,
        user: User,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> Evidence:
        """Completes upload verification pipeline:

        1. Verifies bytes exist in private storage.
        2. Validates magic bytes against declared MIME type.
        3. Performs malware and threat scanning.
        4. Computes cryptographic SHA-256 digest.
        5. Atomically activates Evidence item.
        6. Appends unbroken chain of custody records.
        """
        evidence = (
            self.db.query(Evidence)
            .filter(
                Evidence.id == evidence_id,
                Evidence.case_id == case_id,
                Evidence.deleted_at.is_(None),
            )
            .first()
        )
        if not evidence:
            raise ResourceNotFoundError("Evidence not found")

        version = (
            self.db.query(EvidenceVersion)
            .filter(
                EvidenceVersion.id == version_id,
                EvidenceVersion.evidence_id == evidence_id,
            )
            .first()
        )
        if not version:
            raise ResourceNotFoundError("Evidence version not found")

        # 1. Retrieve bytes from private storage
        file_bytes = self.storage.get_object_bytes(version.storage_key)
        if file_bytes is None or len(file_bytes) == 0:
            version.scan_status = EvidenceScanStatus.FAILED
            version.scan_details = "Storage object not found or empty"
            evidence.status = EvidenceStatus.QUARANTINED
            self.db.commit()
            self._record_custody_event(
                evidence_id=evidence_id,
                version_id=version_id,
                actor_user_id=user.id,
                action=EvidenceCustodyAction.SCAN_FAILED,
                metadata={"error": "Missing or empty storage object"},
            )
            self.db.commit()
            raise ValidationError("Evidence storage object not found or empty")

        # 2. Magic bytes validation
        try:
            validate_file_magic_bytes(file_bytes, version.content_type)
        except ValidationError as e:
            version.scan_status = EvidenceScanStatus.FAILED
            version.scan_details = f"Magic bytes validation failed: {e}"
            evidence.status = EvidenceStatus.QUARANTINED
            self.db.commit()
            self._record_custody_event(
                evidence_id=evidence_id,
                version_id=version_id,
                actor_user_id=user.id,
                action=EvidenceCustodyAction.SCAN_FAILED,
                metadata={"error": str(e)},
            )
            self.db.commit()
            raise ValidationError(f"Content signature mismatch: {e}") from e

        # 3. Malware scanning with fail-closed security policy
        try:
            is_safe, threat_details = self.scanner.scan_bytes(file_bytes, version.original_filename)
        except Exception as scan_err:
            version.scan_status = EvidenceScanStatus.FAILED
            version.scan_details = f"Malware scanner failure: {scan_err}"
            evidence.status = EvidenceStatus.QUARANTINED
            self.db.commit()
            self._record_custody_event(
                evidence_id=evidence_id,
                version_id=version_id,
                actor_user_id=user.id,
                action=EvidenceCustodyAction.SCAN_FAILED,
                metadata={"error": f"Scanner failure: {scan_err}"},
            )
            self.db.commit()
            metrics_collector.record_evidence_operation("SCAN", "FAILED_SCANNER_ERROR")
            metrics_collector.record_dependency_failure("MALWARE_SCANNER")
            raise ScannerUnavailableError(f"Malware scanning service unavailable: {scan_err}") from scan_err

        if not is_safe:
            version.scan_status = EvidenceScanStatus.FAILED
            version.scan_details = threat_details or "Malware detected"
            evidence.status = EvidenceStatus.QUARANTINED
            self.db.commit()
            self._record_custody_event(
                evidence_id=evidence_id,
                version_id=version_id,
                actor_user_id=user.id,
                action=EvidenceCustodyAction.SCAN_FAILED,
                metadata={"threat": threat_details},
            )
            self.db.commit()
            metrics_collector.record_evidence_operation("SCAN", "REJECTED_MALWARE")
            raise ValidationError(f"Evidence rejected: {threat_details}")

        # 4. Cryptographic SHA-256 digest computation
        digest = hashlib.sha256(file_bytes).hexdigest()

        version.sha256 = digest
        version.size_bytes = len(file_bytes)
        version.scan_status = EvidenceScanStatus.PASSED
        version.scan_details = "Validation and malware scanning passed"
        version.integrity_status = EvidenceIntegrityStatus.VERIFIED_MATCH
        version.last_verified_at = datetime.now(UTC)

        evidence.status = EvidenceStatus.ACTIVE
        evidence.current_version_id = version.id

        # 5. Record custody chronology
        self._record_custody_event(
            evidence_id=evidence_id,
            version_id=version_id,
            actor_user_id=user.id,
            action=EvidenceCustodyAction.UPLOADED,
            metadata={"filename": version.original_filename, "size_bytes": len(file_bytes)},
        )
        self._record_custody_event(
            evidence_id=evidence_id,
            version_id=version_id,
            actor_user_id=user.id,
            action=EvidenceCustodyAction.SCAN_PASSED,
            metadata={"sha256": digest},
        )

        # 6. Transactional Outbox Event for activated evidence
        OutboxService.emit_event(
            db=self.db,
            event_type="EVIDENCE_ACTIVATED",
            aggregate_type="evidence",
            aggregate_id=evidence.id,
            payload={
                "evidence_id": str(evidence.id),
                "version_id": str(version.id),
                "case_id": str(case_id),
                "sha256": digest,
            },
        )

        self.db.commit()
        self.db.refresh(evidence)
        metrics_collector.record_evidence_operation("ACTIVATION", "SUCCESS")
        return evidence

    def create_version_init(
        self,
        user: User,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
        req: EvidenceVersionCreateRequest,
    ) -> tuple[EvidenceVersion, str]:
        """Initializes a new immutable evidence version (Version N+1)."""
        evidence = authorize_evidence_management(self.db, user, evidence_id)
        if evidence.case_id != case_id:
            raise ResourceNotFoundError("Evidence not found")

        safe_filename = validate_filename_security(req.original_filename)
        if req.size_bytes > MAX_EVIDENCE_SIZE_BYTES:
            raise ValidationError("Version file size exceeds maximum limit")

        latest_version = (
            self.db.query(EvidenceVersion)
            .filter(EvidenceVersion.evidence_id == evidence_id)
            .order_by(desc(EvidenceVersion.version_number))
            .first()
        )
        next_version_number = (latest_version.version_number + 1) if latest_version else 1

        version_id = generate_uuid7()
        storage_key = f"cases/{case_id}/evidence/{evidence_id}/versions/{version_id}"

        version = EvidenceVersion(
            id=version_id,
            evidence_id=evidence_id,
            version_number=next_version_number,
            uploaded_by_user_id=user.id,
            storage_key=storage_key,
            original_filename=safe_filename,
            content_type=req.content_type,
            size_bytes=req.size_bytes,
            sha256="",
            scan_status=EvidenceScanStatus.PENDING,
            integrity_status=EvidenceIntegrityStatus.UNVERIFIED,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)

        upload_url = self.storage.generate_presigned_upload_url(
            object_key=storage_key,
            mime_type=req.content_type,
            expires_in=900,
        )
        return version, upload_url

    def complete_version(
        self,
        user: User,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> Evidence:
        """Validates, scans, hashes, and promotes a new immutable version to current."""
        evidence = self.complete_upload(user, case_id, evidence_id, version_id)
        version = self.db.query(EvidenceVersion).filter(EvidenceVersion.id == version_id).first()
        if not version:
            raise ResourceNotFoundError("Evidence version not found")

        self._record_custody_event(
            evidence_id=evidence_id,
            version_id=version_id,
            actor_user_id=user.id,
            action=EvidenceCustodyAction.VERSION_CREATED,
            metadata={"version_number": version.version_number, "sha256": version.sha256},
        )
        self.db.commit()
        self.db.refresh(evidence)
        return evidence

    def verify_integrity(
        self,
        user: User,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
        version_id: uuid.UUID | None = None,
    ) -> tuple[EvidenceVersion, str, str, bool]:
        """Cryptographically verifies bytes in storage against the stored SHA-256 digest.

        Returns (version, recorded_sha256, computed_sha256, is_match).
        """
        evidence, _ = authorize_evidence_access(self.db, user, evidence_id, required_level="VIEW")
        if evidence.case_id != case_id:
            raise ResourceNotFoundError("Evidence not found")

        if version_id:
            version = (
                self.db.query(EvidenceVersion)
                .filter(
                    EvidenceVersion.id == version_id,
                    EvidenceVersion.evidence_id == evidence_id,
                )
                .first()
            )
            if not version:
                raise ResourceNotFoundError("Evidence version not found")
        else:
            version = evidence.current_version
            if not version:
                raise ResourceNotFoundError("No current version available")

        file_bytes = self.storage.get_object_bytes(version.storage_key)
        if file_bytes is None:
            version.integrity_status = EvidenceIntegrityStatus.TAMPER_DETECTED
            version.last_verified_at = datetime.now(UTC)
            self._record_custody_event(
                evidence_id=evidence_id,
                version_id=version.id,
                actor_user_id=user.id,
                action=EvidenceCustodyAction.INTEGRITY_FAILED,
                metadata={"error": "Storage object missing during verification"},
            )
            self.db.commit()
            return version, version.sha256, "", False

        computed_sha256 = hashlib.sha256(file_bytes).hexdigest()
        is_match = computed_sha256.lower() == version.sha256.lower()

        version.last_verified_at = datetime.now(UTC)
        if is_match:
            version.integrity_status = EvidenceIntegrityStatus.VERIFIED_MATCH
            self._record_custody_event(
                evidence_id=evidence_id,
                version_id=version.id,
                actor_user_id=user.id,
                action=EvidenceCustodyAction.INTEGRITY_VERIFIED,
                metadata={"sha256": computed_sha256},
            )
        else:
            version.integrity_status = EvidenceIntegrityStatus.TAMPER_DETECTED
            self._record_custody_event(
                evidence_id=evidence_id,
                version_id=version.id,
                actor_user_id=user.id,
                action=EvidenceCustodyAction.INTEGRITY_FAILED,
                metadata={"recorded_sha256": version.sha256, "computed_sha256": computed_sha256},
            )
            self.auth_service.log_audit_event(
                event_type="EVIDENCE_TAMPER_DETECTED",
                user_id=user.id,
                metadata={
                    "evidence_id": str(evidence_id),
                    "version_id": str(version.id),
                    "recorded": version.sha256,
                    "computed": computed_sha256,
                },
                action="evidence_integrity_compromised",
            )

        self.db.commit()
        return version, version.sha256, computed_sha256, is_match

    def share_evidence(
        self,
        user: User,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
        req: EvidenceShareRequest,
    ) -> EvidenceAccessGrant:
        """Creates or updates a controlled access grant.

        Enforces that the target user is an authorized case participant or assigned lawyer.
        """
        evidence = authorize_evidence_management(self.db, user, evidence_id)
        if evidence.case_id != case_id:
            raise ResourceNotFoundError("Evidence not found")

        # Verify target user exists
        target_user = self.db.query(User).filter(User.id == req.target_user_id).first()
        if not target_user:
            raise ValidationError("Target user not found")

        # Validate relationship: target user must be an active participant on the case
        is_case_participant = (
            self.db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.user_id == req.target_user_id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .first()
        )

        # Or target is a lawyer assigned via an associated consultation
        is_consultation_lawyer = (
            self.db.query(Consultation)
            .filter(
                Consultation.case_id == case_id,
                Consultation.lawyer.has(user_id=req.target_user_id),
            )
            .first()
        )

        if not is_case_participant and not is_consultation_lawyer and target_user.role != UserRole.ADMIN:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message="Cannot share evidence with a user who is not associated with this case",
            )

        grant = (
            self.db.query(EvidenceAccessGrant)
            .filter(
                EvidenceAccessGrant.evidence_id == evidence_id,
                EvidenceAccessGrant.grantee_user_id == req.target_user_id,
            )
            .first()
        )

        if grant:
            grant.access_level = req.access_level
            grant.expires_at = req.expires_at
            grant.revoked_at = None
            grant.revocation_reason = None
        else:
            grant = EvidenceAccessGrant(
                id=generate_uuid7(),
                evidence_id=evidence_id,
                grantee_user_id=req.target_user_id,
                granted_by_user_id=user.id,
                access_level=req.access_level,
                expires_at=req.expires_at,
            )
            self.db.add(grant)

        self._record_custody_event(
            evidence_id=evidence_id,
            actor_user_id=user.id,
            action=EvidenceCustodyAction.SHARED,
            metadata={
                "grantee_user_id": str(req.target_user_id),
                "access_level": str(req.access_level),
                "expires_at": req.expires_at.isoformat() if req.expires_at else None,
            },
        )

        self.notification_service.create_notification(
            user_id=req.target_user_id,
            type=NotificationType.DOCUMENT_READY,
            title="Evidence Shared With You",
            message=f"Access to evidence '{evidence.title}' has been granted to you.",
            case_id=case_id,
            metadata={"evidence_id": str(evidence_id)},
        )

        OutboxService.emit_event(
            db=self.db,
            event_type="EVIDENCE_SHARED",
            aggregate_type="evidence",
            aggregate_id=evidence_id,
            payload={
                "evidence_id": str(evidence_id),
                "case_id": str(case_id),
                "target_user_id": str(req.target_user_id),
                "access_level": str(req.access_level),
            },
        )

        self.db.commit()
        self.db.refresh(grant)
        metrics_collector.record_evidence_operation("SHARE", "SUCCESS")
        return grant

    def revoke_access(
        self,
        user: User,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
        req: EvidenceRevokeRequest,
    ) -> EvidenceAccessGrant:
        """Immediately revokes an evidence access grant."""
        evidence = authorize_evidence_management(self.db, user, evidence_id)
        if evidence.case_id != case_id:
            raise ResourceNotFoundError("Evidence not found")

        grant = (
            self.db.query(EvidenceAccessGrant)
            .filter(
                EvidenceAccessGrant.evidence_id == evidence_id,
                EvidenceAccessGrant.grantee_user_id == req.target_user_id,
                EvidenceAccessGrant.revoked_at.is_(None),
            )
            .first()
        )
        if not grant:
            raise ResourceNotFoundError("Active grant not found for target user")

        grant.revoked_at = datetime.now(UTC)
        grant.revocation_reason = req.reason or "Access revoked by manager"

        self._record_custody_event(
            evidence_id=evidence_id,
            actor_user_id=user.id,
            action=EvidenceCustodyAction.ACCESS_REVOKED,
            metadata={"revoked_user_id": str(req.target_user_id), "reason": grant.revocation_reason},
        )

        self.db.commit()
        self.db.refresh(grant)
        return grant

    def get_download_url(
        self,
        user: User,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
        version_id: uuid.UUID | None = None,
    ) -> tuple[str, str, str]:
        """Generates a short-lived (60s) presigned download URL after enforcing DOWNLOAD authorization.

        Returns (url, filename, content_type).
        """
        evidence, _ = authorize_evidence_access(self.db, user, evidence_id, required_level="DOWNLOAD")
        if evidence.case_id != case_id:
            raise ResourceNotFoundError("Evidence not found")

        if version_id:
            version = (
                self.db.query(EvidenceVersion)
                .filter(
                    EvidenceVersion.id == version_id,
                    EvidenceVersion.evidence_id == evidence_id,
                )
                .first()
            )
            if not version:
                raise ResourceNotFoundError("Evidence version not found")
        else:
            version = evidence.current_version
            if not version:
                raise ResourceNotFoundError("No active version available")

        if version.scan_status != EvidenceScanStatus.PASSED:
            raise ValidationError("Cannot download unverified or quarantined evidence")

        safe_filename = version.original_filename.replace('"', '').replace('\r', '').replace('\n', '')
        disposition = f'attachment; filename="{safe_filename}"'

        url = self.storage.generate_presigned_download_url(
            version.storage_key,
            expires_in=60,
            response_content_disposition=disposition,
            response_content_type=version.content_type or "application/octet-stream",
        )

        self._record_custody_event(
            evidence_id=evidence_id,
            version_id=version.id,
            actor_user_id=user.id,
            action=EvidenceCustodyAction.DOWNLOADED,
        )
        self.db.commit()

        return url, version.original_filename, version.content_type

    def get_view_url(
        self,
        user: User,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
        version_id: uuid.UUID | None = None,
    ) -> tuple[str, str, str]:
        """Generates a short-lived (60s) presigned preview URL with execution boundary controls."""
        evidence, _ = authorize_evidence_access(self.db, user, evidence_id, required_level="VIEW")
        if evidence.case_id != case_id:
            raise ResourceNotFoundError("Evidence not found")

        if version_id:
            version = (
                self.db.query(EvidenceVersion)
                .filter(
                    EvidenceVersion.id == version_id,
                    EvidenceVersion.evidence_id == evidence_id,
                )
                .first()
            )
            if not version:
                raise ResourceNotFoundError("Evidence version not found")
        else:
            version = evidence.current_version
            if not version:
                raise ResourceNotFoundError("No active version available")

        # Defense-in-depth: Only allow safe viewing formats inline. Unsafe/executable/scriptable formats force attachment.
        SAFE_INLINE_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/jpg"}
        safe_filename = version.original_filename.replace('"', '').replace('\r', '').replace('\n', '')

        if version.content_type in SAFE_INLINE_MIME_TYPES:
            disposition = f'inline; filename="{safe_filename}"'
            ctype = version.content_type
        else:
            disposition = f'attachment; filename="{safe_filename}"'
            ctype = "application/octet-stream"

        url = self.storage.generate_presigned_download_url(
            version.storage_key,
            expires_in=60,
            response_content_disposition=disposition,
            response_content_type=ctype,
        )

        self._record_custody_event(
            evidence_id=evidence_id,
            version_id=version.id,
            actor_user_id=user.id,
            action=EvidenceCustodyAction.VIEWED,
        )
        self.db.commit()

        return url, version.original_filename, version.content_type

    def set_legal_hold(
        self,
        user: User,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
        req: EvidenceLegalHoldRequest,
    ) -> Evidence:
        """Applies or removes technical legal hold retention controls."""
        evidence = authorize_evidence_management(self.db, user, evidence_id)
        if evidence.case_id != case_id:
            raise ResourceNotFoundError("Evidence not found")

        evidence.legal_hold = req.legal_hold
        evidence.legal_hold_reason = req.reason if req.legal_hold else None

        action = (
            EvidenceCustodyAction.LEGAL_HOLD_APPLIED
            if req.legal_hold
            else EvidenceCustodyAction.LEGAL_HOLD_REMOVED
        )
        self._record_custody_event(
            evidence_id=evidence_id,
            actor_user_id=user.id,
            action=action,
            metadata={"reason": req.reason},
        )
        self.db.commit()
        self.db.refresh(evidence)
        return evidence

    def delete_evidence(
        self,
        user: User,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
    ) -> None:
        """Controlled evidence soft deletion with legal hold and retention enforcement."""
        evidence = authorize_evidence_management(self.db, user, evidence_id)
        if evidence.case_id != case_id:
            raise ResourceNotFoundError("Evidence not found")

        if evidence.legal_hold:
            raise AppException(
                status_code=403,
                code="LEGAL_HOLD_ACTIVE",
                message="Evidence is under legal hold and cannot be deleted",
            )

        if evidence.retention_until:
            ret_until = (
                evidence.retention_until
                if evidence.retention_until.tzinfo
                else evidence.retention_until.replace(tzinfo=UTC)
            )
            if ret_until > datetime.now(UTC):
                raise AppException(
                    status_code=403,
                    code="RETENTION_ACTIVE",
                    message=f"Evidence is subject to active retention until {ret_until.isoformat()} and cannot be deleted",
                )

        evidence.status = EvidenceStatus.DELETED
        evidence.deleted_at = datetime.now(UTC)

        self._record_custody_event(
            evidence_id=evidence_id,
            actor_user_id=user.id,
            action=EvidenceCustodyAction.DELETED,
        )
        self.db.commit()

    def get_custody_chain(
        self,
        user: User,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
    ) -> list[EvidenceCustodyEvent]:
        """Retrieves chronological chain of custody events for provenance audit."""
        evidence, _ = authorize_evidence_access(self.db, user, evidence_id, required_level="VIEW")
        if evidence.case_id != case_id:
            raise ResourceNotFoundError("Evidence not found")

        events = (
            self.db.query(EvidenceCustodyEvent)
            .filter(EvidenceCustodyEvent.evidence_id == evidence_id)
            .order_by(EvidenceCustodyEvent.timestamp.asc())
            .all()
        )
        return events

    def reconcile_abandoned_uploads(self, hours_threshold: int = 2) -> int:
        """Finds evidence items stuck in UPLOADING state longer than threshold and marks them QUARANTINED."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours_threshold)
        stuck_items = (
            self.db.query(Evidence)
            .filter(
                Evidence.status == EvidenceStatus.UPLOADING,
                Evidence.created_at < cutoff,
                Evidence.deleted_at.is_(None),
            )
            .all()
        )
        reconciled_count = 0
        for ev in stuck_items:
            ev.status = EvidenceStatus.QUARANTINED
            self._record_custody_event(
                evidence_id=ev.id,
                action=EvidenceCustodyAction.SCAN_FAILED,
                metadata={"reason": f"Upload abandoned for > {hours_threshold} hours"},
            )
            reconciled_count += 1
        if reconciled_count > 0:
            self.db.commit()
            logger.info(f"Reconciled {reconciled_count} abandoned evidence upload(s).")
        return reconciled_count

    def reconcile_orphaned_evidence(self) -> dict[str, int]:
        """Detects DB records with missing S3 bytes (flagging tamper/loss) and reconciles storage consistency."""
        versions = (
            self.db.query(EvidenceVersion)
            .join(Evidence, Evidence.id == EvidenceVersion.evidence_id)
            .filter(Evidence.status == EvidenceStatus.ACTIVE, Evidence.deleted_at.is_(None))
            .all()
        )
        missing_storage_count = 0
        for ver in versions:
            bytes_data = self.storage.get_object_bytes(ver.storage_key)
            if bytes_data is None:
                missing_storage_count += 1
                ver.integrity_status = EvidenceIntegrityStatus.TAMPER_DETECTED
                self._record_custody_event(
                    evidence_id=ver.evidence_id,
                    version_id=ver.id,
                    action=EvidenceCustodyAction.INTEGRITY_FAILED,
                    metadata={"error": "Storage object missing from S3"},
                )
                metrics_collector.record_tamper_event()
        if missing_storage_count > 0:
            self.db.commit()
            logger.warning(f"Detected {missing_storage_count} active evidence record(s) missing from storage.")
        return {"missing_storage_objects": missing_storage_count}
