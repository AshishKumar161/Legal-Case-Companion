import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.auth import limiter
from app.models.user import User
from app.schemas.task import CaseTaskResponse
from app.schemas.workflow import (
    CaseDeadlineCreate,
    CaseDeadlineResponse,
    CaseDeadlineUpdate,
    CaseHearingCreate,
    CaseHearingResponse,
    CaseHearingUpdate,
    CaseWorkflowResponse,
)
from app.services.case_workflow_service import CaseWorkflowService

router = APIRouter(prefix="/cases", tags=["workflow"])


@router.get(
    "/{case_id}/workflow",
    response_model=CaseWorkflowResponse,
)
@limiter.limit("30/minute")
def get_case_workflow(
    request: Request,
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves comprehensive case workflow dashboard (tasks, deadlines, hearings, summary)."""
    service = CaseWorkflowService(db)
    return service.get_workflow_overview(current_user, case_id)


@router.post(
    "/{case_id}/workflow/suggestions/generate",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("10/minute")
def generate_workflow_suggestions(
    request: Request,
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates unconfirmed task, deadline, and hearing suggestions from case intelligence."""
    service = CaseWorkflowService(db)
    return service.generate_suggestions_from_intelligence(current_user, case_id)


# Deadlines Endpoints
@router.get(
    "/{case_id}/deadlines",
    response_model=list[CaseDeadlineResponse],
)
@limiter.limit("30/minute")
def list_deadlines(
    request: Request,
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseWorkflowService(db)
    overview = service.get_workflow_overview(current_user, case_id)
    return overview.deadlines


@router.post(
    "/{case_id}/deadlines",
    response_model=CaseDeadlineResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def create_deadline(
    request: Request,
    case_id: uuid.UUID,
    req: CaseDeadlineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseWorkflowService(db)
    return service.create_deadline(current_user, case_id, req)


@router.patch(
    "/{case_id}/deadlines/{deadline_id}",
    response_model=CaseDeadlineResponse,
)
@limiter.limit("20/minute")
def update_deadline(
    request: Request,
    case_id: uuid.UUID,
    deadline_id: uuid.UUID,
    req: CaseDeadlineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseWorkflowService(db)
    return service.update_deadline(current_user, case_id, deadline_id, req)


@router.post(
    "/{case_id}/deadlines/{deadline_id}/confirm",
    response_model=CaseDeadlineResponse,
)
@limiter.limit("20/minute")
def confirm_deadline(
    request: Request,
    case_id: uuid.UUID,
    deadline_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseWorkflowService(db)
    return service.confirm_deadline(current_user, case_id, deadline_id)


# Hearings Endpoints
@router.get(
    "/{case_id}/hearings",
    response_model=list[CaseHearingResponse],
)
@limiter.limit("30/minute")
def list_hearings(
    request: Request,
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseWorkflowService(db)
    overview = service.get_workflow_overview(current_user, case_id)
    return overview.hearings


@router.post(
    "/{case_id}/hearings",
    response_model=CaseHearingResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def create_hearing(
    request: Request,
    case_id: uuid.UUID,
    req: CaseHearingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseWorkflowService(db)
    return service.create_hearing(current_user, case_id, req)


@router.patch(
    "/{case_id}/hearings/{hearing_id}",
    response_model=CaseHearingResponse,
)
@limiter.limit("20/minute")
def update_hearing(
    request: Request,
    case_id: uuid.UUID,
    hearing_id: uuid.UUID,
    req: CaseHearingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseWorkflowService(db)
    return service.update_hearing(current_user, case_id, hearing_id, req)


@router.post(
    "/{case_id}/hearings/{hearing_id}/confirm",
    response_model=CaseHearingResponse,
)
@limiter.limit("20/minute")
def confirm_hearing(
    request: Request,
    case_id: uuid.UUID,
    hearing_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseWorkflowService(db)
    return service.confirm_hearing(current_user, case_id, hearing_id)


# Task Confirmation Endpoint
@router.post(
    "/{case_id}/tasks/{task_id}/confirm",
    response_model=CaseTaskResponse,
)
@limiter.limit("20/minute")
def confirm_task(
    request: Request,
    case_id: uuid.UUID,
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseWorkflowService(db)
    return service.confirm_task(current_user, case_id, task_id)
