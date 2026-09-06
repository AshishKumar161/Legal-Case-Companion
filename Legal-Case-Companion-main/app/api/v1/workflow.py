import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.auth import limiter
from app.models.task import TaskPriority, TaskStatus
from app.models.user import User
from app.models.workflow import DeadlineStatus, DeadlineType
from app.schemas.task import (
    CaseHealthSummaryResponse,
    CaseTaskBatchActionRequest,
    CaseTaskReassignRequest,
    CaseTaskResponse,
    CaseWorkflowTemplateApplyRequest,
)
from app.schemas.workflow import (
    CaseDeadlineCreate,
    CaseDeadlineResponse,
    CaseDeadlineUpdate,
    CaseHearingAdjournRequest,
    CaseHearingCompleteRequest,
    CaseHearingCreate,
    CaseHearingECourtsImportRequest,
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


@router.post(
    "/{case_id}/hearings/{hearing_id}/adjourn",
    response_model=CaseHearingResponse,
)
@limiter.limit("20/minute")
def adjourn_hearing(
    request: Request,
    case_id: uuid.UUID,
    hearing_id: uuid.UUID,
    req: CaseHearingAdjournRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Adjourns a hearing and records the scheduled next date of hearing."""
    service = CaseWorkflowService(db)
    return service.adjourn_hearing(current_user, case_id, hearing_id, req)


@router.post(
    "/{case_id}/hearings/{hearing_id}/complete",
    response_model=CaseHearingResponse,
)
@limiter.limit("20/minute")
def complete_hearing(
    request: Request,
    case_id: uuid.UUID,
    hearing_id: uuid.UUID,
    req: CaseHearingCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Concludes hearing proceedings with immutable audit records."""
    service = CaseWorkflowService(db)
    return service.complete_hearing(current_user, case_id, hearing_id, req)


@router.post(
    "/{case_id}/hearings/import-ecourts",
    response_model=CaseHearingResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def import_ecourts_hearing(
    request: Request,
    case_id: uuid.UUID,
    req: CaseHearingECourtsImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Imports verified eCourts cause list or CNR hearing data preserving external provenance."""
    service = CaseWorkflowService(db)
    return service.import_ecourts_hearing(current_user, case_id, req)


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


# Task Lifecycle Actions
@router.post(
    "/{case_id}/tasks/{task_id}/start",
    response_model=CaseTaskResponse,
)
@limiter.limit("20/minute")
def start_task(
    request: Request,
    case_id: uuid.UUID,
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transitions task from PENDING/BLOCKED to IN_PROGRESS."""
    service = CaseWorkflowService(db)
    return service.start_task(current_user, case_id, task_id)


@router.post(
    "/{case_id}/tasks/{task_id}/complete",
    response_model=CaseTaskResponse,
)
@limiter.limit("20/minute")
def complete_task(
    request: Request,
    case_id: uuid.UUID,
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marks task as COMPLETED with timestamp and audit trail."""
    service = CaseWorkflowService(db)
    return service.complete_task(current_user, case_id, task_id)


@router.post(
    "/{case_id}/tasks/{task_id}/cancel",
    response_model=CaseTaskResponse,
)
@limiter.limit("20/minute")
def cancel_task(
    request: Request,
    case_id: uuid.UUID,
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancels task with audit record."""
    service = CaseWorkflowService(db)
    return service.cancel_task(current_user, case_id, task_id)


@router.post(
    "/{case_id}/tasks/{task_id}/reopen",
    response_model=CaseTaskResponse,
)
@limiter.limit("20/minute")
def reopen_task(
    request: Request,
    case_id: uuid.UUID,
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Explicitly reopens a completed or cancelled task back to IN_PROGRESS."""
    service = CaseWorkflowService(db)
    return service.reopen_task(current_user, case_id, task_id)


@router.post(
    "/{case_id}/tasks/{task_id}/reassign",
    response_model=CaseTaskResponse,
)
@limiter.limit("20/minute")
def reassign_task(
    request: Request,
    case_id: uuid.UUID,
    task_id: uuid.UUID,
    req: CaseTaskReassignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reassigns task to an active authorized participant of the case."""
    service = CaseWorkflowService(db)
    return service.reassign_task(current_user, case_id, task_id, req)


@router.post(
    "/{case_id}/tasks/batch",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("10/minute")
def batch_task_operations(
    request: Request,
    case_id: uuid.UUID,
    req: CaseTaskBatchActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Executes atomic batch task actions (REASSIGN, CHANGE_PRIORITY, COMPLETE, CANCEL) within case scope."""
    service = CaseWorkflowService(db)
    return service.batch_task_operations(current_user, case_id, req)


# Deadline Lifecycle Actions
@router.post(
    "/{case_id}/deadlines/{deadline_id}/complete",
    response_model=CaseDeadlineResponse,
)
@limiter.limit("20/minute")
def complete_deadline(
    request: Request,
    case_id: uuid.UUID,
    deadline_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marks deadline as COMPLETED with timestamp and audit log."""
    service = CaseWorkflowService(db)
    return service.complete_deadline(current_user, case_id, deadline_id)


@router.post(
    "/{case_id}/deadlines/{deadline_id}/cancel",
    response_model=CaseDeadlineResponse,
)
@limiter.limit("20/minute")
def cancel_deadline(
    request: Request,
    case_id: uuid.UUID,
    deadline_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancels statutory or compliance deadline."""
    service = CaseWorkflowService(db)
    return service.cancel_deadline(current_user, case_id, deadline_id)


# Workflow Templates & Health Summary (Deterministic, Zero AI)
@router.post(
    "/{case_id}/workflow/templates/apply",
    response_model=list[CaseTaskResponse],
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
def apply_workflow_template(
    request: Request,
    case_id: uuid.UUID,
    req: CaseWorkflowTemplateApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Applies deterministic procedural operational templates (HEARING_PREPARATION, POST_HEARING_FOLLOWUP, EVIDENCE_PREPARATION, NEW_CONSULTATION)."""
    service = CaseWorkflowService(db)
    return service.apply_workflow_template(current_user, case_id, req)


@router.get(
    "/{case_id}/workflow/health-summary",
    response_model=CaseHealthSummaryResponse,
)
@limiter.limit("30/minute")
def get_case_health_summary(
    request: Request,
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculates deterministic operational case health indicators (telemetry, not legal advice)."""
    service = CaseWorkflowService(db)
    return service.get_case_health_summary(current_user, case_id)


@router.get(
    "/{case_id}/workflow/tasks",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("30/minute")
def get_filtered_tasks(
    request: Request,
    case_id: uuid.UUID,
    q: str | None = None,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    owner_user_id: uuid.UUID | None = None,
    linked_hearing_id: uuid.UUID | None = None,
    linked_evidence_id: uuid.UUID | None = None,
    is_overdue: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Server-side filtered and paginated search for case tasks."""
    service = CaseWorkflowService(db)
    return service.get_filtered_tasks(
        current_user,
        case_id,
        q=q,
        status=status,
        priority=priority,
        owner_user_id=owner_user_id,
        linked_hearing_id=linked_hearing_id,
        linked_evidence_id=linked_evidence_id,
        is_overdue=is_overdue,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{case_id}/workflow/deadlines",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("30/minute")
def get_filtered_deadlines(
    request: Request,
    case_id: uuid.UUID,
    q: str | None = None,
    status: DeadlineStatus | None = None,
    deadline_type: DeadlineType | None = None,
    linked_hearing_id: uuid.UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Server-side filtered and paginated search for case deadlines."""
    service = CaseWorkflowService(db)
    return service.get_filtered_deadlines(
        current_user,
        case_id,
        q=q,
        status=status,
        deadline_type=deadline_type,
        linked_hearing_id=linked_hearing_id,
        skip=skip,
        limit=limit,
    )
