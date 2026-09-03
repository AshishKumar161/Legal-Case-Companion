"""Real-time presence tracking service for platform users and lawyers."""

import threading
import time
from uuid import UUID


class PresenceManager:
    """Thread-safe in-memory presence tracker with automatic TTL eviction."""

    def __init__(self, timeout_seconds: int = 45):
        self._lock = threading.Lock()
        # user_id (str) -> timestamp of last heartbeat
        self._active_users: dict[str, float] = {}
        self._timeout_seconds = timeout_seconds

    def record_heartbeat(self, user_id: UUID | str) -> None:
        """Record or refresh active presence for a given user."""
        key = str(user_id)
        with self._lock:
            self._active_users[key] = time.time()

    def is_online(self, user_id: UUID | str | None) -> bool:
        """Check if a specific user is currently active/online."""
        if not user_id:
            return False
        key = str(user_id)
        now = time.time()
        with self._lock:
            last_seen = self._active_users.get(key)
            if not last_seen:
                return False
            return (now - last_seen) <= self._timeout_seconds

    def get_online_user_ids(self) -> set[str]:
        """Return set of user IDs who sent a heartbeat within the timeout window."""
        now = time.time()
        with self._lock:
            # Purge entries older than 2x timeout
            self._active_users = {
                uid: ts
                for uid, ts in self._active_users.items()
                if (now - ts) <= (self._timeout_seconds * 2)
            }
            return {
                uid
                for uid, ts in self._active_users.items()
                if (now - ts) <= self._timeout_seconds
            }

    def clear(self) -> None:
        """Clear all presence records (useful for test fixtures)."""
        with self._lock:
            self._active_users.clear()


presence_manager = PresenceManager(timeout_seconds=45)
