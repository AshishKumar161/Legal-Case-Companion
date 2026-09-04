import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.core.identifiers import generate_uuid7
from app.models.ai_review import (
    AIReviewCategory,
    AIReviewOutcome,
    AIReviewRecord,
    AIReviewSeverity,
    AIReviewStatus,
)
from app.models.audit import AuditEvent
from app.models.user import User


class AIReviewService:
    """Manages the human review loop for AI legal outputs, grounding discrepancies, and safety audits."""

    def __init__(self, db: Session):
        self.db = db

    def _generate_review_id(self) -> str:
        today_str = datetime.now(UTC).strftime("%Y%m%d")
        count = (
            self.db.query(func.count(AIReviewRecord.id))
            .filter(AIReviewRecord.review_id.like(f"REV-{today_str}-%"))
            .scalar()
            or 0
        )
        return f"REV-{today_str}-{count + 1:04d}"

    def submit_review(
        self,
        reviewer: User,
        category: AIReviewCategory,
        severity: AIReviewSeverity,
        review_outcome: AIReviewOutcome,
        original_prompt_snippet: str | None = None,
        original_answer_snippet: str | None = None,
        corrected_interpretation: str | None = None,
        message_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
        model_version: str | None = "gpt-4o",
        retrieval_config_version: str | None = "v1.0",
        linked_release_id: str | None = None,
        linked_incident_id: uuid.UUID | None = None,
    ) -> AIReviewRecord:
        now = datetime.now(UTC)
        rev_id = self._generate_review_id()

        record = AIReviewRecord(
            id=generate_uuid7(),
            review_id=rev_id,
            message_id=message_id,
            conversation_id=conversation_id,
            reviewer_user_id=reviewer.id,
            category=category,
            severity=severity,
            review_outcome=review_outcome,
            status=AIReviewStatus.PENDING,
            original_prompt_snippet=original_prompt_snippet[:1000] if original_prompt_snippet else None,
            original_answer_snippet=original_answer_snippet[:2000] if original_answer_snippet else None,
            corrected_interpretation=corrected_interpretation,
            model_version=model_version,
            retrieval_config_version=retrieval_config_version,
            linked_release_id=linked_release_id,
            linked_incident_id=linked_incident_id,
            created_at=now,
            updated_at=now,
        )
        self.db.add(record)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=reviewer.id,
            event_type="AI_REVIEW_SUBMITTED",
            entity_type="AI_HUMAN_REVIEW",
            entity_id=record.id,
            action="CREATE",
            timestamp=now,
            metadata_={
                "review_id": record.review_id,
                "category": category.value,
                "severity": severity.value,
                "outcome": review_outcome.value,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(record)
        return record

    def action_review(
        self,
        identifier: str | uuid.UUID,
        action_taken: str,
        actor: User,
    ) -> AIReviewRecord:
        record = self.get_review(identifier)
        now = datetime.now(UTC)

        record.status = AIReviewStatus.ACTIONED
        record.action_taken = action_taken.strip()
        record.updated_at = now

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=actor.id,
            event_type="AI_REVIEW_ACTIONED",
            entity_type="AI_HUMAN_REVIEW",
            entity_id=record.id,
            action="UPDATE",
            timestamp=now,
            metadata_={"review_id": record.review_id, "action_taken": action_taken},
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_review(self, identifier: str | uuid.UUID) -> AIReviewRecord:
        query = self.db.query(AIReviewRecord)
        if isinstance(identifier, uuid.UUID):
            record = query.filter(AIReviewRecord.id == identifier).first()
        else:
            try:
                parsed_uuid = uuid.UUID(str(identifier))
                record = query.filter((AIReviewRecord.id == parsed_uuid) | (AIReviewRecord.review_id == str(identifier))).first()
            except ValueError:
                record = query.filter(AIReviewRecord.review_id == str(identifier)).first()

        if not record:
            raise ResourceNotFoundError(f"AI Review '{identifier}' not found.")
        return record

    def list_reviews(
        self,
        status: AIReviewStatus | None = None,
        category: AIReviewCategory | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AIReviewRecord]:
        query = self.db.query(AIReviewRecord)
        if status:
            query = query.filter(AIReviewRecord.status == status)
        if category:
            query = query.filter(AIReviewRecord.category == category)
        return query.order_by(AIReviewRecord.created_at.desc()).offset(skip).limit(limit).all()

    def get_review_metrics(self) -> dict[str, Any]:
        total_reviews = self.db.query(func.count(AIReviewRecord.id)).scalar() or 0
        confirmed_defects = (
            self.db.query(func.count(AIReviewRecord.id))
            .filter(AIReviewRecord.review_outcome == AIReviewOutcome.CONFIRMED_DEFECT)
            .scalar()
            or 0
        )

        cat_counts: dict[str, int] = {}
        all_revs = self.db.query(AIReviewRecord).all()
        for r in all_revs:
            cat_counts[r.category.value] = cat_counts.get(r.category.value, 0) + 1

        defect_rate = round((confirmed_defects / total_reviews) * 100.0, 2) if total_reviews > 0 else 0.0

        return {
            "total_reviews": total_reviews,
            "confirmed_defects": confirmed_defects,
            "defect_rate_pct": defect_rate,
            "category_breakdown": cat_counts,
            "sample_confidence": "HIGH" if total_reviews >= 30 else "INSUFFICIENT_SAMPLE_SIZE",
        }
