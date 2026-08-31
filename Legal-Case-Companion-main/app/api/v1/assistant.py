import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.auth import limiter
from app.models.user import User
from app.schemas.assistant import CaseAssistantQueryRequest, CaseAssistantQueryResponse
from app.services.assistant_service import CaseAssistantService

router = APIRouter(prefix="/cases", tags=["case-assistant"])


@router.post("/{case_id}/assistant/query", response_model=CaseAssistantQueryResponse)
@limiter.limit("15/minute")
def query_case_assistant(
    request: Request,
    case_id: uuid.UUID,
    payload: CaseAssistantQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseAssistantQueryResponse:
    """Case-aware, evidence-grounded legal assistant query endpoint.

    Executes case authorization, hybrid search, untrusted evidence boundary wrapping,
    structured model generation, citation validation, and claim verification.
    """
    service = CaseAssistantService(db)
    return service.query_case_assistant(current_user, case_id, payload)
