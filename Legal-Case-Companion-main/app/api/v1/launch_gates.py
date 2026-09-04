import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user, get_db
from app.models.user import User
from app.services.launch_gate_service import LaunchGateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/launch-gates", tags=["launch-gates"])


@router.get(
    "/evaluation",
    summary="Get machine-readable public-launch gate evaluation",
)
def get_launch_gate_evaluation(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = LaunchGateService(db)
    return service.evaluate_all_gates()
