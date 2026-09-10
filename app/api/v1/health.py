import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.redis import get_redis_client
from app.core.storage import get_storage_provider
from app.models.job import BackgroundJob, JobStatus
from app.models.outbox import OutboxEvent, OutboxStatus
from app.domain.evidence.scanner_service import DefaultMalwareScanner

router = APIRouter(tags=["health"])
root_router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", status_code=status.HTTP_200_OK)
@root_router.get("/health", status_code=status.HTTP_200_OK)
@router.get("/health/live", status_code=status.HTTP_200_OK)
@root_router.get("/health/live", status_code=status.HTTP_200_OK)
@root_router.get("/liveness", status_code=status.HTTP_200_OK)
def liveness_check():
    """Liveness probe.

    Indicates whether the application process is running.
    Does not verify external dependencies to prevent cascading restarts.
    """
    return {"status": "alive", "service": "lcc-backend", "environment": settings.ENVIRONMENT}


@router.get("/health/ready")
@root_router.get("/health/ready")
@root_router.get("/ready")
@root_router.get("/readiness")
def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe.

    Verifies that core database connectivity is operational to safely serve traffic.
    """
    try:
        t0 = time.perf_counter()
        db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ready",
                "database": "connected",
                "latency_ms": latency_ms,
                "environment": settings.ENVIRONMENT,
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": "disconnected",
                "error": "Database connectivity check failed",
            },
        )


@router.get("/health/details")
@root_router.get("/health/details")
def dependency_health_check(db: Session = Depends(get_db)):
    """Comprehensive dependency health inspection.

    Monitors PostgreSQL, Redis, Storage, Malware Scanner, and Background Job queues.
    Sanitized output: never exposes passwords, secrets, or internal connection strings.
    """
    dependencies: dict[str, Any] = {}
    is_degraded = False
    is_unhealthy = False

    # 1. PostgreSQL Health Check
    try:
        t0 = time.perf_counter()
        db.execute(text("SELECT 1"))
        db_latency = round((time.perf_counter() - t0) * 1000, 2)
        dependencies["database"] = {
            "status": "connected",
            "latency_ms": db_latency,
        }
    except Exception:  # noqa: BLE001
        dependencies["database"] = {"status": "disconnected", "error": "Database unreachable"}
        is_unhealthy = True

    # 2. Redis Health Check
    try:
        t0 = time.perf_counter()
        redis_client = get_redis_client()
        ping_ok = redis_client.ping()
        redis_latency = round((time.perf_counter() - t0) * 1000, 2)
        dependencies["redis"] = {
            "status": "connected" if ping_ok else "unresponsive",
            "latency_ms": redis_latency,
            "mock_mode": getattr(redis_client, "is_mock", False),
        }
    except Exception:  # noqa: BLE001
        dependencies["redis"] = {"status": "degraded", "note": "Operating with graceful degradation"}
        is_degraded = True

    # 3. Storage Provider Check
    try:
        storage = get_storage_provider()
        provider_name = storage.__class__.__name__
        dependencies["storage"] = {
            "status": "operational",
            "provider": provider_name,
        }
    except Exception:  # noqa: BLE001
        dependencies["storage"] = {"status": "degraded"}
        is_degraded = True

    # 4. Malware Scanner Check
    try:
        scanner = DefaultMalwareScanner()
        dependencies["scanner"] = {
            "status": "operational",
            "clamav_available": scanner.is_clamav_available(),
        }
    except Exception:  # noqa: BLE001
        dependencies["scanner"] = {"status": "heuristic_only"}
        is_degraded = True

    # 5. Background Jobs & Outbox Health
    try:
        pending_jobs = (
            db.query(func.count(BackgroundJob.id))
            .filter(BackgroundJob.status == JobStatus.PENDING)
            .scalar()
            or 0
        )
        dead_letter_jobs = (
            db.query(func.count(BackgroundJob.id))
            .filter(BackgroundJob.status == JobStatus.DEAD_LETTER)
            .scalar()
            or 0
        )
        pending_outbox = (
            db.query(func.count(OutboxEvent.id))
            .filter(OutboxEvent.status == OutboxStatus.PENDING)
            .scalar()
            or 0
        )
        dead_letter_outbox = (
            db.query(func.count(OutboxEvent.id))
            .filter(OutboxEvent.status == OutboxStatus.DEAD_LETTER)
            .scalar()
            or 0
        )
        running_jobs = (
            db.query(func.count(BackgroundJob.id))
            .filter(BackgroundJob.status == JobStatus.RUNNING)
            .scalar()
            or 0
        )
        retrying_jobs = (
            db.query(func.count(BackgroundJob.id))
            .filter(BackgroundJob.status == JobStatus.RETRYING)
            .scalar()
            or 0
        )
        dependencies["queues"] = {
            "background_jobs_pending": pending_jobs,
            "background_jobs_running": running_jobs,
            "background_jobs_retrying": retrying_jobs,
            "background_jobs_dead_letter": dead_letter_jobs,
            "outbox_events_pending": pending_outbox,
            "outbox_events_dead_letter": dead_letter_outbox,
        }
    except Exception:  # noqa: BLE001
        dependencies["queues"] = {"status": "unavailable"}

    overall_status = "unhealthy" if is_unhealthy else ("degraded" if is_degraded else "healthy")
    http_status = (
        status.HTTP_503_SERVICE_UNAVAILABLE if is_unhealthy else status.HTTP_200_OK
    )

    return JSONResponse(
        status_code=http_status,
        content={
            "status": overall_status,
            "version": settings.APP_VERSION,
            "release_id": settings.RELEASE_ID,
            "environment": settings.ENVIRONMENT,
            "dependencies": dependencies,
        },
    )
