import logging
import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppException, AuthorizationError, ResourceNotFoundError, ValidationError
from app.models.availability import LawyerAvailability
from app.models.user import (
    AccountStatus,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


class RejectionCategory(str, Enum):
    INVALID_ENROLLMENT_FORMAT = "INVALID_ENROLLMENT_FORMAT"
    BAR_COUNCIL_MISMATCH = "BAR_COUNCIL_MISMATCH"
    DOCUMENTS_ILLEGIBLE = "DOCUMENTS_ILLEGIBLE"
    DISCIPLINARY_SANCTION = "DISCIPLINARY_SANCTION"
    EXPIRED_CREDENTIALS = "EXPIRED_CREDENTIALS"
    UNVERIFIABLE_RECORD = "UNVERIFIABLE_RECORD"


class LawyerVerificationService:
    """
    Phase XX Mature Advocate/Lawyer Professional Verification & Discovery Service.
    Enforces statutory Bar Council validation, document evidence binding, structured
    rejection taxonomy, expiration/renewal lifecycle, and deterministic discovery ranking.
    """

    def __init__(self, db: Session):
        self.db = db

    def submit_verification(
        self,
        user: User,
        enrollment_number: str,
        state_bar_council: str,
        evidence_document_id: uuid.UUID | None = None,
        is_reverification: bool = False,
    ) -> LawyerVerification:
        if user.role != UserRole.LAWYER:
            raise AuthorizationError("Only users with role LAWYER can submit advocate verification")

        profile = self.db.query(LawyerProfile).filter(LawyerProfile.user_id == user.id).first()
        if not profile:
            raise ResourceNotFoundError("Lawyer profile not found")

        cleaned_enrollment = enrollment_number.strip().upper()
        if not cleaned_enrollment or "/" not in cleaned_enrollment:
            raise ValidationError(
                "Invalid Bar Council enrollment number format. Expected format: STATE/XXXX/YYYY (e.g. D/1234/2018)"
            )

        # Check existing active or pending verification
        existing = (
            self.db.query(LawyerVerification)
            .filter(
                LawyerVerification.lawyer_profile_id == profile.id,
                LawyerVerification.status.in_([VerificationStatus.PENDING, VerificationStatus.APPROVED]),
            )
            .first()
        )
        if existing and not is_reverification:
            if existing.status == VerificationStatus.APPROVED:
                raise ValidationError("Advocate profile already has an approved verification.")
            raise ValidationError("A verification request is already pending review.")

        verification = LawyerVerification(
            lawyer_profile_id=profile.id,
            enrollment_number=cleaned_enrollment,
            state_bar_council=state_bar_council.strip(),
            status=VerificationStatus.PENDING,
            evidence_document_id=evidence_document_id,
            is_reverification=is_reverification,
        )
        self.db.add(verification)
        self.db.commit()
        self.db.refresh(verification)

        logger.info(
            f"Advocate verification submitted: id={verification.id} lawyer_profile_id={profile.id} "
            f"bar_council='{state_bar_council}' is_reverification={is_reverification}"
        )
        return verification

    def review_verification(
        self,
        reviewer: User,
        verification_id: uuid.UUID,
        approved: bool,
        rejection_category: str | None = None,
        validity_days: int = 365,
    ) -> LawyerVerification:
        if reviewer.role != UserRole.ADMIN:
            raise AuthorizationError("Only administrators can review professional verifications")

        verification = (
            self.db.query(LawyerVerification)
            .filter(LawyerVerification.id == verification_id)
            .first()
        )
        if not verification:
            raise ResourceNotFoundError(f"Verification {verification_id} not found")

        now = datetime.now(UTC)
        verification.reviewed_by = reviewer.id
        verification.reviewed_at = now

        profile = (
            self.db.query(LawyerProfile)
            .filter(LawyerProfile.id == verification.lawyer_profile_id)
            .first()
        )

        if approved:
            verification.status = VerificationStatus.APPROVED
            verification.expires_at = now + timedelta(days=validity_days)
            verification.rejection_reason_category = None

            # Promote user account status to VERIFIED if currently REGISTERED
            if profile:
                lawyer_user = self.db.query(User).filter(User.id == profile.user_id).first()
                if lawyer_user and lawyer_user.account_status == AccountStatus.REGISTERED:
                    lawyer_user.account_status = AccountStatus.VERIFIED
        else:
            verification.status = VerificationStatus.REJECTED
            verification.expires_at = None
            verification.rejection_reason_category = rejection_category or RejectionCategory.DOCUMENTS_ILLEGIBLE.value

        self.db.commit()
        self.db.refresh(verification)

        logger.info(
            f"Verification {verification_id} reviewed: status={verification.status.value} "
            f"reviewer={reviewer.id} expires_at={verification.expires_at}"
        )
        return verification

    def check_and_expire_verifications(self) -> int:
        """
        Background/cron task to transition lapsed verifications.
        Revoked/expired verification immediately strips advocate professional eligibility.
        """
        now = datetime.now(UTC)
        expired_records = (
            self.db.query(LawyerVerification)
            .filter(
                LawyerVerification.status == VerificationStatus.APPROVED,
                LawyerVerification.expires_at.is_not(None),
                LawyerVerification.expires_at < now,
            )
            .all()
        )
        count = 0
        for verif in expired_records:
            verif.status = VerificationStatus.REJECTED
            verif.rejection_reason_category = RejectionCategory.EXPIRED_CREDENTIALS.value
            count += 1

        if count > 0:
            self.db.commit()
            logger.warning(f"Expired {count} advocate verifications due to elapsed renewal date.")
        return count

    def get_discovery_ranking_explanation(self) -> dict[str, Any]:
        """
        Returns explainable, deterministic discovery ranking methodology per Part K.
        No fabricated ratings, reviews, or paid placements exist in LCC.
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
                {
                    "signal": "VERIFIED_ENROLLMENT_TENURE",
                    "weight": "TIE_BREAKER",
                    "description": "Chronological verified enrollment date with State Bar Council.",
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
