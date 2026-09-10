import uuid
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.domain.cases.case_attention_service import CaseAttentionService

router = APIRouter(prefix="/cases", tags=["case_attention"])


@router.get("/{case_id}/attention")
def get_case_attention(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Evaluates the 6 operational attention dimensions for a case:

    Hearing, Documents, Tasks, Court Synchronization, Communication, Payment.
    Synthesizes the single primary NextStep. Strictly NO AI risk scores.
    """
    service = CaseAttentionService(db)
    return service.evaluate_case_attention(case_id=case_id, user=current_user)
