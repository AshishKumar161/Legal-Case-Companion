import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.auth import limiter
from app.models.user import User
from app.schemas.ai import AIResearchRequest, AIResearchResponse
from app.domain.ai.ai_budget_service import AIBudgetService
from app.domain.ai.ai_research_service import AIResearchService

router = APIRouter(prefix="/cases", tags=["ai"])


@router.post("/{case_id}/ai/research", response_model=AIResearchResponse)
@limiter.limit("10/minute")
def generate_ai_research(
    request: Request,
    case_id: uuid.UUID,
    req: AIResearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Evidence-grounded AI research endpoint scoped strictly to the given case_id.
    """
    budget_service = AIBudgetService(db)
    budget_service.check_and_consume_budget(current_user)

    service = AIResearchService(db)
    return service.generate_research(current_user, case_id, req)
