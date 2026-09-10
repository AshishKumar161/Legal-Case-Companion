"""Real-time presence tracking service for platform users and lawyers.

Provides production-safe, distributed presence tracking via Redis with
automatic TTL eviction and authoritative state management (OFFLINE, ONLINE,
AVAILABLE, BUSY).
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.redis import get_redis_client
from app.schemas.presence import PresenceStatus

logger = logging.getLogger(__name__)


class PresenceService:
    """Production-grade presence tracker backed by Redis with TTL eviction."""

    def __init__(self, timeout_seconds: int | None = None) -> None:
        self._timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.PRESENCE_TTL_SECONDS
        )

    def _get_redis(self) -> Any:
        return get_redis_client()

    def _user_key(self, user_id: UUID | str) -> str:
        return (
            f"{settings.REDIS_KEY_PREFIX}:{settings.ENVIRONMENT}:presence:user:{user_id}"
        )

    def _lawyer_key(self, lawyer_id: UUID | str) -> str:
        return (
            f"{settings.REDIS_KEY_PREFIX}:{settings.ENVIRONMENT}:presence:lawyer:{lawyer_id}"
        )

    def record_heartbeat(
        self,
        user_id: UUID | str,
        lawyer_id: UUID | str | None = None,
        available_preference: bool = True,
    ) -> PresenceStatus:
        """Record or refresh active presence for a user or lawyer.

        Sets a TTL on Redis key so that crashes or closed browsers naturally
        expire to OFFLINE after timeout_seconds.
        """
        redis_client = self._get_redis()
        now = datetime.now(UTC)
        payload = {
            "user_id": str(user_id),
            "lawyer_id": str(lawyer_id) if lawyer_id else None,
            "last_heartbeat": now.isoformat(),
            "available_preference": bool(available_preference),
            "status": PresenceStatus.AVAILABLE.value
            if available_preference
            else PresenceStatus.ONLINE.value,
        }
        encoded = json.dumps(payload).encode("utf-8")

        u_key = self._user_key(user_id)
        redis_client.set(u_key, encoded, ex=self._timeout_seconds)

        if lawyer_id:
            l_key = self._lawyer_key(lawyer_id)
            redis_client.set(l_key, encoded, ex=self._timeout_seconds)

        logger.debug(
            "Recorded presence heartbeat for user=%s lawyer=%s (pref_avail=%s)",
            user_id,
            lawyer_id,
            available_preference,
        )
        return (
            PresenceStatus.AVAILABLE
            if available_preference
            else PresenceStatus.ONLINE
        )

    def mark_online(
        self, user_id: UUID | str, lawyer_id: UUID | str | None = None
    ) -> None:
        """Mark lawyer explicitly as ONLINE (not accepting instant calls)."""
        self.record_heartbeat(
            user_id, lawyer_id=lawyer_id, available_preference=False
        )

    def mark_available(
        self, user_id: UUID | str, lawyer_id: UUID | str | None = None
    ) -> None:
        """Mark lawyer explicitly as AVAILABLE for instant calls."""
        self.record_heartbeat(
            user_id, lawyer_id=lawyer_id, available_preference=True
        )

    def mark_unavailable(
        self, user_id: UUID | str, lawyer_id: UUID | str | None = None
    ) -> None:
        """Mark lawyer explicitly as unavailable (ONLINE only)."""
        self.record_heartbeat(
            user_id, lawyer_id=lawyer_id, available_preference=False
        )

    def mark_busy(
        self,
        user_id: UUID | str,
        lawyer_id: UUID | str | None = None,
        reason: str = "In active consultation",
    ) -> None:
        """Mark lawyer as BUSY due to ongoing call or meeting."""
        redis_client = self._get_redis()
        now = datetime.now(UTC)
        payload = {
            "user_id": str(user_id),
            "lawyer_id": str(lawyer_id) if lawyer_id else None,
            "last_heartbeat": now.isoformat(),
            "available_preference": False,
            "status": PresenceStatus.BUSY.value,
            "busy_reason": reason,
        }
        encoded = json.dumps(payload).encode("utf-8")

        u_key = self._user_key(user_id)
        redis_client.set(u_key, encoded, ex=self._timeout_seconds)

        if lawyer_id:
            l_key = self._lawyer_key(lawyer_id)
            redis_client.set(l_key, encoded, ex=self._timeout_seconds)

    def mark_offline(
        self, user_id: UUID | str, lawyer_id: UUID | str | None = None
    ) -> None:
        """Immediately delete presence record (explicit logout / disconnect)."""
        redis_client = self._get_redis()
        keys_to_del = [self._user_key(user_id)]
        if lawyer_id:
            keys_to_del.append(self._lawyer_key(lawyer_id))
        redis_client.delete(*keys_to_del)
        logger.info("Evicted presence for user=%s lawyer=%s", user_id, lawyer_id)

    def is_online(self, user_id: UUID | str | None) -> bool:
        """Check if a specific user is currently active/online."""
        if not user_id:
            return False
        try:
            redis_client = self._get_redis()
            raw = redis_client.get(self._user_key(user_id))
            return raw is not None
        except Exception as e:
            logger.warning("Redis presence read failed for user %s: %s. Failing safe to offline.", user_id, e)
            return False

    def is_available_preference(self, user_id: UUID | str | None) -> bool:
        """Check if user has a valid heartbeat with preference set to AVAILABLE."""
        if not user_id:
            return False
        try:
            redis_client = self._get_redis()
            raw = redis_client.get(self._user_key(user_id))
            if not raw:
                return False
            data = json.loads(raw.decode("utf-8"))
            return (
                data.get("status") == PresenceStatus.AVAILABLE.value
                and data.get("available_preference", True) is True
            )
        except Exception as e:
            logger.warning("Redis availability read failed for user %s: %s. Failing safe to unavailable.", user_id, e)
            return False

    def get_raw_presence(
        self, user_id: UUID | str | None = None, lawyer_id: UUID | str | None = None
    ) -> dict[str, Any] | None:
        """Retrieve stored presence payload from Redis."""
        try:
            redis_client = self._get_redis()
            raw: bytes | None = None
            if user_id:
                raw = redis_client.get(self._user_key(user_id))
            if not raw and lawyer_id:
                raw = redis_client.get(self._lawyer_key(lawyer_id))
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            logger.warning("Redis presence payload read failed: %s. Failing safe to None.", e)
            return None

    def get_presence(
        self, user_id: UUID | str | None = None, lawyer_id: UUID | str | None = None
    ) -> dict[str, Any] | None:
        """Retrieve stored presence payload from Redis."""
        return self.get_raw_presence(user_id=user_id, lawyer_id=lawyer_id)

    def get_online_user_ids(self) -> set[str]:
        """Return set of user IDs who currently have an unexpired heartbeat in Redis."""
        redis_client = self._get_redis()
        pattern = f"{settings.REDIS_KEY_PREFIX}:{settings.ENVIRONMENT}:presence:user:*"
        user_ids = set()
        for raw_key in redis_client.scan_iter(match=pattern):
            key_str = (
                raw_key.decode("utf-8")
                if isinstance(raw_key, bytes)
                else str(raw_key)
            )
            # Extract user_id from prefix:env:presence:user:<user_id>
            parts = key_str.split(":presence:user:")
            if len(parts) == 2:
                user_ids.add(parts[1])
        return user_ids

    def get_online_lawyer_ids(self) -> set[str]:
        """Return set of lawyer IDs who currently have an unexpired heartbeat in Redis."""
        redis_client = self._get_redis()
        pattern = f"{settings.REDIS_KEY_PREFIX}:{settings.ENVIRONMENT}:presence:lawyer:*"
        lawyer_ids = set()
        for raw_key in redis_client.scan_iter(match=pattern):
            key_str = (
                raw_key.decode("utf-8")
                if isinstance(raw_key, bytes)
                else str(raw_key)
            )
            parts = key_str.split(":presence:lawyer:")
            if len(parts) == 2:
                lawyer_ids.add(parts[1])
        return lawyer_ids

    def clear(self) -> None:
        """Clear all presence records across Redis (used for test fixtures)."""
        redis_client = self._get_redis()
        pattern = f"{settings.REDIS_KEY_PREFIX}:{settings.ENVIRONMENT}:presence:*"
        keys = list(redis_client.scan_iter(match=pattern))
        if keys:
            redis_client.delete(*[k.decode("utf-8") if isinstance(k, bytes) else k for k in keys])


presence_service = PresenceService(timeout_seconds=settings.PRESENCE_TTL_SECONDS)
presence_manager = presence_service  # Backwards compatibility alias
