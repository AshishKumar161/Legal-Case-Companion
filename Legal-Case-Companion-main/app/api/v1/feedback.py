import urllib.parse
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.api.deps import RequireRole, get_current_user, get_db
from app.core.exceptions import ResourceNotFoundError
from app.core.identifiers import generate_uuid7
from app.models.feedback import FeedbackCategory, PilotFeedback
from app.models.user import User, UserRole
from app.schemas.feedback import (
    PilotFeedbackCreate,
    PilotFeedbackResponse,
    PilotFeedbackUpdate,
)

router = APIRouter(prefix="/feedback", tags=["Feedback"])


def _sanitize_page_url(raw_url: str) -> str:
    """Sanitize URL to strip sensitive query parameters (PII, tokens, secret params) before persistence."""
    try:
        parsed = urllib.parse.urlparse(raw_url)
        # Keep path only to prevent sensitive search params / case tokens from leaking into feedback logs
        clean_path = parsed.path or "/"
        if parsed.fragment:
            clean_path = f"{clean_path}#{parsed.fragment}"
        return clean_path[:500]
    except (ValueError, TypeError, AttributeError):
        return "/"


@router.post(
    "",
    response_model=PilotFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit lightweight privacy-preserving pilot feedback",
)
def submit_pilot_feedback(
    payload: PilotFeedbackCreate,
    current_user: User = Depends(get_current_user),
    user_agent: str | None = Header(None),
    db: Session = Depends(get_db),
):
    clean_url = _sanitize_page_url(payload.page_url)
    clean_desc = payload.description.strip()

    feedback = PilotFeedback(
        id=generate_uuid7(),
        user_id=current_user.id if current_user else None,
        category=payload.category,
        description=clean_desc,
        page_url=clean_url,
        user_agent=user_agent[:500] if user_agent else None,
        status="NEW",
        priority="P2",
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return PilotFeedbackResponse(
        id=feedback.id,
        user_id=feedback.user_id,
        user_email=current_user.email if current_user else None,
        category=feedback.category,
        description=feedback.description,
        page_url=feedback.page_url,
        status=feedback.status,
        priority=feedback.priority,
        resolution_notes=feedback.resolution_notes,
        created_at=feedback.created_at,
    )


@router.get(
    "",
    response_model=list[PilotFeedbackResponse],
    summary="Admin review of pilot user feedback",
)
def list_pilot_feedback(
    category: FeedbackCategory | None = None,
    priority: str | None = None,
    status_: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _admin: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    query = db.query(PilotFeedback).filter(PilotFeedback.deleted_at.is_(None))
    if category:
        query = query.filter(PilotFeedback.category == category)
    if priority:
        query = query.filter(PilotFeedback.priority == priority)
    if status_:
        query = query.filter(PilotFeedback.status == status_)

    items = query.order_by(PilotFeedback.created_at.desc()).offset(skip).limit(limit).all()

    return [
        PilotFeedbackResponse(
            id=f.id,
            user_id=f.user_id,
            user_email=f.user.email if f.user else None,
            category=f.category,
            description=f.description,
            page_url=f.page_url,
            status=f.status,
            priority=f.priority,
            resolution_notes=f.resolution_notes,
            created_at=f.created_at,
        )
        for f in items
    ]


@router.patch(
    "/{feedback_id}",
    response_model=PilotFeedbackResponse,
    summary="Admin triage and resolution of pilot feedback",
)
def update_pilot_feedback(
    feedback_id: UUID,
    payload: PilotFeedbackUpdate,
    _admin: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    fb = (
        db.query(PilotFeedback)
        .filter(PilotFeedback.id == feedback_id, PilotFeedback.deleted_at.is_(None))
        .first()
    )
    if not fb:
        raise ResourceNotFoundError("Feedback item not found")

    if payload.status is not None:
        fb.status = payload.status
    if payload.priority is not None:
        fb.priority = payload.priority
    if payload.resolution_notes is not None:
        fb.resolution_notes = payload.resolution_notes

    db.commit()
    db.refresh(fb)

    return PilotFeedbackResponse(
        id=fb.id,
        user_id=fb.user_id,
        user_email=fb.user.email if fb.user else None,
        category=fb.category,
        description=fb.description,
        page_url=fb.page_url,
        status=fb.status,
        priority=fb.priority,
        resolution_notes=fb.resolution_notes,
        created_at=fb.created_at,
    )
