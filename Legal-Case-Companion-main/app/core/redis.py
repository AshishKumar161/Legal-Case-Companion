"""Redis connection manager and caching/presence client.

Provides connection-pooled access to Redis in production environments, with
observable failure modes when Redis is unreachable. In development/testing,
supports an in-memory TTL-expiring adapter when an external Redis instance
is not configured.
"""

import fnmatch
import logging
import threading
import time
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import redis
    from redis.exceptions import ConnectionError as RedisConnectionError
except ImportError:
    redis = None  # type: ignore[assignment]
    RedisConnectionError = ConnectionError  # type: ignore[assignment, misc]


class InMemoryRedisClient:
    """Thread-safe in-memory mock of Redis for local dev and testing.

    Faithfully supports TTL expiration, key scanning, and atomic operations.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # key -> (value_bytes, expire_timestamp_or_none)
        self._store: dict[str, tuple[bytes, float | None]] = {}

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [
            k
            for k, (_, exp) in self._store.items()
            if exp is not None and now > exp
        ]
        for k in expired:
            self._store.pop(k, None)

    def ping(self) -> bool:
        return True

    def get(self, name: str) -> bytes | None:
        with self._lock:
            self._purge_expired()
            entry = self._store.get(name)
            if entry is None:
                return None
            val, exp = entry
            if exp is not None and time.time() > exp:
                self._store.pop(name, None)
                return None
            return val

    def set(
        self,
        name: str,
        value: Any,
        ex: int | None = None,
        px: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        val_bytes = value if isinstance(value, bytes) else str(value).encode("utf-8")
        with self._lock:
            self._purge_expired()
            exists = name in self._store

            if nx and exists:
                return False
            if xx and not exists:
                return False

            exp_time: float | None = None
            if ex is not None:
                exp_time = time.time() + ex
            elif px is not None:
                exp_time = time.time() + (px / 1000.0)

            self._store[name] = (val_bytes, exp_time)
            return True

    def setex(self, name: str, time_sec: int, value: Any) -> bool:
        return self.set(name, value, ex=time_sec)

    def delete(self, *names: str) -> int:
        with self._lock:
            deleted = 0
            for name in names:
                if self._store.pop(name, None) is not None:
                    deleted += 1
            return deleted

    def exists(self, *names: str) -> int:
        with self._lock:
            self._purge_expired()
            count = 0
            for name in names:
                if name in self._store:
                    count += 1
            return count

    def expire(self, name: str, time_sec: int) -> bool:
        with self._lock:
            entry = self._store.get(name)
            if entry is None:
                return False
            val, _ = entry
            self._store[name] = (val, time.time() + time_sec)
            return True

    def ttl(self, name: str) -> int:
        with self._lock:
            entry = self._store.get(name)
            if entry is None:
                return -2
            _, exp = entry
            if exp is None:
                return -1
            remaining = int(exp - time.time())
            return max(0, remaining)

    def keys(self, pattern: str = "*") -> list[bytes]:
        with self._lock:
            self._purge_expired()
            matched = [
                k.encode("utf-8")
                for k in self._store.keys()
                if fnmatch.fnmatch(k, pattern)
            ]
            return matched

    def scan_iter(self, match: str = "*") -> Any:
        with self._lock:
            self._purge_expired()
            matching_keys = [
                k.encode("utf-8")
                for k in self._store.keys()
                if fnmatch.fnmatch(k, match)
            ]
        for k in matching_keys:
            yield k

    def flushdb(self) -> bool:
        with self._lock:
            self._store.clear()
            return True


class RedisManager:
    """Manages Redis client connections, pooling, and fallback lifecycle."""

    def __init__(self) -> None:
        self._client: Any = None
        self._pool: Any = None
        self._lock = threading.Lock()
        self._in_memory_fallback = InMemoryRedisClient()

    def get_client(self) -> Any:
        """Return the active Redis client.

        In production: Requires a live Redis connection. If unreachable or not configured,
        raises a RuntimeError to fail safely and observably.
        In dev/test: Connects to Redis if available, or seamlessly uses the thread-safe
        TTL InMemoryRedisClient.
        """
        if self._client is not None:
            return self._client

        with self._lock:
            if self._client is not None:
                return self._client

            is_production = settings.ENVIRONMENT.lower() == "production"
            redis_url = settings.REDIS_URL

            if is_production:
                if not redis_url:
                    raise RuntimeError(
                        "REDIS_URL must be configured in production for distributed presence."
                    )
                if redis is None:
                    raise RuntimeError(
                        "redis library is required in production but not installed."
                    )
                try:
                    pool = redis.ConnectionPool.from_url(
                        redis_url,
                        max_connections=20,
                        decode_responses=False,
                        socket_timeout=3.0,
                        socket_connect_timeout=3.0,
                    )
                    client = redis.Redis(connection_pool=pool)
                    client.ping()
                    self._pool = pool
                    self._client = client
                    logger.info("Connected to production Redis instance at %s", redis_url)
                    return self._client
                except Exception as e:
                    logger.critical(
                        "Failed to connect to required production Redis: %s", str(e)
                    )
                    raise RuntimeError(
                        f"Production Redis presence is unavailable: {e}"
                    ) from e

            # Dev or Test Environment
            if redis_url and redis is not None:
                try:
                    pool = redis.ConnectionPool.from_url(
                        redis_url,
                        max_connections=10,
                        decode_responses=False,
                        socket_timeout=1.0,
                        socket_connect_timeout=1.0,
                    )
                    client = redis.Redis(connection_pool=pool)
                    client.ping()
                    self._pool = pool
                    self._client = client
                    logger.info("Connected to development Redis at %s", redis_url)
                    return self._client
                except Exception as e:
                    logger.warning(
                        "Redis not reachable at %s (%s). Falling back to in-memory store for dev/test.",
                        redis_url,
                        e,
                    )

            # Fallback for dev / tests without Redis server
            self._client = self._in_memory_fallback
            return self._client

    def reset_for_tests(self) -> None:
        """Reset in-memory storage between test invocations."""
        with self._lock:
            self._in_memory_fallback.flushdb()


redis_manager = RedisManager()


def get_redis_client() -> Any:
    """Convenience accessor for Redis client."""
    return redis_manager.get_client()
