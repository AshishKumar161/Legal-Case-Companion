from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import RequireRole, get_db
from app.models.user import User, UserRole
from app.schemas.audit import AuditEventResponse
from app.schemas.pagination import PaginatedResponse
from app.domain.users.admin_service import AdminService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=PaginatedResponse[AuditEventResponse])
def get_audit_logs(
    event_type: str | None = None,
    actor_user_id: UUID | None = None,
    entity_type: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """
    Query system audit events. Restricted strictly to active administrators.
    """
    admin_service = AdminService(db)
    return admin_service.list_audit_logs(
        admin_user=current_user,
        event_type=event_type,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        skip=skip,
        limit=limit,
    )
