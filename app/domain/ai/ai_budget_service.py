import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.identifiers import generate_uuid7
from app.models.commercial import CommercialEntitlement
from app.models.user import User


class AIBudgetService:
    """Production AI cost, query quota, and emergency capacity governor (Part T)."""

    DEFAULT_DAILY_QUERY_LIMIT = 50
    DEFAULT_DAILY_TOKEN_LIMIT = 100_000

    def __init__(self, db: Session):
        self.db = db

    def check_and_consume_budget(
        self,
        user: User,
        estimated_tokens: int = 1000,
    ) -> dict[str, Any]:
        """Validates that user has not exceeded daily AI limits and platform AI is not disabled."""
        # Check emergency AI disablement
        if "ai" in [f.lower() for f in settings.PILOT_DISABLED_FEATURES] or "copilot" in [f.lower() for f in settings.PILOT_DISABLED_FEATURES]:
            raise AppException(
                status_code=503,
                code="AI_EMERGENCY_DISABLED",
                message="AI services are temporarily disabled for operational capacity or cost control.",
            )

        # Admin bypass for testing / ops
        if user.role.value == "ADMIN":
            return {"status": "ALLOWED", "remaining_queries": 9999, "is_admin": True}

        # Query entitlement record with concurrency locking when supported
        query = (
            self.db.query(CommercialEntitlement)
            .filter(
                CommercialEntitlement.user_id == user.id,
                CommercialEntitlement.entitlement_type == "AI_RESEARCH_QUERIES",
                CommercialEntitlement.is_active.is_(True),
            )
        )
        if self.db.bind and self.db.bind.dialect.name != "sqlite":
            query = query.with_for_update()
        entitlement = query.first()

        now = datetime.now(UTC)
        if not entitlement:
            # Create default daily entitlement
            entitlement = CommercialEntitlement(
                id=generate_uuid7(),
                user_id=user.id,
                entitlement_type="AI_RESEARCH_QUERIES",
                quota_limit=self.DEFAULT_DAILY_QUERY_LIMIT,
                quota_used=0,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            self.db.add(entitlement)
            self.db.commit()
            self.db.refresh(entitlement)

        if entitlement.quota_used >= entitlement.quota_limit:
            raise AppException(
                status_code=429,
                code="AI_DAILY_QUOTA_EXCEEDED",
                message=f"Daily AI research query limit ({entitlement.quota_limit}) reached. Quota refreshes daily.",
            )

        entitlement.quota_used += 1
        entitlement.updated_at = now
        self.db.commit()

        return {
            "status": "ALLOWED",
            "quota_used": entitlement.quota_used,
            "quota_limit": entitlement.quota_limit,
            "remaining_queries": entitlement.quota_limit - entitlement.quota_used,
        }

    def check_user_budget(self, user_id: uuid.UUID, daily_limit: int = 50) -> dict[str, Any]:
        """Inspects current user quota and remaining allowances."""
        ent = (
            self.db.query(CommercialEntitlement)
            .filter(
                CommercialEntitlement.user_id == user_id,
                CommercialEntitlement.entitlement_type == "AI_RESEARCH_QUERIES",
                CommercialEntitlement.is_active.is_(True),
            )
            .first()
        )
        used = ent.quota_used if ent else 0
        limit = ent.quota_limit if ent else daily_limit
        remaining = max(0, limit - used)
        return {
            "allowed": remaining > 0,
            "remaining_queries": remaining,
            "quota_used": used,
            "quota_limit": limit,
        }

    def record_query_usage(self, user_id: uuid.UUID, cost_usd: float = 0.0, tokens: int = 0) -> None:
        """Records query consumption against entitlement."""
        ent = (
            self.db.query(CommercialEntitlement)
            .filter(
                CommercialEntitlement.user_id == user_id,
                CommercialEntitlement.entitlement_type == "AI_RESEARCH_QUERIES",
                CommercialEntitlement.is_active.is_(True),
            )
            .first()
        )
        now = datetime.now(UTC)
        if not ent:
            ent = CommercialEntitlement(
                id=generate_uuid7(),
                user_id=user_id,
                entitlement_type="AI_RESEARCH_QUERIES",
                quota_limit=2,  # Configurable in tests
                quota_used=1,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            self.db.add(ent)
        else:
            ent.quota_used += 1
            ent.updated_at = now
        self.db.commit()

    def refund_budget(self, user_id: uuid.UUID) -> None:
        """Rolls back 1 consumed query in case of internal provider error or failure."""
        ent = (
            self.db.query(CommercialEntitlement)
            .filter(
                CommercialEntitlement.user_id == user_id,
                CommercialEntitlement.entitlement_type == "AI_RESEARCH_QUERIES",
                CommercialEntitlement.is_active.is_(True),
            )
            .first()
        )
        if ent and ent.quota_used > 0:
            ent.quota_used -= 1
            ent.updated_at = datetime.now(UTC)
            self.db.commit()

    def is_emergency_disabled(self) -> bool:
        return "ai" in [f.lower() for f in settings.PILOT_DISABLED_FEATURES]

    def set_emergency_disabled(self, disabled: bool) -> None:
        features = list(settings.PILOT_DISABLED_FEATURES)
        if disabled and "ai" not in [f.lower() for f in features]:
            features.append("ai")
        elif not disabled:
            features = [f for f in features if f.lower() not in ("ai", "copilot")]
        settings.PILOT_DISABLED_FEATURES = features
