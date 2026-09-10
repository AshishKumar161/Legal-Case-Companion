from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import RequireOperatorPermission, get_db
from app.models.compliance import ComplianceItemStatus, ComplianceRegistryItem
from app.models.operator import OperationalPermission
from app.models.user import User
from app.domain.governance.compliance_service import ComplianceService

router = APIRouter(prefix="/compliance", tags=["compliance"])


class ComplianceItemRegisterRequest(BaseModel):
    compliance_item_id: str = Field(..., min_length=3, max_length=100)
    subject: str = Field(..., min_length=3, max_length=255)
    requirement_question: str = Field(..., min_length=5)
    technical_control: str = Field(..., min_length=5)
    evidence: str = Field(..., min_length=5)
    owner: str = Field(..., min_length=2, max_length=100)
    technical_readiness: bool = False
    contractual_readiness: bool = False
    policy_readiness: bool = False
    legal_approval: bool = False


class LegalReviewRequest(BaseModel):
    legal_reviewer: str = Field(..., min_length=2, max_length=100)
    decision: str = Field(..., min_length=2, max_length=255)
    status: ComplianceItemStatus
    legal_approval: bool
    follow_up: str | None = None


@router.get("/scorecard")
def get_compliance_scorecard(
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.COMPLIANCE_OPERATIONS)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieves dimensional compliance readiness: technical, contractual, policy, and legal."""
    service = ComplianceService(db)
    return service.get_compliance_scorecard()


@router.get("/items")
def list_compliance_items(
    status_filter: ComplianceItemStatus | None = Query(None, alias="status"),
    owner_filter: str | None = Query(None, alias="owner"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.COMPLIANCE_OPERATIONS)),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Lists compliance items in the formal compliance closure registry."""
    query = db.query(ComplianceRegistryItem)
    if status_filter:
        query = query.filter(ComplianceRegistryItem.status == status_filter)
    if owner_filter:
        query = query.filter(ComplianceRegistryItem.owner == owner_filter)
    items = query.order_by(ComplianceRegistryItem.created_at.desc()).offset(skip).limit(limit).all()
    return [
        {
            "compliance_item_id": i.compliance_item_id,
            "subject": i.subject,
            "requirement_question": i.requirement_question,
            "technical_control": i.technical_control,
            "evidence": i.evidence,
            "owner": i.owner,
            "legal_reviewer": i.legal_reviewer,
            "status": i.status.value,
            "technical_readiness": i.technical_readiness,
            "contractual_readiness": i.contractual_readiness,
            "policy_readiness": i.policy_readiness,
            "legal_approval": i.legal_approval,
            "decision": i.decision,
            "follow_up": i.follow_up,
        }
        for i in items
    ]


@router.post("/items", status_code=status.HTTP_201_CREATED)
def register_compliance_item(
    req: ComplianceItemRegisterRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.COMPLIANCE_OPERATIONS)),
    db: Session = Depends(get_db),
):
    """Registers or updates an item in the formal compliance registry."""
    service = ComplianceService(db)
    item = service.register_compliance_item(
        compliance_item_id=req.compliance_item_id,
        subject=req.subject,
        requirement_question=req.requirement_question,
        technical_control=req.technical_control,
        evidence=req.evidence,
        owner=req.owner,
        technical_readiness=req.technical_readiness,
        contractual_readiness=req.contractual_readiness,
        policy_readiness=req.policy_readiness,
        legal_approval=req.legal_approval,
        actor=current_user,
    )
    return {"status": "REGISTERED", "compliance_item_id": item.compliance_item_id}


@router.post("/items/{compliance_item_id}/review")
def record_legal_review(
    compliance_item_id: str,
    req: LegalReviewRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.COMPLIANCE_OPERATIONS)),
    db: Session = Depends(get_db),
):
    """Records formal legal reviewer decision on a compliance registry item."""
    service = ComplianceService(db)
    item = service.record_legal_review(
        compliance_item_id=compliance_item_id,
        legal_reviewer=req.legal_reviewer,
        decision=req.decision,
        status=req.status,
        legal_approval=req.legal_approval,
        actor=current_user,
        follow_up=req.follow_up,
    )
    return {"status": "REVIEWED", "compliance_item_id": item.compliance_item_id, "decision": item.decision}
