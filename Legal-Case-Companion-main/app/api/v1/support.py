from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import RequireOperatorPermission, get_current_user, get_db
from app.models.operator import OperationalPermission
from app.models.support import SupportCaseSeverity, SupportCaseStatus
from app.models.user import User
from app.schemas.support import (
    SupportCaseCreateRequest,
    SupportCaseEscalateRequest,
    SupportCaseResolveRequest,
    SupportCaseResponse,
)
from app.services.support_service import SupportService

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/cases", response_model=SupportCaseResponse, status_code=status.HTTP_201_CREATED)
def create_support_case(
    req: SupportCaseCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submits a customer support ticket under zero-trust evidence isolation."""
    service = SupportService(db)
    return service.create_case(
        category=req.category,
        subject=req.subject,
        description=req.description,
        user=current_user,
        user_scope=current_user.role.value,
        workflow=req.workflow,
        severity=req.severity,
        metadata_=req.metadata_,
    )


@router.get("/cases", response_model=list[SupportCaseResponse])
def list_support_cases(
    status_filter: SupportCaseStatus | None = Query(None, alias="status"),
    category_filter: str | None = Query(None, alias="category"),
    severity_filter: SupportCaseSeverity | None = Query(None, alias="severity"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists support tickets (caller's tickets for regular users, all tickets for support operators)."""
    service = SupportService(db)
    user_id_filter = current_user.id if current_user.role.value != "ADMIN" else None
    return service.list_cases(
        user_id=user_id_filter,
        status=status_filter,
        category=category_filter,
        severity=severity_filter,
        skip=skip,
        limit=limit,
    )


@router.get("/cases/{case_id}", response_model=SupportCaseResponse)
def get_support_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves single support ticket metadata."""
    service = SupportService(db)
    case = service.get_case(case_id)
    if current_user.role.value != "ADMIN" and case.user_id != current_user.id:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Not authorized to view this support ticket.")
    return case


@router.post("/cases/{case_id}/resolve", response_model=SupportCaseResponse)
def resolve_support_case(
    case_id: str,
    req: SupportCaseResolveRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.USER_SUPPORT)),
    db: Session = Depends(get_db),
):
    """Resolves a support case with formal resolution code and operator notes."""
    service = SupportService(db)
    return service.resolve_case(
        identifier=case_id,
        resolution_code=req.resolution_code,
        resolution_notes=req.resolution_notes,
        actor=current_user,
    )


@router.post("/cases/{case_id}/escalate", response_model=SupportCaseResponse)
def escalate_support_case(
    case_id: str,
    req: SupportCaseEscalateRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.USER_SUPPORT)),
    db: Session = Depends(get_db),
):
    """Escalates a support case to Tier 2 (Engineering) or Tier 3 (Compliance/Legal)."""
    service = SupportService(db)
    return service.escalate_case(
        identifier=case_id,
        target_level=req.target_level,
        actor=current_user,
        notes=req.notes,
    )


@router.get("/analytics")
def get_support_analytics(
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.USER_SUPPORT)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieves operational support metrics, resolution times, and recurring friction hotspots."""
    service = SupportService(db)
    return service.get_support_analytics()


@router.get("/enhanced-analytics")
def get_enhanced_support_analytics(
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.USER_SUPPORT)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieves advanced Phase 10 support metrics including response times, reopen rate, and ratios."""
    service = SupportService(db)
    return service.get_enhanced_support_analytics()


@router.get("/cases/{case_id}/messages")
def get_support_case_messages(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieves communication thread on a support ticket under zero-trust note isolation."""
    service = SupportService(db)
    case = service.get_case(case_id)
    if current_user.role.value != "ADMIN" and case.user_id != current_user.id:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Not authorized to view messages on this support ticket.")

    msgs = service.get_case_messages(case_id, current_user)
    return [
        {
            "id": str(m.id),
            "sender_role": m.sender_role,
            "sender_name": m.sender.full_name if m.sender else ("Support Operator" if m.sender_role == "OPERATOR" else "User"),
            "message_text": m.message_text,
            "is_internal_note": m.is_internal_note,
            "created_at": m.created_at.isoformat(),
        }
        for m in msgs
    ]


@router.post("/cases/{case_id}/messages", status_code=status.HTTP_201_CREATED)
def add_support_case_message(
    case_id: str,
    message_text: str = Query(..., min_length=1),
    is_internal_note: bool = Query(False),
    new_status: SupportCaseStatus | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Adds a customer-operator communication entry or internal note to a support ticket."""
    service = SupportService(db)
    case = service.get_case(case_id)
    if current_user.role.value != "ADMIN" and case.user_id != current_user.id:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Not authorized to post messages on this support ticket.")

    # Only admins can create internal notes
    internal = is_internal_note if current_user.role.value == "ADMIN" else False
    msg = service.add_case_message(
        identifier=case_id,
        message_text=message_text,
        sender=current_user,
        is_internal_note=internal,
        new_status=new_status,
    )
    return {
        "status": "CREATED",
        "message_id": str(msg.id),
        "sender_role": msg.sender_role,
        "created_at": msg.created_at.isoformat(),
    }
