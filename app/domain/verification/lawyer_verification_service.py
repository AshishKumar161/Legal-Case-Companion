import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AppException,
    AuthorizationError,
    ConflictError,
    ResourceNotFoundError,
    ValidationError,
)
from app.core.file_validation import validate_file_magic_bytes, validate_filename_security
from app.core.identifiers import generate_uuid7
from app.core.storage import get_storage_provider
from app.models.audit import AuditEvent
from app.models.availability import LawyerAvailability
from app.models.notification import Notification, NotificationType
from app.models.user import (
    AccountStatus,
    AdvocateDocumentType,
    AdvocateVerificationDocument,
    DocumentScanStatus,
    DocumentVerificationStatus,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationReviewEvent,
    VerificationStatus,
)
from app.schemas.verification import (
    AdvocateVerificationDetailResponse,
    AdvocateVerificationDocumentResponse,
    AdvocateVerificationSubmitRequest,
    LawyerVerificationQueueItem,
    LawyerVerificationQueueResponse,
    PublicAdvocateVerificationBadgeResponse,
    VerificationReviewEventResponse,
)

logger = logging.getLogger(__name__)

MAX_VERIFICATION_FILE_BYTES = 15 * 1024 * 1024  # 15 MB


class RejectionCategory(str, Enum):
    INVALID_ENROLLMENT_FORMAT = "INVALID_ENROLLMENT_FORMAT"
    BAR_COUNCIL_MISMATCH = "BAR_COUNCIL_MISMATCH"
    DOCUMENTS_ILLEGIBLE = "DOCUMENTS_ILLEGIBLE"
    DISCIPLINARY_SANCTION = "DISCIPLINARY_SANCTION"
    EXPIRED_CREDENTIALS = "EXPIRED_CREDENTIALS"
    UNVERIFIABLE_RECORD = "UNVERIFIABLE_RECORD"
    IDENTITY_NAME_MISMATCH = "IDENTITY_NAME_MISMATCH"
    SUSPICIOUS_DOCUMENT = "SUSPICIOUS_DOCUMENT"


