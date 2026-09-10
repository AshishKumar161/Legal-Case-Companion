from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationBulkDeleteRequest,
    NotificationBulkDeleteResponse,
    NotificationBulkReadRequest,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationReadAllResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.schemas.pagination import PaginatedResponse
from app.domain.notifications.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=PaginatedResponse[NotificationResponse])
def list_notifications(
    is_read: bool | None = None,
    category: str | None = None,
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List notifications for the current authenticated user.
    Supports filtering by read/unread status, category, keyword search, and bounded pagination.
    """
    service = NotificationService(db)
    return service.list_notifications(
        current_user,
        is_read=is_read,
        category=category,
        search=search,
        skip=skip,
        limit=limit,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get total count of unread notifications for the current user.
    """
    service = NotificationService(db)
    count = service.get_unread_count(current_user)
    return UnreadCountResponse(unread_count=count)


@router.get("/preferences", response_model=NotificationPreferenceResponse)
def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current notification preferences for the authenticated user.
    """
    service = NotificationService(db)
    return service.get_preferences(user=current_user)


@router.patch("/preferences", response_model=NotificationPreferenceResponse)
def update_notification_preferences(
    req: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update notification preferences for the authenticated user.
    """
    service = NotificationService(db)
    return service.update_preferences(current_user, req)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_as_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark a notification as read.
    """
    service = NotificationService(db)
    return service.mark_as_read(current_user, notification_id)


@router.post("/{notification_id}/unread", response_model=NotificationResponse)
def mark_as_unread(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark a notification as unread.
    """
    service = NotificationService(db)
    return service.mark_as_unread(current_user, notification_id)


@router.post("/read-all", response_model=NotificationReadAllResponse)
def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark all unread notifications for the current user as read.
    """
    service = NotificationService(db)
    updated = service.mark_all_as_read(current_user)
    return NotificationReadAllResponse(updated_count=updated)


@router.post("/bulk-read", response_model=NotificationReadAllResponse)
def bulk_mark_as_read(
    req: NotificationBulkReadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark a specific list of notifications as read with strict user recipient isolation.
    """
    service = NotificationService(db)
    updated = service.bulk_mark_as_read(current_user, req.notification_ids)
    return NotificationReadAllResponse(updated_count=updated)


@router.post("/bulk-delete", response_model=NotificationBulkDeleteResponse)
def bulk_delete_notifications(
    req: NotificationBulkDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Soft-delete a specific list of notifications with strict recipient ownership isolation.
    """
    service = NotificationService(db)
    deleted = service.bulk_delete_notifications(current_user, req.notification_ids)
    return NotificationBulkDeleteResponse(deleted_count=deleted)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete (soft-delete) a notification.
    """
    service = NotificationService(db)
    service.delete_notification(current_user, notification_id)
