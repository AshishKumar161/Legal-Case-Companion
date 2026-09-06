import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.auth import EmailVerificationToken, RefreshTokenSession

logger = logging.getLogger(__name__)


class SessionCleanupService:
    """
    Manages periodic pruning of expired auth records, refresh token sessions,
    and verification tokens while preserving a minimum 30-day forensic audit window.
    """

    def __init__(self, db: Session):
        self.db = db

    def cleanup_expired_sessions(
        self,
        refresh_token_retention_days: int = 30,
        verification_token_retention_days: int = 7,
    ) -> dict[str, Any]:
        """
        Prunes expired RefreshTokenSessions beyond the security forensic retention window (default: 30 days),
        and expired EmailVerificationTokens beyond their retention window (default: 7 days).
        Never deletes unexpired, active, or legitimately pending credentials.
        """
        now = datetime.now(UTC)
        rt_cutoff = now - timedelta(days=refresh_token_retention_days)
        vt_cutoff = now - timedelta(days=verification_token_retention_days)

        # 1. Prune expired refresh token sessions beyond forensic retention
        pruned_rt = (
            self.db.query(RefreshTokenSession)
            .filter(RefreshTokenSession.expires_at < rt_cutoff)
            .delete(synchronize_session=False)
        )

        # 2. Prune expired email verification tokens beyond retention
        pruned_vt = (
            self.db.query(EmailVerificationToken)
            .filter(EmailVerificationToken.expires_at < vt_cutoff)
            .delete(synchronize_session=False)
        )

        if pruned_rt or pruned_vt:
            self.db.commit()
            logger.info(
                "Pruned %d expired refresh token sessions (>%dd) and %d verification tokens (>%dd).",
                pruned_rt,
                refresh_token_retention_days,
                pruned_vt,
                verification_token_retention_days,
            )

        return {
            "pruned_refresh_token_sessions": pruned_rt,
            "pruned_verification_tokens": pruned_vt,
            "executed_at": now.isoformat(),
        }
