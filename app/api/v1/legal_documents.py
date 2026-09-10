from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import RequireOperatorPermission, get_current_user, get_db
from app.models.legal_document import LegalDocumentType
from app.models.operator import OperationalPermission
from app.models.user import User
from app.domain.documents.legal_document_service import LegalDocumentService

router = APIRouter(prefix="/legal-documents", tags=["legal-documents"])


class PublishDocumentRequest(BaseModel):
    document_type: LegalDocumentType
    version: str = Field(..., min_length=1, max_length=50)
    locale: str = Field(default="en-IN", min_length=2, max_length=20)
    title: str = Field(..., min_length=3, max_length=255)
    content: str = Field(..., min_length=10)
    effective_at: datetime
    summary_of_changes: str | None = None


class ConsentRecordRequest(BaseModel):
    document_type: LegalDocumentType
    version: str = Field(..., min_length=1, max_length=50)
    locale: str = Field(default="en-IN", min_length=2, max_length=20)


@router.get("/{document_type}/current")
def get_current_document_version(
    document_type: LegalDocumentType,
    locale: str = Query("en-IN"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieves current published version of a legal policy document in the requested locale."""
    service = LegalDocumentService(db)
    doc = service.get_current_document(document_type, locale=locale)
    return {
        "id": str(doc.id),
        "document_type": doc.document_type.value,
        "version": doc.version,
        "locale": doc.locale,
        "title": doc.title,
        "content": doc.content,
        "effective_at": doc.effective_at.isoformat(),
        "summary_of_changes": doc.summary_of_changes,
    }


@router.post("/publish", status_code=status.HTTP_201_CREATED)
def publish_document_version(
    req: PublishDocumentRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.COMPLIANCE_OPERATIONS)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Publishes a new versioned legal policy document with explicit counsel approval."""
    service = LegalDocumentService(db)
    doc = service.publish_version(
        document_type=req.document_type,
        version=req.version,
        title=req.title,
        content=req.content,
        effective_at=req.effective_at,
        actor=current_user,
        locale=req.locale,
        summary_of_changes=req.summary_of_changes,
    )
    return {"status": "PUBLISHED", "version": doc.version, "document_type": doc.document_type.value}


@router.post("/accept", status_code=status.HTTP_200_OK)
def accept_document_terms(
    req: ConsentRecordRequest,
    request: Request,
    user_agent: str | None = Header(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Records non-repudiable user consent for a specific policy version."""
    service = LegalDocumentService(db)
    client_ip = request.client.host if request.client else None
    consent = service.record_user_consent(
        user=current_user,
        document_type=req.document_type,
        version=req.version,
        locale=req.locale,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    return {
        "status": "CONSENT_RECORDED",
        "consent_id": str(consent.id),
        "accepted_at": consent.accepted_at.isoformat(),
    }


@router.get("/consents/my")
def list_my_consents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Lists current user's historical accepted policy versions."""
    service = LegalDocumentService(db)
    consents = service.list_user_consents(current_user.id)
    return [
        {
            "id": str(c.id),
            "document_type": c.document_type.value,
            "version": c.version,
            "locale": c.locale,
            "accepted_at": c.accepted_at.isoformat(),
        }
        for c in consents
    ]
