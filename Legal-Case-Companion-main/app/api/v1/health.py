import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db

router = APIRouter(tags=["health"])
root_router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", status_code=status.HTTP_200_OK)
@root_router.get("/health", status_code=status.HTTP_200_OK)
@router.get("/health/live", status_code=status.HTTP_200_OK)
@root_router.get("/health/live", status_code=status.HTTP_200_OK)
def liveness_check():
    """Liveness probe.

    Indicates whether the application process is running.
    Does not verify external dependencies.
    """
    return {"status": "alive"}


@router.get("/health/ready")
@root_router.get("/health/ready")
@root_router.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe.

    Verifies that required infrastructure (e.g., PostgreSQL) is available.
    """
    try:
        # Fast query to verify database connectivity
        db.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ready", "database": "connected"},
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "database": "disconnected"},
        )