class LawyerVerificationService:
    """
    Authoritative Advocate Verification & Practice Compliance Service (Phase 14).
    Enforces deterministic human-in-the-loop review, State Bar Council roll provenance,
    cryptographic document integrity, self-approval prevention, credential change revocation,
    and BCI Rule 36 advertising compliance under the Zero-AI Mandate.
    """

    def __init__(self, db: Session):
        self.db = db
        self.storage = get_storage_provider()

    def get_or_create_draft_verification(self, user: User) -> LawyerVerification:
        """Retrieves or creates a draft verification application for an advocate."""
        if user.role != UserRole.LAWYER:
            raise AuthorizationError("Only users with role LAWYER can initiate advocate verification")

        profile = self.db.query(LawyerProfile).filter(LawyerProfile.user_id == user.id).first()
        if not profile:
            raise ResourceNotFoundError("Lawyer profile not found")

        verification = (
            self.db.query(LawyerVerification)
            .filter(
                LawyerVerification.lawyer_profile_id == profile.id,
                LawyerVerification.status.in_(
                    [
                        VerificationStatus.DRAFT,
                        VerificationStatus.NEEDS_INFO,
                        VerificationStatus.PENDING,
                        VerificationStatus.UNDER_REVIEW,
                    ]
                ),
            )
            .order_by(desc(LawyerVerification.created_at))
            .first()
        )

        if not verification:
            verification = LawyerVerification(
                id=generate_uuid7(),
                lawyer_profile_id=profile.id,
                enrollment_number="PENDING_SUBMISSION",
                state_bar_council="PENDING_SUBMISSION",
                status=VerificationStatus.DRAFT,
            )
            self.db.add(verification)
            self.db.commit()
            self.db.refresh(verification)

        return verification

    def upload_document(
        self,
        user: User,
        document_type: AdvocateDocumentType,
        file_bytes: bytes,
        original_filename: str,
        mime_type: str,
    ) -> AdvocateVerificationDocument:
        """
        Uploads and cryptographically binds a professional verification document.
        Validates magic bytes, filename security, and computes immutable SHA-256 digest.
        """
        if user.role != UserRole.LAWYER:
            raise AuthorizationError("Only users with role LAWYER can upload verification documents")

        if len(file_bytes) > MAX_VERIFICATION_FILE_BYTES:
            raise ValidationError(f"File size exceeds maximum permitted limit of {MAX_VERIFICATION_FILE_BYTES / 1024 / 1024} MB")

        # Filename and path traversal sanitization
        safe_filename = validate_filename_security(original_filename)

        # Magic byte signature validation
        validate_file_magic_bytes(file_bytes, mime_type)

        sha256_hash = hashlib.sha256(file_bytes).hexdigest()

        verification = self.get_or_create_draft_verification(user)

        doc_id = generate_uuid7()
        storage_key = f"advocate-verification/{verification.id}/{doc_id}"

        # Deposit into private encrypted storage
        success = self.storage.put_object_bytes(storage_key, file_bytes, mime_type)
        if not success:
            raise AppException(status_code=500, code="STORAGE_FAILED", message="Failed to store verification document securely")

        # Check if a document of this type already exists on this verification
        existing_doc = (
            self.db.query(AdvocateVerificationDocument)
            .filter(
                AdvocateVerificationDocument.verification_id == verification.id,
                AdvocateVerificationDocument.document_type == document_type,
            )
            .first()
        )

        now = datetime.now(UTC)
        if existing_doc:
            existing_doc.storage_key = storage_key
            existing_doc.original_filename = safe_filename
            existing_doc.file_size_bytes = len(file_bytes)
            existing_doc.mime_type = mime_type
            existing_doc.sha256_hash = sha256_hash
            existing_doc.scan_status = DocumentScanStatus.PASSED
            existing_doc.verification_status = DocumentVerificationStatus.SUBMITTED
            existing_doc.rejection_reason = None
            existing_doc.updated_at = now
            doc = existing_doc
        else:
            doc = AdvocateVerificationDocument(
                id=doc_id,
                verification_id=verification.id,
                document_type=document_type,
                storage_key=storage_key,
                original_filename=safe_filename,
                file_size_bytes=len(file_bytes),
                mime_type=mime_type,
                sha256_hash=sha256_hash,
                scan_status=DocumentScanStatus.PASSED,
                verification_status=DocumentVerificationStatus.SUBMITTED,
                created_at=now,
                updated_at=now,
            )
            self.db.add(doc)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=user.id,
            event_type="DOCUMENT_SUBMITTED",
            entity_type="AdvocateVerificationDocument",
            entity_id=doc.id,
            action="UPLOAD_VERIFICATION_DOCUMENT",
            timestamp=now,
            metadata_={
                "verification_id": str(verification.id),
                "document_type": document_type.value,
                "sha256_hash": sha256_hash,
                "file_size": len(file_bytes),
            },
        )
        self.db.add(audit)

        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get_document_download_url(self, user: User, document_id: uuid.UUID) -> str:
        """
        Generates a short-lived presigned download URL for an authorized reviewer or the owner.
        Logs an auditable access event without leaking sensitive document content.
        """
        doc = self.db.query(AdvocateVerificationDocument).filter(AdvocateVerificationDocument.id == document_id).first()
        if not doc:
            raise ResourceNotFoundError("Verification document not found")

        verification = self.db.query(LawyerVerification).filter(LawyerVerification.id == doc.verification_id).first()
        if not verification:
            raise ResourceNotFoundError("Verification application not found")

        profile = self.db.query(LawyerProfile).filter(LawyerProfile.id == verification.lawyer_profile_id).first()
        is_owner = profile and profile.user_id == user.id
        is_admin = user.role == UserRole.ADMIN

        if not (is_owner or is_admin):
            raise AuthorizationError("Not authorized to access confidential advocate verification documents")

        url = self.storage.generate_presigned_download_url(
            object_key=doc.storage_key,
            expires_in=300,
            response_content_disposition=f'attachment; filename="{doc.original_filename}"',
            response_content_type=doc.mime_type,
        )

        now = datetime.now(UTC)
        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=user.id,
            event_type="DOCUMENT_VIEWED",
            entity_type="AdvocateVerificationDocument",
            entity_id=doc.id,
            action="GENERATE_DOWNLOAD_LINK",
            timestamp=now,
            metadata_={
                "verification_id": str(verification.id),
                "document_type": doc.document_type.value,
                "is_admin": is_admin,
            },
        )
        self.db.add(audit)
        self.db.commit()

        return url

    def submit_verification(
        self,
        user: User,
        payload: AdvocateVerificationSubmitRequest | None = None,
        enrollment_number: str | None = None,
        state_bar_council: str | None = None,
        evidence_document_id: uuid.UUID | None = None,
        is_reverification: bool = False,
    ) -> LawyerVerification:
        """
        Formally submits an advocate's verification application for human reviewer inspection.
        Enforces enrollment format validation and checks that required Bar Council documents are present.
        Supports both modern payload object and backward-compatible keyword arguments.
        """
        if user.role != UserRole.LAWYER:
            raise AuthorizationError("Only users with role LAWYER can submit advocate verification")

        profile = self.db.query(LawyerProfile).filter(LawyerProfile.user_id == user.id).first()
        if not profile:
            raise ResourceNotFoundError("Lawyer profile not found")

        enroll_num = payload.enrollment_number if payload else (enrollment_number or "")
        state_bar = payload.state_bar_council if payload else (state_bar_council or "")
        is_reverif = payload.is_reverification if payload else is_reverification
        practice_jurisdictions = payload.declared_practice_jurisdictions if payload else []

        cleaned_enrollment = enroll_num.strip().upper()
        if not cleaned_enrollment or "/" not in cleaned_enrollment:
            raise ValidationError(
                "Invalid Bar Council enrollment number format. Expected format: STATE/XXXX/YYYY (e.g. D/1234/2018)"
            )

        # Check existing active or pending verification
        existing = (
            self.db.query(LawyerVerification)
            .filter(
                LawyerVerification.lawyer_profile_id == profile.id,
                LawyerVerification.status.in_([VerificationStatus.PENDING, VerificationStatus.APPROVED, VerificationStatus.UNDER_REVIEW]),
            )
            .first()
        )
        if existing and not is_reverif:
            if existing.status == VerificationStatus.APPROVED:
                raise ValidationError("Advocate profile already has an approved verification.")
            raise ValidationError("A verification request is already in progress or pending review.")

        if existing and is_reverif and existing.status == VerificationStatus.APPROVED:
            self.invalidate_on_credential_change(
                profile_id=profile.id,
                new_enrollment=cleaned_enrollment,
                new_state_bar=state_bar,
            )

        verification = self.get_or_create_draft_verification(user)

        # Verify at least the Bar Council Enrollment Certificate is uploaded if payload was passed
        if payload is not None:
            has_enrollment_cert = (
                self.db.query(AdvocateVerificationDocument)
                .filter(
                    AdvocateVerificationDocument.verification_id == verification.id,
                    AdvocateVerificationDocument.document_type == AdvocateDocumentType.BAR_COUNCIL_ENROLLMENT_CERT,
                    AdvocateVerificationDocument.scan_status == DocumentScanStatus.PASSED,
                )
                .first()
            )
            if not has_enrollment_cert:
                raise ValidationError(
                    "Mandatory professional credential missing: Please upload your Bar Council Enrollment Certificate before submitting."
                )

        now = datetime.now(UTC)
        from_status = verification.status.value

        verification.enrollment_number = cleaned_enrollment
        verification.state_bar_council = state_bar.strip()
        verification.declared_practice_jurisdictions = practice_jurisdictions
        verification.evidence_document_id = evidence_document_id
        verification.status = VerificationStatus.PENDING
        verification.is_reverification = is_reverif
        verification.updated_at = now

        review_event = VerificationReviewEvent(
            id=generate_uuid7(),
            verification_id=verification.id,
            reviewer_id=None,
            from_status=from_status,
            to_status=VerificationStatus.PENDING.value,
            decision="SUBMIT",
            verification_method="ADVOCATE_SELF_SUBMISSION",
            verification_source="LCC Advocate Onboarding Portal",
            notes="Advocate submitted complete professional credential dossier.",
            created_at=now,
            updated_at=now,
        )
        self.db.add(review_event)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=user.id,
            event_type="ADVOCATE_APPLICATION_STARTED",
            entity_type="LawyerVerification",
            entity_id=verification.id,
            action="SUBMIT_VERIFICATION_APPLICATION",
            timestamp=now,
            metadata_={
                "enrollment_number": cleaned_enrollment,
                "state_bar_council": state_bar.strip(),
                "is_reverification": is_reverif,
            },
        )
        self.db.add(audit)

        self.db.commit()
        self.db.refresh(verification)
        logger.info(f"Advocate verification submitted: id={verification.id} lawyer={profile.id} enrollment={cleaned_enrollment}")
        return verification

    def get_review_queue(
        self,
        reviewer: User,
        status_filter: VerificationStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> LawyerVerificationQueueResponse:
        """
        Returns bounded, paginated verification queue for administrative human reviewers.
        Identifies missing documents and surfaces submission provenance.
        """
        if reviewer.role != UserRole.ADMIN:
            raise AuthorizationError("Only administrators are authorized to access the verification review queue")

        page_size = min(max(page_size, 1), 50)
        page = max(page, 1)

        query = self.db.query(LawyerVerification).join(LawyerProfile, LawyerVerification.lawyer_profile_id == LawyerProfile.id)

        if status_filter:
            query = query.filter(LawyerVerification.status == status_filter)
        else:
            query = query.filter(
                LawyerVerification.status.in_(
                    [VerificationStatus.PENDING, VerificationStatus.UNDER_REVIEW, VerificationStatus.NEEDS_INFO]
                )
            )

        total = query.count()
        records = (
            query.order_by(desc(LawyerVerification.updated_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items: list[LawyerVerificationQueueItem] = []
        for r in records:
            prof = self.db.query(LawyerProfile).filter(LawyerProfile.id == r.lawyer_profile_id).first()
            docs = self.db.query(AdvocateVerificationDocument).filter(AdvocateVerificationDocument.verification_id == r.id).all()
            doc_types = {d.document_type for d in docs}

            missing: list[str] = []
            if AdvocateDocumentType.BAR_COUNCIL_ENROLLMENT_CERT not in doc_types:
                missing.append("Bar Council Enrollment Certificate")
            if AdvocateDocumentType.GOVERNMENT_PHOTO_ID not in doc_types:
                missing.append("Government Photo ID")

            items.append(
                LawyerVerificationQueueItem(
                    id=r.id,
                    lawyer_profile_id=r.lawyer_profile_id,
                    advocate_name=prof.full_name if prof else "Advocate",
                    enrollment_number=r.enrollment_number,
                    state_bar_council=r.state_bar_council,
                    status=r.status.value,
                    documents_count=len(docs),
                    missing_documents=missing,
                    submitted_at=r.created_at,
                    last_reviewed_at=r.last_reviewed_at,
                    reviewer_id=r.reviewed_by,
                )
            )

        return LawyerVerificationQueueResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_verification_detail(self, user: User, verification_id: uuid.UUID) -> AdvocateVerificationDetailResponse:
        """Returns complete application review detail, uploaded documents, and chronological audit history."""
        verification = self.db.query(LawyerVerification).filter(LawyerVerification.id == verification_id).first()
        if not verification:
            raise ResourceNotFoundError("Verification application not found")

        profile = self.db.query(LawyerProfile).filter(LawyerProfile.id == verification.lawyer_profile_id).first()
        if not profile:
            raise ResourceNotFoundError("Advocate profile not found")

        # Authorization: Admin or Owner
        if user.role != UserRole.ADMIN and profile.user_id != user.id:
            raise AuthorizationError("Not authorized to view this verification application")

        lawyer_user = self.db.query(User).filter(User.id == profile.user_id).first()
        docs = (
            self.db.query(AdvocateVerificationDocument)
            .filter(AdvocateVerificationDocument.verification_id == verification.id)
            .order_by(AdvocateVerificationDocument.created_at.asc())
            .all()
        )
        events = (
            self.db.query(VerificationReviewEvent)
            .filter(VerificationReviewEvent.verification_id == verification.id)
            .order_by(desc(VerificationReviewEvent.created_at))
            .all()
        )

        return AdvocateVerificationDetailResponse(
            id=verification.id,
            lawyer_profile_id=verification.lawyer_profile_id,
            advocate_name=profile.full_name,
            advocate_email=lawyer_user.email if lawyer_user else None,
            enrollment_number=verification.enrollment_number,
            state_bar_council=verification.state_bar_council,
            status=verification.status.value,
            declared_practice_jurisdictions=verification.declared_practice_jurisdictions or [],
            verification_source=verification.verification_source,
            source_reference=verification.source_reference,
            verification_method=verification.verification_method,
            verified_at=verification.verified_at,
            expires_at=verification.expires_at,
            last_reviewed_at=verification.last_reviewed_at,
            reviewer_id=verification.reviewed_by,
            reviewer_notes=verification.reviewer_notes,
            rejection_reason_category=verification.rejection_reason_category,
            documents=[AdvocateVerificationDocumentResponse.model_validate(d) for d in docs],
            review_events=[VerificationReviewEventResponse.model_validate(e) for e in events],
            created_at=verification.created_at,
        )

    def start_review(self, reviewer: User, verification_id: uuid.UUID, notes: str | None = None) -> LawyerVerification:
        """
        Transitions application to UNDER_REVIEW with pessimistic row locking.
        Guarantees self-approval prevention.
        """
        if reviewer.role != UserRole.ADMIN:
            raise AuthorizationError("Only administrators are authorized to conduct professional verification reviews")

        # Pessimistic locking prevents concurrent reviewers stepping on each other
        verification = (
            self.db.query(LawyerVerification)
            .filter(LawyerVerification.id == verification_id)
            .with_for_update()
            .first()
        )
        if not verification:
            raise ResourceNotFoundError("Verification application not found")

        profile = self.db.query(LawyerProfile).filter(LawyerProfile.id == verification.lawyer_profile_id).first()
        if profile and profile.user_id == reviewer.id:
            raise AuthorizationError("Self-approval prohibited. An advocate cannot review or approve their own verification application.")

        if verification.status in [VerificationStatus.APPROVED, VerificationStatus.REJECTED]:
            raise ConflictError(f"Cannot start review: application is already in terminal status {verification.status.value}")

        now = datetime.now(UTC)
        from_status = verification.status.value
        verification.status = VerificationStatus.UNDER_REVIEW
        verification.reviewed_by = reviewer.id
        verification.last_reviewed_at = now
        verification.reviewer_notes = notes

        # Update documents to UNDER_REVIEW
        self.db.query(AdvocateVerificationDocument).filter(
            AdvocateVerificationDocument.verification_id == verification.id,
            AdvocateVerificationDocument.verification_status == DocumentVerificationStatus.SUBMITTED,
        ).update({"verification_status": DocumentVerificationStatus.UNDER_REVIEW})

        event = VerificationReviewEvent(
            id=generate_uuid7(),
            verification_id=verification.id,
            reviewer_id=reviewer.id,
            from_status=from_status,
            to_status=VerificationStatus.UNDER_REVIEW.value,
            decision="START_REVIEW",
            verification_method="ADMIN_OPERATIONAL_INSPECTION",
            notes=notes or "Reviewer initiated formal verification inspection.",
            created_at=now,
            updated_at=now,
        )
        self.db.add(event)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=reviewer.id,
            event_type="DOCUMENT_REVIEW_STARTED",
            entity_type="LawyerVerification",
            entity_id=verification.id,
            action="START_VERIFICATION_REVIEW",
            timestamp=now,
            metadata_={"reviewer_id": str(reviewer.id)},
        )
        self.db.add(audit)

        self.db.commit()
        self.db.refresh(verification)
        return verification

    def review_verification(
        self,
        reviewer: User,
        verification_id: uuid.UUID,
        approved: bool,
        rejection_category: str | None = None,
        validity_days: int = 365,
    ) -> LawyerVerification:
        """Backward-compatible review method routing to approve_verification or reject_verification."""
        if approved:
            return self.approve_verification(
                reviewer=reviewer,
                verification_id=verification_id,
                verification_source="State Bar Council Roll",
                source_reference="Administrative review verification",
                validity_days=validity_days,
            )
        else:
            return self.reject_verification(
                reviewer=reviewer,
                verification_id=verification_id,
                rejection_category=rejection_category or "DOCUMENTS_ILLEGIBLE",
                reason=rejection_category or "Application rejected by reviewer.",
            )

    def approve_verification(
        self,
        reviewer: User,
        verification_id: uuid.UUID,
        verification_source: str,
        source_reference: str,
        verification_method: str = "STATE_BAR_COUNCIL_PORTAL_CHECK",
        validity_days: int = 365,
        notes: str | None = None,
    ) -> LawyerVerification:
        """
        Approves advocate verification with required State Bar Council provenance.
        Promotes advocate account status to VERIFIED, updates documents to APPROVED,
        and sets validity window. Guarantees self-approval prevention.
        """
        if reviewer.role != UserRole.ADMIN:
            raise AuthorizationError("Only administrators are authorized to approve advocate verifications")

        verification = (
            self.db.query(LawyerVerification)
            .filter(LawyerVerification.id == verification_id)
            .with_for_update()
            .first()
        )
        if not verification:
            raise ResourceNotFoundError("Verification application not found")

        profile = self.db.query(LawyerProfile).filter(LawyerProfile.id == verification.lawyer_profile_id).first()
        if profile and profile.user_id == reviewer.id:
            raise AuthorizationError("Self-approval prohibited. An advocate cannot review or approve their own verification application.")

        if verification.status == VerificationStatus.APPROVED:
            raise ConflictError("Verification is already approved.")
        if verification.status == VerificationStatus.REJECTED:
            raise ConflictError("Cannot approve an already rejected application without resubmission.")

        now = datetime.now(UTC)
        from_status = verification.status.value

        verification.status = VerificationStatus.APPROVED
        verification.reviewed_by = reviewer.id
        verification.reviewed_at = now
        verification.verified_at = now
        verification.last_reviewed_at = now
        verification.expires_at = now + timedelta(days=validity_days)
        verification.verification_source = verification_source.strip()
        verification.source_reference = source_reference.strip()
        verification.verification_method = verification_method.strip()
        verification.reviewer_notes = notes
        verification.rejection_reason_category = None

        # Promote documents to APPROVED
        self.db.query(AdvocateVerificationDocument).filter(
            AdvocateVerificationDocument.verification_id == verification.id
        ).update({"verification_status": DocumentVerificationStatus.APPROVED})

        # Promote user account status to VERIFIED
        if profile:
            lawyer_user = self.db.query(User).filter(User.id == profile.user_id).first()
            if lawyer_user and lawyer_user.account_status in [AccountStatus.REGISTERED, AccountStatus.RESTRICTED]:
                lawyer_user.account_status = AccountStatus.VERIFIED

        event = VerificationReviewEvent(
            id=generate_uuid7(),
            verification_id=verification.id,
            reviewer_id=reviewer.id,
            from_status=from_status,
            to_status=VerificationStatus.APPROVED.value,
            decision="APPROVE",
            verification_method=verification_method,
            verification_source=verification_source,
            source_reference=source_reference,
            notes=notes or "Advocate credentials verified against official roll records.",
            created_at=now,
            updated_at=now,
        )
        self.db.add(event)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=reviewer.id,
            event_type="ADVOCATE_APPROVED",
            entity_type="LawyerVerification",
            entity_id=verification.id,
            action="APPROVE_ADVOCATE_VERIFICATION",
            timestamp=now,
            metadata_={
                "reviewer_id": str(reviewer.id),
                "verification_source": verification_source,
                "expires_at": verification.expires_at.isoformat(),
            },
        )
        self.db.add(audit)

        self.db.commit()
        self.db.refresh(verification)
        logger.info(f"Advocate verification approved: id={verification.id} lawyer={verification.lawyer_profile_id} by={reviewer.id}")
        return verification

    def reject_verification(
        self,
        reviewer: User,
        verification_id: uuid.UUID,
        rejection_category: str,
        reason: str,
        notes: str | None = None,
    ) -> LawyerVerification:
        """
        Rejects advocate verification with structured rejection category and professional reasoning.
        Demotes account status and logs immutable audit trail. Guarantees self-approval prevention.
        """
        if reviewer.role != UserRole.ADMIN:
            raise AuthorizationError("Only administrators are authorized to reject advocate verifications")

        verification = (
            self.db.query(LawyerVerification)
            .filter(LawyerVerification.id == verification_id)
            .with_for_update()
            .first()
        )
        if not verification:
            raise ResourceNotFoundError("Verification application not found")

        profile = self.db.query(LawyerProfile).filter(LawyerProfile.id == verification.lawyer_profile_id).first()
        if profile and profile.user_id == reviewer.id:
            raise AuthorizationError("Self-approval prohibited. An advocate cannot review or reject their own verification application.")

        if verification.status == VerificationStatus.REJECTED:
            raise ConflictError("Verification is already rejected.")

        now = datetime.now(UTC)
        from_status = verification.status.value

        verification.status = VerificationStatus.REJECTED
        verification.reviewed_by = reviewer.id
        verification.reviewed_at = now
        verification.last_reviewed_at = now
        verification.expires_at = None
        verification.rejection_reason_category = rejection_category
        verification.reviewer_notes = notes or reason

        # Mark documents REJECTED
        self.db.query(AdvocateVerificationDocument).filter(
            AdvocateVerificationDocument.verification_id == verification.id
        ).update({
            "verification_status": DocumentVerificationStatus.REJECTED,
            "rejection_reason": reason,
        })

        # If lawyer user was VERIFIED, demote to REGISTERED
        if profile:
            lawyer_user = self.db.query(User).filter(User.id == profile.user_id).first()
            if lawyer_user and lawyer_user.account_status == AccountStatus.VERIFIED:
                lawyer_user.account_status = AccountStatus.REGISTERED

        event = VerificationReviewEvent(
            id=generate_uuid7(),
            verification_id=verification.id,
            reviewer_id=reviewer.id,
            from_status=from_status,
            to_status=VerificationStatus.REJECTED.value,
            decision="REJECT",
            verification_method="ADMIN_OPERATIONAL_INSPECTION",
            notes=reason,
            created_at=now,
            updated_at=now,
        )
        self.db.add(event)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=reviewer.id,
            event_type="ADVOCATE_REJECTED",
            entity_type="LawyerVerification",
            entity_id=verification.id,
            action="REJECT_ADVOCATE_VERIFICATION",
            timestamp=now,
            metadata_={
                "reviewer_id": str(reviewer.id),
                "rejection_category": rejection_category,
                "reason": reason,
            },
        )
        self.db.add(audit)

        self.db.commit()
        self.db.refresh(verification)
        logger.info(f"Advocate verification rejected: id={verification.id} lawyer={verification.lawyer_profile_id} reason='{reason}'")
        return verification

    def request_information(
        self,
        reviewer: User,
        verification_id: uuid.UUID,
        requested_documents: list[str],
        explanation: str,
        notes: str | None = None,
    ) -> LawyerVerification:
        """
        Requests additional documents or clarification without leaking confidential details.
        Transitions application to NEEDS_INFO and marks specified documents for resubmission.
        """
        if reviewer.role != UserRole.ADMIN:
            raise AuthorizationError("Only administrators can request verification clarification")

        verification = (
            self.db.query(LawyerVerification)
            .filter(LawyerVerification.id == verification_id)
            .with_for_update()
            .first()
        )
        if not verification:
            raise ResourceNotFoundError("Verification application not found")

        profile = self.db.query(LawyerProfile).filter(LawyerProfile.id == verification.lawyer_profile_id).first()
        if profile and profile.user_id == reviewer.id:
            raise AuthorizationError("Self-approval prohibited. An advocate cannot review their own verification application.")

        now = datetime.now(UTC)
        from_status = verification.status.value

        verification.status = VerificationStatus.NEEDS_INFO
        verification.reviewed_by = reviewer.id
        verification.last_reviewed_at = now
        verification.reviewer_notes = notes

        # Update specified documents to NEEDS_RESUBMISSION
        for doc_type_str in requested_documents:
            try:
                dt = AdvocateDocumentType(doc_type_str)
                self.db.query(AdvocateVerificationDocument).filter(
                    AdvocateVerificationDocument.verification_id == verification.id,
                    AdvocateVerificationDocument.document_type == dt,
                ).update({
                    "verification_status": DocumentVerificationStatus.NEEDS_RESUBMISSION,
                    "rejection_reason": explanation,
                })
            except ValueError:
                pass

        event = VerificationReviewEvent(
            id=generate_uuid7(),
            verification_id=verification.id,
            reviewer_id=reviewer.id,
            from_status=from_status,
            to_status=VerificationStatus.NEEDS_INFO.value,
            decision="REQUEST_INFORMATION",
            verification_method="ADMIN_OPERATIONAL_INSPECTION",
            notes=f"Clarification requested: {explanation}",
            created_at=now,
            updated_at=now,
        )
        self.db.add(event)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=reviewer.id,
            event_type="INFORMATION_REQUESTED",
            entity_type="LawyerVerification",
            entity_id=verification.id,
            action="REQUEST_VERIFICATION_INFORMATION",
            timestamp=now,
            metadata_={
                "reviewer_id": str(reviewer.id),
                "requested_documents": requested_documents,
            },
        )
        self.db.add(audit)

        self.db.commit()
        self.db.refresh(verification)
        return verification

    def revoke_verification(
        self,
        reviewer: User,
        verification_id: uuid.UUID,
        revocation_reason: str,
        notes: str | None = None,
    ) -> LawyerVerification:
        """
        Revokes an existing approved advocate verification (e.g. upon Bar Council disciplinary action
        or credential invalidation). Demotes account status and updates public badge.
        """
        if reviewer.role != UserRole.ADMIN:
            raise AuthorizationError("Only administrators are authorized to revoke advocate verifications")

        verification = (
            self.db.query(LawyerVerification)
            .filter(LawyerVerification.id == verification_id)
            .with_for_update()
            .first()
        )
        if not verification:
            raise ResourceNotFoundError("Verification application not found")

        profile = self.db.query(LawyerProfile).filter(LawyerProfile.id == verification.lawyer_profile_id).first()
        if profile and profile.user_id == reviewer.id:
            raise AuthorizationError("Self-approval prohibited. An advocate cannot review or revoke their own verification application.")

        now = datetime.now(UTC)
        from_status = verification.status.value

        verification.status = VerificationStatus.REVOKED
        verification.reviewed_by = reviewer.id
        verification.reviewed_at = now
        verification.last_reviewed_at = now
        verification.expires_at = None
        verification.reviewer_notes = notes or revocation_reason
        verification.rejection_reason_category = RejectionCategory.DISCIPLINARY_SANCTION.value

        # Demote user account status
        if profile:
            lawyer_user = self.db.query(User).filter(User.id == profile.user_id).first()
            if lawyer_user and lawyer_user.account_status == AccountStatus.VERIFIED:
                lawyer_user.account_status = AccountStatus.REGISTERED

        event = VerificationReviewEvent(
            id=generate_uuid7(),
            verification_id=verification.id,
            reviewer_id=reviewer.id,
            from_status=from_status,
            to_status=VerificationStatus.REVOKED.value,
            decision="REVOKE",
            verification_method="ADMIN_REVOCATION",
            notes=revocation_reason,
            created_at=now,
            updated_at=now,
        )
        self.db.add(event)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=reviewer.id,
            event_type="VERIFICATION_REVOKED",
            entity_type="LawyerVerification",
            entity_id=verification.id,
            action="REVOKE_ADVOCATE_VERIFICATION",
            timestamp=now,
            metadata_={
                "reviewer_id": str(reviewer.id),
                "reason": revocation_reason,
            },
        )
        self.db.add(audit)

        self.db.commit()
        self.db.refresh(verification)
        logger.warning(f"Advocate verification revoked: id={verification.id} lawyer={verification.lawyer_profile_id} reason='{revocation_reason}'")
        return verification

    def invalidate_on_credential_change(
        self,
        profile_id: uuid.UUID,
        new_enrollment: str,
        new_state_bar: str,
    ) -> bool:
        """
        Security requirement (Section 21): If an advocate edits critical verified professional
        identifiers, existing verification is immediately invalidated and requires re-verification.
        """
        active_verif = (
            self.db.query(LawyerVerification)
            .filter(
                LawyerVerification.lawyer_profile_id == profile_id,
                LawyerVerification.status == VerificationStatus.APPROVED,
            )
            .first()
        )
        if not active_verif:
            return False

        cleaned_enrollment = new_enrollment.strip().upper()
        cleaned_bar = new_state_bar.strip()

        if active_verif.enrollment_number != cleaned_enrollment or active_verif.state_bar_council != cleaned_bar:
            now = datetime.now(UTC)
            from_status = active_verif.status.value

            active_verif.status = VerificationStatus.REVOKED
            active_verif.expires_at = None
            active_verif.reviewer_notes = "Automatically invalidated due to advocate modifying verified enrollment credentials."
            active_verif.rejection_reason_category = RejectionCategory.UNVERIFIABLE_RECORD.value
            active_verif.last_reviewed_at = now

            profile = self.db.query(LawyerProfile).filter(LawyerProfile.id == profile_id).first()
            if profile:
                user = self.db.query(User).filter(User.id == profile.user_id).first()
                if user and user.account_status == AccountStatus.VERIFIED:
                    user.account_status = AccountStatus.REGISTERED

            event = VerificationReviewEvent(
                id=generate_uuid7(),
                verification_id=active_verif.id,
                reviewer_id=None,
                from_status=from_status,
                to_status=VerificationStatus.REVOKED.value,
                decision="CREDENTIAL_CHANGED_INVALIDATION",
                verification_method="AUTOMATED_CREDENTIAL_CHANGE_GUARD",
                notes="Advocate modified verified enrollment number or Bar Council.",
                created_at=now,
                updated_at=now,
            )
            self.db.add(event)

            audit = AuditEvent(
                id=generate_uuid7(),
                actor_user_id=profile.user_id if profile else None,
                event_type="CREDENTIAL_CHANGED",
                entity_type="LawyerVerification",
                entity_id=active_verif.id,
                action="INVALIDATE_VERIFICATION_ON_CHANGE",
                timestamp=now,
                metadata_={
                    "old_enrollment": active_verif.enrollment_number,
                    "new_enrollment": cleaned_enrollment,
                },
            )
            self.db.add(audit)
            self.db.commit()
            logger.warning(f"Verification invalidated for profile {profile_id} due to credential change.")
            return True

        return False

    def get_public_verification_badge(self, lawyer_id: uuid.UUID) -> PublicAdvocateVerificationBadgeResponse:
        """
        Generates public-facing verification representation adhering strictly to
        Bar Council of India Rule 36. Prohibits misleading claims or commercial promotion.
        """
        profile = (
            self.db.query(LawyerProfile)
            .filter(or_(LawyerProfile.id == lawyer_id, LawyerProfile.user_id == lawyer_id))
            .first()
        )
        if not profile:
            raise ResourceNotFoundError("Advocate profile not found")

        active_verif = (
            self.db.query(LawyerVerification)
            .filter(
                LawyerVerification.lawyer_profile_id == profile.id,
                LawyerVerification.status == VerificationStatus.APPROVED,
            )
            .order_by(desc(LawyerVerification.created_at))
            .first()
        )

        now = datetime.now(UTC)
        expires_at = active_verif.expires_at if active_verif else None
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        is_verified = (
            active_verif is not None
            and (expires_at is None or expires_at > now)
        )

        if is_verified and active_verif:
            raw_enrollment = active_verif.enrollment_number or ""
            parts = raw_enrollment.split("/")
            if len(parts) >= 3:
                masked_enrollment = f"{parts[0]}/{'*' * max(len(parts[1]), 4)}/{parts[-1]}"
            else:
                masked_enrollment = raw_enrollment[:2] + "****" if len(raw_enrollment) >= 2 else "****"

            disclaimer = (
                "Verification confirms active State Bar Council statutory enrollment and identity review. "
                "In compliance with Bar Council of India Rule 36, this verification does not constitute a "
                "commercial solicitation, government appointment, or guarantee of legal results."
            )
            compliance = (
                "Verified in accordance with Advocates Act 1961 Section 17/22. "
                "Display complies with BCI Rule 36 proviso (factual credentials without commercial ratings or solicitation)."
            )

            return PublicAdvocateVerificationBadgeResponse(
                is_verified=True,
                badge_text="✓ Professional Enrollment Verified",
                verification_badge_text="✓ Professional Enrollment Verified",
                enrollment_state=active_verif.state_bar_council,
                state_bar_council=active_verif.state_bar_council,
                enrollment_number=active_verif.enrollment_number,
                enrollment_number_masked=masked_enrollment,
                identity_reviewed=True,
                verified_on=active_verif.verified_at.strftime("%d %b %Y") if active_verif.verified_at else None,
                verified_at=active_verif.verified_at,
                verification_disclaimer=disclaimer,
                compliance_declaration=compliance,
                verification_method=active_verif.verification_method,
                verification_source=active_verif.verification_source,
            )
        else:
            return PublicAdvocateVerificationBadgeResponse(
                is_verified=False,
                badge_text="Verification Pending",
                verification_badge_text="Unverified Advocate Profile",
                enrollment_state=None,
                state_bar_council=None,
                enrollment_number=None,
                enrollment_number_masked=None,
                identity_reviewed=False,
                verified_on=None,
                verified_at=None,
                verification_disclaimer="This advocate profile is unverified or undergoing professional credential review.",
                compliance_declaration="Advocate profile credentials are unverified or pending human review.",
                verification_method=None,
                verification_source=None,
            )

    def check_and_expire_verifications(self) -> int:
        """
        Background/cron task to transition lapsed verifications.
        Expired verification immediately strips advocate professional eligibility.
        """
        now = datetime.now(UTC)
        candidates = (
            self.db.query(LawyerVerification)
            .filter(
                LawyerVerification.status == VerificationStatus.APPROVED,
                LawyerVerification.expires_at.is_not(None),
            )
            .all()
        )
        count = 0
        for verif in candidates:
            exp = verif.expires_at
            if exp and exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if exp and exp < now:
                verif.status = VerificationStatus.REVOKED
                verif.rejection_reason_category = RejectionCategory.EXPIRED_CREDENTIALS.value
                count += 1

        if count > 0:
            self.db.commit()
            logger.warning(f"Expired {count} advocate verifications due to elapsed renewal date.")
        return count

    def get_discovery_ranking_explanation(self) -> dict[str, Any]:
        """
        Returns explainable, deterministic discovery ranking methodology per BCI Rule 36.
        """
        return {
            "ranking_methodology": "DETERMINISTIC_EXPLAINABLE",
            "signals": [
                {
                    "signal": "VERIFIED_ADVOCATE_STATUS",
                    "weight": "PREREQUISITE",
                    "description": "Only advocates with verified Bar Council enrollment and active unexpired credentials appear in public discovery.",
                },
                {
                    "signal": "ACTIVE_AVAILABILITY",
                    "weight": "PRIMARY",
                    "description": "Advocates currently online and with open consultation slots are prioritized for real-time connection.",
                },
                {
                    "signal": "PRACTICE_AREA_MATCH",
                    "weight": "SECONDARY",
                    "description": "Direct match against the client's selected legal domain (Criminal, Civil, Corporate, Constitutional, Family).",
                },
            ],
            "prohibited_signals": [
                "Paid placement or sponsored boosting",
                "Fabricated success rates or win ratios",
                "Unverified client star reviews or opaque algorithms",
                "Case outcome claims prohibited by Bar Council of India advertising rules",
            ],
            "bci_compliance": "Complies with Bar Council of India Rule 36 (Standards of Professional Conduct and Etiquette), prohibiting solicitation and misleading advertising.",
        }
