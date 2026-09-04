import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import AppException, ResourceNotFoundError
from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.legal_document import (
    LegalDocumentType,
    LegalDocumentVersion,
    UserDocumentConsent,
)
from app.models.user import User


class LegalDocumentService:
    """Manages versioned legal documents, publications, and non-repudiable user consent audit trails (Parts G, H)."""

    def __init__(self, db: Session):
        self.db = db

    def publish_version(
        self,
        document_type: LegalDocumentType,
        version: str,
        title: str,
        content: str,
        effective_at: datetime,
        actor: User,
        locale: str = "en-IN",
        summary_of_changes: str | None = None,
    ) -> LegalDocumentVersion:
        now = datetime.now(UTC)

        # Check existing version
        existing = (
            self.db.query(LegalDocumentVersion)
            .filter(
                LegalDocumentVersion.document_type == document_type,
                LegalDocumentVersion.version == version,
                LegalDocumentVersion.locale == locale,
            )
            .first()
        )
        if existing:
            raise AppException(
                status_code=400,
                code="DOCUMENT_VERSION_EXISTS",
                message=f"Version {version} for {document_type.value} ({locale}) already exists.",
            )

        doc = LegalDocumentVersion(
            id=generate_uuid7(),
            document_type=document_type,
            version=version,
            locale=locale,
            title=title,
            content=content,
            summary_of_changes=summary_of_changes,
            effective_at=effective_at,
            approval_status="LEGAL_APPROVED",
            publication_status="PUBLISHED",
            approved_by=actor.email,
            approved_at=now,
            metadata_={},
            created_at=now,
            updated_at=now,
        )
        self.db.add(doc)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=actor.id,
            event_type="LEGAL_DOCUMENT_PUBLISHED",
            entity_type="LEGAL_DOCUMENT_VERSION",
            entity_id=doc.id,
            action="CREATE",
            timestamp=now,
            metadata_={"document_type": document_type.value, "version": version, "locale": locale},
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get_current_document(
        self,
        document_type: LegalDocumentType,
        locale: str = "en-IN",
    ) -> LegalDocumentVersion:
        now = datetime.now(UTC)
        doc = (
            self.db.query(LegalDocumentVersion)
            .filter(
                LegalDocumentVersion.document_type == document_type,
                LegalDocumentVersion.locale == locale,
                LegalDocumentVersion.publication_status == "PUBLISHED",
                LegalDocumentVersion.effective_at <= now,
            )
            .order_by(LegalDocumentVersion.effective_at.desc())
            .first()
        )
        if not doc and locale != "en-IN":
            # Fallback to English
            doc = (
                self.db.query(LegalDocumentVersion)
                .filter(
                    LegalDocumentVersion.document_type == document_type,
                    LegalDocumentVersion.locale == "en-IN",
                    LegalDocumentVersion.publication_status == "PUBLISHED",
                    LegalDocumentVersion.effective_at <= now,
                )
                .order_by(LegalDocumentVersion.effective_at.desc())
                .first()
            )

        if not doc:
            raise ResourceNotFoundError(f"Published document for {document_type.value} ({locale}) not found.")
        return doc

    def record_user_consent(
        self,
        user: User,
        document_type: LegalDocumentType,
        version: str,
        locale: str = "en-IN",
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> UserDocumentConsent:
        doc = (
            self.db.query(LegalDocumentVersion)
            .filter(
                LegalDocumentVersion.document_type == document_type,
                LegalDocumentVersion.version == version,
            )
            .first()
        )
        if not doc:
            raise ResourceNotFoundError(f"Document version '{version}' for {document_type.value} not found.")

        now = datetime.now(UTC)
        ip_hash = hashlib.sha256(client_ip.encode()).hexdigest() if client_ip else None
        ua_hash = hashlib.sha256(user_agent.encode()).hexdigest() if user_agent else None

        consent = UserDocumentConsent(
            id=generate_uuid7(),
            user_id=user.id,
            document_version_id=doc.id,
            document_type=document_type,
            version=version,
            locale=locale,
            accepted_at=now,
            ip_hash=ip_hash,
            user_agent_hash=ua_hash,
            metadata_={},
            created_at=now,
            updated_at=now,
        )
        self.db.add(consent)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=user.id,
            event_type="LEGAL_DOCUMENT_CONSENT_RECORDED",
            entity_type="USER_DOCUMENT_CONSENT",
            entity_id=consent.id,
            action="CREATE",
            timestamp=now,
            metadata_={"document_type": document_type.value, "version": version, "locale": locale},
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(consent)
        return consent

    def list_user_consents(self, user_id: uuid.UUID) -> list[UserDocumentConsent]:
        return (
            self.db.query(UserDocumentConsent)
            .filter(UserDocumentConsent.user_id == user_id)
            .order_by(UserDocumentConsent.accepted_at.desc())
            .all()
        )
