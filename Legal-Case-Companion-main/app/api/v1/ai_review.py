from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import RequireOperatorPermission, RequireRole, get_current_user, get_db
from app.models.ai_review import AIReviewCategory, AIReviewStatus
from app.models.operator import OperationalPermission
from app.models.user import User, UserRole
from app.schemas.ai_review import (
    AIReviewActionRequest,
    AIReviewCreateRequest,
    AIReviewResponse,
)
from app.services.ai_evaluation_service import AIEvaluationService
from app.services.ai_review_service import AIReviewService

router = APIRouter(prefix="/ai/reviews", tags=["ai-reviews"])


@router.post("", response_model=AIReviewResponse, status_code=status.HTTP_201_CREATED)
def submit_ai_review(
    req: AIReviewCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submits an AI output defect or grounding discrepancy for human review."""
    service = AIReviewService(db)
    return service.submit_review(
        reviewer=current_user,
        category=req.category,
        severity=req.severity,
        review_outcome=req.review_outcome,
        original_prompt_snippet=req.original_prompt_snippet,
        original_answer_snippet=req.original_answer_snippet,
        corrected_interpretation=req.corrected_interpretation,
        message_id=req.message_id,
        conversation_id=req.conversation_id,
        model_version=req.model_version,
        retrieval_config_version=req.retrieval_config_version,
        linked_release_id=req.linked_release_id,
        linked_incident_id=req.linked_incident_id,
    )


@router.get("", response_model=list[AIReviewResponse])
def list_ai_reviews(
    status_filter: AIReviewStatus | None = Query(None, alias="status"),
    category_filter: AIReviewCategory | None = Query(None, alias="category"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.COMPLIANCE_OPERATIONS)),
    db: Session = Depends(get_db),
):
    """Lists human review records for AI outputs."""
    service = AIReviewService(db)
    return service.list_reviews(status=status_filter, category=category_filter, skip=skip, limit=limit)


@router.get("/{review_id}", response_model=AIReviewResponse)
def get_ai_review(
    review_id: str,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.COMPLIANCE_OPERATIONS)),
    db: Session = Depends(get_db),
):
    """Retrieves a specific AI human review record."""
    service = AIReviewService(db)
    return service.get_review(review_id)


@router.post("/{review_id}/action", response_model=AIReviewResponse)
def action_ai_review(
    review_id: str,
    req: AIReviewActionRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.COMPLIANCE_OPERATIONS)),
    db: Session = Depends(get_db),
):
    """Records corrective action taken following human review of an AI defect."""
    service = AIReviewService(db)
    return service.action_review(
        identifier=review_id,
        action_taken=req.action_taken,
        actor=current_user,
    )


@router.get("/analytics/metrics")
def get_ai_review_metrics(
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieves aggregate defect rates and category breakdowns from human AI reviews."""
    service = AIReviewService(db)
    return service.get_review_metrics()


@router.post("/benchmark/run")
def run_ai_benchmark(
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
) -> dict[str, Any]:
    """Executes the standard 20-scenario Indian legal benchmark test suite against the AI provider."""
    service = AIEvaluationService()
    return service.run_benchmark()
