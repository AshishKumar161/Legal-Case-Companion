import contextlib
import hashlib
import logging
import time
from collections.abc import Generator

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


class DistributedJobLock:
    """
    Distributed lock mechanism for background workers (e.g. reminder dispatch, overdue jobs).
    Guarantees that when multiple workers run concurrently, only one executes the job.
    Supports:
    1. Redis/In-Memory atomic set with NX and TTL expiration.
    2. Optional PostgreSQL session advisory lock if DB session is provided.
    """

    def __init__(self, lock_key: str, ttl_seconds: int = 300, db: Session | None = None) -> None:
        self.lock_key = f"job_lock:{lock_key}"
        self.ttl_seconds = ttl_seconds
        self.db = db
        self.acquired = False
        self._token = str(time.time())

    def acquire(self) -> bool:
        # 1. Try DB advisory lock if DB is postgres
        if self.db is not None and self.db.bind is not None:
            dialect_name = self.db.bind.dialect.name
            if dialect_name == "postgresql":
                try:
                    # Convert key to a signed 64-bit int for pg_try_advisory_lock
                    key_hash = int(hashlib.sha256(self.lock_key.encode()).hexdigest()[:15], 16) - (1 << 59)
                    res = self.db.execute(
                        text("SELECT pg_try_advisory_lock(:lock_id)"),
                        {"lock_id": key_hash},
                    ).scalar()
                    if not res:
                        logger.info("PostgreSQL advisory lock %s already held by another worker", self.lock_key)
                        return False
                except Exception as e:
                    logger.warning("Failed checking PostgreSQL advisory lock: %s", e)

        # 2. Primary / complementary Redis distributed lock
        try:
            client = get_redis_client()
            acquired = client.set(self.lock_key, self._token, nx=True, ex=self.ttl_seconds)
            self.acquired = bool(acquired)
            if not self.acquired:
                logger.info("Distributed lock %s already held by another worker", self.lock_key)
            return self.acquired
        except Exception as e:
            logger.warning("Error acquiring distributed lock %s: %s", self.lock_key, e)
            return False

    def release(self) -> None:
        if self.acquired:
            try:
                client = get_redis_client()
                val = client.get(self.lock_key)
                if val is not None:
                    stored_token = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    if stored_token == self._token:
                        client.delete(self.lock_key)
            except Exception as e:
                logger.warning("Error releasing distributed lock %s: %s", self.lock_key, e)
            finally:
                self.acquired = False

        if self.db is not None and self.db.bind is not None:
            dialect_name = self.db.bind.dialect.name
            if dialect_name == "postgresql":
                try:
                    key_hash = int(hashlib.sha256(self.lock_key.encode()).hexdigest()[:15], 16) - (1 << 59)
                    self.db.execute(
                        text("SELECT pg_advisory_unlock(:lock_id)"),
                        {"lock_id": key_hash},
                    )
                except Exception as e:
                    logger.warning("Error releasing PostgreSQL advisory lock: %s", e)


@contextlib.contextmanager
def job_lock(lock_key: str, ttl_seconds: int = 300, db: Session | None = None) -> Generator[bool, None, None]:
    """Context manager for distributed job locking. Yields True if lock acquired, False otherwise."""
    dist_lock = DistributedJobLock(lock_key, ttl_seconds=ttl_seconds, db=db)
    is_acquired = dist_lock.acquire()
    try:
        yield is_acquired
    finally:
        if is_acquired:
            dist_lock.release()
