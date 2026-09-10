import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.auth import limiter
from app.models.user import User
from app.schemas.ai import (
    AIConversationCreate,
    AIConversationResponse,
    AIConversationUpdate,
    AIMessageRequest,
    AIMessageResponse,
)
from app.domain.ai.ai_conversation_service import AIConversationService

router = APIRouter(prefix="/cases", tags=["ai-conversations"])


@router.post(
    "/{case_id}/ai/conversations",
    response_model=AIConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
def create_conversation(
    request: Request,
    case_id: uuid.UUID,
    req: AIConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates a new AI conversation scoped to the authorized case."""
    service = AIConversationService(db)
    return service.create_conversation(current_user, case_id, req.title)


@router.get("/{case_id}/ai/conversations", response_model=list[AIConversationResponse])
@limiter.limit("20/minute")
def list_conversations(
    request: Request,
    case_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists active conversations for the authorized case."""
    service = AIConversationService(db)
    return service.list_conversations(current_user, case_id, limit, offset)


@router.get(
    "/{case_id}/ai/conversations/{conversation_id}",
    response_model=AIConversationResponse,
)
@limiter.limit("30/minute")
def get_conversation(
    request: Request,
    case_id: uuid.UUID,
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves a single AI conversation by ID."""
    service = AIConversationService(db)
    return service.get_conversation(current_user, case_id, conversation_id)


@router.patch(
    "/{case_id}/ai/conversations/{conversation_id}",
    response_model=AIConversationResponse,
)
@limiter.limit("15/minute")
def update_conversation(
    request: Request,
    case_id: uuid.UUID,
    conversation_id: uuid.UUID,
    req: AIConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates an AI conversation title or status."""
    service = AIConversationService(db)
    return service.update_conversation(
        current_user, case_id, conversation_id, req.title, req.status
    )


@router.delete(
    "/{case_id}/ai/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("15/minute")
def delete_conversation(
    request: Request,
    case_id: uuid.UUID,
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-deletes an AI conversation."""
    service = AIConversationService(db)
    service.delete_conversation(current_user, case_id, conversation_id)


@router.post(
    "/{case_id}/ai/conversations/{conversation_id}/messages",
    response_model=AIMessageResponse,
)
@limiter.limit("15/minute")
def send_message(
    request: Request,
    case_id: uuid.UUID,
    conversation_id: uuid.UUID,
    req: AIMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sends a query to the AI conversation, retrieval-grounded and injection-secured."""
    service = AIConversationService(db)
    return service.send_message(current_user, case_id, conversation_id, req)


@router.get(
    "/{case_id}/ai/conversations/{conversation_id}/messages",
    response_model=list[AIMessageResponse],
)
@limiter.limit("20/minute")
def list_messages(
    request: Request,
    case_id: uuid.UUID,
    conversation_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves message history for the AI conversation."""
    service = AIConversationService(db)
    return service.list_messages(current_user, case_id, conversation_id, limit, offset)
