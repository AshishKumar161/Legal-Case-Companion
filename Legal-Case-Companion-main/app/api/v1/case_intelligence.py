import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.auth import limiter
from app.models.user import User
from app.schemas.case_intelligence import (
    CaseChronologyEventCreate,
    CaseChronologyEventResponse,
    CaseChronologyEventUpdate,
    CaseEvidenceGapCreate,
    CaseEvidenceGapResponse,
    CaseEvidenceGapUpdate,
    CaseFactCreate,
    CaseFactResponse,
    CaseFactUpdate,
    CaseIntelligenceResponse,
    CaseRiskIndicatorCreate,
    CaseRiskIndicatorResponse,
    CaseRiskIndicatorUpdate,
    LegalIssueCreate,
    LegalIssueResponse,
    LegalIssueUpdate,
    RefreshIntelligenceRequest,
)
from app.services.case_intelligence_service import CaseIntelligenceService

router = APIRouter(prefix="/cases", tags=["case-intelligence"])


@router.get(
    "/{case_id}/intelligence",
    response_model=CaseIntelligenceResponse,
)
@limiter.limit("30/minute")
def get_case_intelligence(
    request: Request,
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves full case intelligence summary, facts, issues, timeline, gaps, and risks."""
    service = CaseIntelligenceService(db)
    return service.get_case_intelligence(current_user, case_id)


@router.post(
    "/{case_id}/intelligence/refresh",
    response_model=CaseIntelligenceResponse,
)
@limiter.limit("10/minute")
def refresh_case_intelligence(
    request: Request,
    case_id: uuid.UUID,
    req: RefreshIntelligenceRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Refreshes and extracts verified case intelligence from active safe evidence."""
    service = CaseIntelligenceService(db)
    return service.refresh_case_intelligence(current_user, case_id, req)


# Facts Endpoints
@router.get(
    "/{case_id}/intelligence/facts",
    response_model=list[CaseFactResponse],
)
@limiter.limit("30/minute")
def list_facts(
    request: Request,
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    intel = service.get_case_intelligence(current_user, case_id)
    return intel.facts


@router.post(
    "/{case_id}/intelligence/facts",
    response_model=CaseFactResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def create_fact(
    request: Request,
    case_id: uuid.UUID,
    req: CaseFactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    return service.create_fact(current_user, case_id, req)


@router.patch(
    "/{case_id}/intelligence/facts/{fact_id}",
    response_model=CaseFactResponse,
)
@limiter.limit("20/minute")
def update_fact(
    request: Request,
    case_id: uuid.UUID,
    fact_id: uuid.UUID,
    req: CaseFactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    return service.update_fact(current_user, case_id, fact_id, req)


# Issues Endpoints
@router.get(
    "/{case_id}/intelligence/issues",
    response_model=list[LegalIssueResponse],
)
@limiter.limit("30/minute")
def list_issues(
    request: Request,
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    intel = service.get_case_intelligence(current_user, case_id)
    return intel.issues


@router.post(
    "/{case_id}/intelligence/issues",
    response_model=LegalIssueResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def create_issue(
    request: Request,
    case_id: uuid.UUID,
    req: LegalIssueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    return service.create_issue(current_user, case_id, req)


@router.patch(
    "/{case_id}/intelligence/issues/{issue_id}",
    response_model=LegalIssueResponse,
)
@limiter.limit("20/minute")
def update_issue(
    request: Request,
    case_id: uuid.UUID,
    issue_id: uuid.UUID,
    req: LegalIssueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    return service.update_issue(current_user, case_id, issue_id, req)


# Timeline Endpoints
@router.get(
    "/{case_id}/intelligence/timeline",
    response_model=list[CaseChronologyEventResponse],
)
@limiter.limit("30/minute")
def list_timeline(
    request: Request,
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    intel = service.get_case_intelligence(current_user, case_id)
    return intel.timeline


@router.post(
    "/{case_id}/intelligence/timeline",
    response_model=CaseChronologyEventResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def create_timeline_event(
    request: Request,
    case_id: uuid.UUID,
    req: CaseChronologyEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    return service.create_timeline_event(current_user, case_id, req)


@router.patch(
    "/{case_id}/intelligence/timeline/{event_id}",
    response_model=CaseChronologyEventResponse,
)
@limiter.limit("20/minute")
def update_timeline_event(
    request: Request,
    case_id: uuid.UUID,
    event_id: uuid.UUID,
    req: CaseChronologyEventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    return service.update_timeline_event(current_user, case_id, event_id, req)


# Evidence Gaps Endpoints
@router.get(
    "/{case_id}/intelligence/evidence-gaps",
    response_model=list[CaseEvidenceGapResponse],
)
@limiter.limit("30/minute")
def list_evidence_gaps(
    request: Request,
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    intel = service.get_case_intelligence(current_user, case_id)
    return intel.evidence_gaps


@router.post(
    "/{case_id}/intelligence/evidence-gaps",
    response_model=CaseEvidenceGapResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def create_evidence_gap(
    request: Request,
    case_id: uuid.UUID,
    req: CaseEvidenceGapCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    return service.create_evidence_gap(current_user, case_id, req)


@router.patch(
    "/{case_id}/intelligence/evidence-gaps/{gap_id}",
    response_model=CaseEvidenceGapResponse,
)
@limiter.limit("20/minute")
def update_evidence_gap(
    request: Request,
    case_id: uuid.UUID,
    gap_id: uuid.UUID,
    req: CaseEvidenceGapUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    return service.update_evidence_gap(current_user, case_id, gap_id, req)


# Risks Endpoints
@router.get(
    "/{case_id}/intelligence/risks",
    response_model=list[CaseRiskIndicatorResponse],
)
@limiter.limit("30/minute")
def list_risks(
    request: Request,
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    intel = service.get_case_intelligence(current_user, case_id)
    return intel.risks


@router.post(
    "/{case_id}/intelligence/risks",
    response_model=CaseRiskIndicatorResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def create_risk(
    request: Request,
    case_id: uuid.UUID,
    req: CaseRiskIndicatorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    return service.create_risk(current_user, case_id, req)


@router.patch(
    "/{case_id}/intelligence/risks/{risk_id}",
    response_model=CaseRiskIndicatorResponse,
)
@limiter.limit("20/minute")
def update_risk(
    request: Request,
    case_id: uuid.UUID,
    risk_id: uuid.UUID,
    req: CaseRiskIndicatorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseIntelligenceService(db)
    return service.update_risk(current_user, case_id, risk_id, req)
