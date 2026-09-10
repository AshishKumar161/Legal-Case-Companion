import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.auth import limiter
from app.models.user import User
from app.schemas.search import CaseSearchRequest, CaseSearchResponse
from app.domain.ai.retrieval_service import RetrievalService

router = APIRouter(tags=["search"])


@router.post(
    "/cases/{case_id}/search",
    response_model=CaseSearchResponse,
)
@limiter.limit("30/minute")
def search_case_evidence(
    request: Request,
    case_id: uuid.UUID,
    req: CaseSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Executes case-scoped hybrid, lexical, or semantic search across active case documents.

    Returns ranked evidence chunks preserving full document provenance.
    """
    retrieval_service = RetrievalService(db)
    return retrieval_service.search_case_evidence(current_user, case_id, req)
