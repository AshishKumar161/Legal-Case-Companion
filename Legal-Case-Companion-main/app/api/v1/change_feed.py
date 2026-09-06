from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.change_feed_service import ChangeFeedService

router = APIRouter(prefix="/feed", tags=["change_feed"])


@router.get("/what-changed")
def get_what_changed_since_last_visit(
    limit: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Returns deterministic delta events that occurred since the user's last acknowledged checkpoint.

    Covers hearing date changes, court status updates, new orders, documents,
    counsel requests, messages, and payments. Zero AI.
    """
    service = ChangeFeedService(db)
    return service.get_what_changed(user=current_user, limit=limit)


@router.post("/what-changed/acknowledge", status_code=status.HTTP_200_OK)
def acknowledge_what_changed(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Updates the user's last acknowledged checkpoint to the current UTC timestamp."""
    service = ChangeFeedService(db)
    return service.acknowledge_changes(user=current_user)
