from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import RequireOperatorPermission, RequireRole, get_db
from app.core.i18n import DEFAULT_LOCALE, resolve_locale
from app.models.operator import OperationalPermission
from app.models.user import User, UserRole
from app.schemas.localization import (
    TranslationCreateRequest,
    TranslationResponse,
    TranslationReviewRequest,
)
from app.domain.governance.translation_service import TranslationService

router = APIRouter(prefix="/localization", tags=["localization"])


@router.get("/messages")
def get_localized_messages(
    request: Request,
    locale: str | None = Query(None, description="Optional locale tag (e.g. hi-IN, en-IN)"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieves consolidated dictionary for the requested or resolved locale."""
    target_locale = locale or resolve_locale(request)
    service = TranslationService(db)
    messages = service.get_messages_dictionary(target_locale)
    return {
        "locale": target_locale,
        "messages": messages,
    }


@router.get("/locales")
def list_supported_locales(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Lists supported locales, coverage completeness, and approval metrics."""
    service = TranslationService(db)
    return service.get_localization_summary()


@router.post("/messages", response_model=TranslationResponse, status_code=status.HTTP_201_CREATED)
def register_translation_message(
    req: TranslationCreateRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.COMPLIANCE_OPERATIONS)),
    db: Session = Depends(get_db),
):
    """Registers or updates a translation message awaiting review."""
    service = TranslationService(db)
    return service.register_translation(
        source_key=req.source_key,
        source_text=req.source_text,
        locale=req.locale,
        translation=req.translation,
        actor=current_user,
        version=req.version,
        metadata_=req.metadata_,
    )


@router.post("/messages/{message_id}/review", response_model=TranslationResponse)
def review_translation_message(
    message_id: UUID,
    req: TranslationReviewRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.COMPLIANCE_OPERATIONS)),
    db: Session = Depends(get_db),
):
    """Records human/legal review approval for a translation message."""
    service = TranslationService(db)
    return service.review_translation(
        message_id=message_id,
        approved=req.approved,
        actor=current_user,
        review_status=req.review_status,
        review_notes=req.review_notes,
    )
