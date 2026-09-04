import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.profile import (
    LawyerVerificationCreate,
    LawyerVerificationResponse,
    LawyerVerificationReviewRequest,
)
from app.services.lawyer_verification_service import LawyerVerificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/verification", tags=["verification"])


@router.post(
    "/lawyer/submit",
    response_model=LawyerVerificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit advocate Bar Council verification",
)
def submit_lawyer_verification(
    payload: LawyerVerificationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = LawyerVerificationService(db)
    return service.submit_verification(
        user=current_user,
        enrollment_number=payload.enrollment_number,
        state_bar_council=payload.state_bar_council,
        evidence_document_id=payload.evidence_document_id,
        is_reverification=payload.is_reverification,
    )


@router.post(
    "/admin/{verification_id}/review",
    response_model=LawyerVerificationResponse,
    summary="Review and approve/reject advocate verification",
)
def review_lawyer_verification(
    verification_id: uuid.UUID,
    payload: LawyerVerificationReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = LawyerVerificationService(db)
    return service.review_verification(
        reviewer=current_user,
        verification_id=verification_id,
        approved=payload.approved,
        rejection_category=payload.rejection_category,
        validity_days=payload.validity_days,
    )


@router.get(
    "/discovery/transparency",
    summary="Explainable discovery ranking transparency information",
)
def get_discovery_ranking_transparency(
    db: Session = Depends(get_db),
):
    service = LawyerVerificationService(db)
    return service.get_discovery_ranking_explanation()
