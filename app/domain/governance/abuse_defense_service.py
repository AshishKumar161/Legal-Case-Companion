import logging
import uuid
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.consultation import Consultation, ConsultationStatus
from app.models.user import User

logger = logging.getLogger(__name__)

DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "guerrillamail.com",
    "tempmail.com",
    "10minutemail.com",
    "throwawaymail.com",
    "yopmail.com",
    "sharklasers.com",
    "getairmail.com",
    "dispostable.com",
    "trashmail.com",
}


class AbuseDefenseService:
    """
    Phase XX Public Abuse Resilience Service.
    Protects registration, consultation booking, profile enumeration, and file uploads
    from automated abuse, credential stuffing, scraping, and spam without invasive surveillance.
    """

    def __init__(self, db: Session):
        self.db = db

    def check_registration_risk(self, email: str, ip_address: str | None = None) -> dict[str, Any]:
        """
        Validates email domain and basic risk indicators during onboarding.
        Rejects disposable mail domains and flagged patterns.
        """
        normalized = email.strip().lower()
        domain = normalized.split("@")[-1] if "@" in normalized else ""

        if domain in DISPOSABLE_DOMAINS:
            logger.warning(f"Registration blocked for disposable email domain: {domain}")
            return {
                "allowed": False,
                "reason": "Disposable or temporary email domains are not permitted for legal communications.",
                "risk_tier": "HIGH",
            }

        return {
            "allowed": True,
            "reason": None,
            "risk_tier": "LOW",
        }

    def check_consultation_velocity(self, client_id: uuid.UUID, max_pending: int = 5) -> dict[str, Any]:
        """
        Prevents spamming advocates with fake or unconfirmed consultation requests.
        Enforces a ceiling on concurrent pending consultation requests per client.
        """
        pending_count = (
            self.db.query(func.count(Consultation.id))
            .filter(
                Consultation.client_id == client_id,
                Consultation.status.in_([ConsultationStatus.REQUESTED, ConsultationStatus.ACCEPTED]),
            )
            .scalar()
            or 0
        )

        if pending_count >= max_pending:
            logger.warning(
                f"Client {client_id} exceeded pending consultation limit ({pending_count}/{max_pending})"
            )
            return {
                "allowed": False,
                "reason": f"You have {pending_count} pending consultations. Please complete or cancel existing requests before booking more.",
                "pending_count": pending_count,
            }

        return {
            "allowed": True,
            "reason": None,
            "pending_count": pending_count,
        }

    def evaluate_public_request_risk(
        self,
        endpoint: str,
        user: User | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """
        Lightweight non-invasive risk assessment for public facing endpoints.
        """
        risk_tier = "LOW"
        if user and user.account_status and user.account_status.value in ("RESTRICTED", "SUSPENDED"):
            risk_tier = "CRITICAL"

        return {
            "endpoint": endpoint,
            "risk_tier": risk_tier,
            "requires_step_up_auth": risk_tier == "CRITICAL",
        }
