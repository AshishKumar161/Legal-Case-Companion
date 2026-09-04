import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, ResourceNotFoundError
from app.core.i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES, TRANSLATION_CATALOG
from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.localization import TranslationMessage, TranslationStatus
from app.models.user import User


class TranslationService:
    """Manages translation message lifecycle, legal review statuses, and dictionary distribution."""

    def __init__(self, db: Session):
        self.db = db

    def get_messages_dictionary(self, locale: str = DEFAULT_LOCALE) -> dict[str, str]:
        """Returns consolidated dictionary: built-in defaults merged with approved database messages."""
        norm_locale = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
        result = dict(TRANSLATION_CATALOG.get(norm_locale, TRANSLATION_CATALOG[DEFAULT_LOCALE]))

        # Overlay approved messages from DB
        db_messages = (
            self.db.query(TranslationMessage)
            .filter(
                TranslationMessage.locale == norm_locale,
                TranslationMessage.status == TranslationStatus.APPROVED,
            )
            .all()
        )
        for msg in db_messages:
            result[msg.source_key] = msg.translation

        return result

    def register_translation(
        self,
        source_key: str,
        source_text: str,
        locale: str,
        translation: str,
        actor: User,
        version: str = "1.0.0",
        metadata_: dict | None = None,
    ) -> TranslationMessage:
        if locale not in SUPPORTED_LOCALES:
            raise AppException(
                status_code=400,
                code="UNSUPPORTED_LOCALE",
                message=f"Locale '{locale}' is not currently supported. Supported: {SUPPORTED_LOCALES}",
            )

        now = datetime.now(UTC)
        existing = (
            self.db.query(TranslationMessage)
            .filter(TranslationMessage.locale == locale, TranslationMessage.source_key == source_key)
            .first()
        )
        if existing:
            existing.source_text = source_text
            existing.translation = translation
            existing.status = TranslationStatus.REVIEW
            existing.version = version
            existing.updated_at = now
            if metadata_:
                existing.metadata_ = metadata_
            msg = existing
        else:
            msg = TranslationMessage(
                id=generate_uuid7(),
                source_key=source_key,
                source_text=source_text,
                locale=locale,
                translation=translation,
                status=TranslationStatus.REVIEW,
                review_status="PENDING",
                version=version,
                metadata_=metadata_ or {},
                created_at=now,
                updated_at=now,
            )
            self.db.add(msg)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=actor.id,
            event_type="TRANSLATION_REGISTERED",
            entity_type="TRANSLATION_MESSAGE",
            entity_id=msg.id,
            action="CREATE" if not existing else "UPDATE",
            timestamp=now,
            metadata_={"locale": locale, "source_key": source_key, "version": version},
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def review_translation(
        self,
        message_id: uuid.UUID,
        approved: bool,
        actor: User,
        review_status: str = "HUMAN_REVIEWED",
        review_notes: str | None = None,
    ) -> TranslationMessage:
        msg = self.db.query(TranslationMessage).filter(TranslationMessage.id == message_id).first()
        if not msg:
            raise ResourceNotFoundError(f"Translation message '{message_id}' not found.")

        now = datetime.now(UTC)
        msg.status = TranslationStatus.APPROVED if approved else TranslationStatus.DRAFT
        msg.review_status = review_status
        msg.reviewed_by = actor.email
        msg.reviewed_at = now
        msg.updated_at = now
        if review_notes:
            msg.metadata_["review_notes"] = review_notes

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=actor.id,
            event_type="TRANSLATION_REVIEWED",
            entity_type="TRANSLATION_MESSAGE",
            entity_id=msg.id,
            action="UPDATE",
            timestamp=now,
            metadata_={
                "locale": msg.locale,
                "source_key": msg.source_key,
                "approved": approved,
                "review_status": review_status,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_localization_summary(self) -> dict[str, Any]:
        """Calculates translation coverage and legal approval rate per locale."""
        summary = {}
        for loc in SUPPORTED_LOCALES:
            total_catalog = len(TRANSLATION_CATALOG.get(loc, {}))
            db_total = self.db.query(func.count(TranslationMessage.id)).filter(TranslationMessage.locale == loc).scalar() or 0
            db_approved = (
                self.db.query(func.count(TranslationMessage.id))
                .filter(TranslationMessage.locale == loc, TranslationMessage.status == TranslationStatus.APPROVED)
                .scalar()
                or 0
            )
            summary[loc] = {
                "base_strings": total_catalog,
                "custom_strings_total": db_total,
                "custom_approved": db_approved,
                "coverage_status": "HIGH" if (total_catalog + db_approved) >= 15 else "INCOMPLETE",
            }
        return {"supported_locales": list(SUPPORTED_LOCALES), "locales": summary}
