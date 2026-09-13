from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.case import CaseStatus
from app.models.case_collaboration import MatterRequestStatus
from app.models.task import TaskStatus
from app.models.user import User
from app.schemas.case import (
    CaseCreate,
    CaseResponse,
    CaseUpdate,
    CaseWorkspaceResponse,
    GrantLawyerAccessRequest,
    ParticipantAdd,
    ParticipantResponse,
    ParticipantUpdate,
    TimelineEventResponse,
)
from app.schemas.collaboration import (
    CaseMessageCreate,
    CaseMessageResponse,
    MatterBriefResponse,
    MatterParticipantDetailResponse,
    MatterRequestCreate,
    MatterRequestResponse,
    MatterRequestReview,
    MatterRequestSubmit,
)
from app.schemas.consultation import ConsultationCreate, ConsultationResponse
from app.schemas.note import CaseNoteCreate, CaseNoteResponse, CaseNoteUpdate
from app.schemas.pagination import PaginatedResponse
from app.schemas.task import CaseTaskCreate, CaseTaskResponse, CaseTaskUpdate
from app.domain.cases.case_report_service import CaseReportService
from app.domain.cases.case_service import CaseService
from app.domain.cases.collaboration_service import CollaborationService
from app.domain.consultations.consultation_service import ConsultationService

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    req: CaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.create_case(current_user, req)


@router.get("", response_model=PaginatedResponse[CaseResponse])
def get_cases(
    status: CaseStatus | None = None,
    search: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.get_cases(
        current_user,
        status=status,
        search=search,
        created_after=created_after,
        created_before=created_before,
        skip=skip,
        limit=limit,
    )


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.get_case_by_id(current_user, case_id)


@router.get("/{case_id}/workspace", response_model=CaseWorkspaceResponse)
def get_case_workspace(
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.get_workspace(current_user, case_id)


@router.get("/{case_id}/report")
def export_case_report(
    case_id: UUID,
    format: str = Query("json", pattern="^(json|markdown)$"),
    download: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates and exports an authorized point-in-time Case Summary Report.
    Supports JSON model response or attachment downloads in JSON and Markdown.
    """
    report_service = CaseReportService(db)
    report_data = report_service.generate_report_data(current_user, case_id)

    if format == "markdown":
        md_content = report_service.generate_markdown_report(report_data)
        filename = report_service.generate_safe_filename(
            case_id, report_data.case_overview.title, ext="markdown"
        )
        return Response(
            content=md_content,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if download:
        json_content = report_data.model_dump_json(indent=2)
        filename = report_service.generate_safe_filename(
            case_id, report_data.case_overview.title, ext="json"
        )
        return Response(
            content=json_content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return report_data


@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: UUID,
    req: CaseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.update_case(current_user, case_id, req)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    case_service.delete_case(current_user, case_id)


# --------------------------------------------------------------------------
# PARTICIPANTS
# --------------------------------------------------------------------------


@router.post("/{case_id}/participants", response_model=ParticipantResponse)
def add_participant(
    case_id: UUID,
    req: ParticipantAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.add_participant(current_user, case_id, req)


@router.post(
    "/{case_id}/grant-lawyer-access",
    response_model=ParticipantResponse,
    status_code=status.HTTP_201_CREATED,
)
def grant_lawyer_access(
    case_id: UUID,
    req: GrantLawyerAccessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.grant_lawyer_access(current_user, case_id, req)


@router.get(
    "/{case_id}/participants", response_model=PaginatedResponse[ParticipantResponse]
)
def get_participants(
    case_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.get_participants(current_user, case_id, skip, limit)


@router.patch("/{case_id}/participants/{user_id}", response_model=ParticipantResponse)
def update_participant_role(
    case_id: UUID,
    user_id: UUID,
    req: ParticipantUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.update_participant_role(current_user, case_id, user_id, req)


@router.delete(
    "/{case_id}/participants/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_participant(
    case_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    case_service.remove_participant(current_user, case_id, user_id)


# --------------------------------------------------------------------------
# TIMELINE
# --------------------------------------------------------------------------


@router.get(
    "/{case_id}/timeline", response_model=PaginatedResponse[TimelineEventResponse]
)
def get_timeline(
    case_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.get_timeline(current_user, case_id, skip, limit)


# --------------------------------------------------------------------------
# TASKS
# --------------------------------------------------------------------------


@router.post(
    "/{case_id}/tasks",
    response_model=CaseTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    case_id: UUID,
    req: CaseTaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.create_task(current_user, case_id, req)


@router.get("/{case_id}/tasks", response_model=PaginatedResponse[CaseTaskResponse])
def get_tasks(
    case_id: UUID,
    status: TaskStatus | None = None,
    owner_user_id: UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.get_tasks(
        current_user,
        case_id,
        status=status,
        owner_user_id=owner_user_id,
        skip=skip,
        limit=limit,
    )


@router.get("/{case_id}/tasks/{task_id}", response_model=CaseTaskResponse)
def get_task(
    case_id: UUID,
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.get_task_by_id(current_user, case_id, task_id)


@router.patch("/{case_id}/tasks/{task_id}", response_model=CaseTaskResponse)
def update_task(
    case_id: UUID,
    task_id: UUID,
    req: CaseTaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.update_task(current_user, case_id, task_id, req)


@router.delete("/{case_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    case_id: UUID,
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    case_service.delete_task(current_user, case_id, task_id)


# --------------------------------------------------------------------------
# NOTES
# --------------------------------------------------------------------------


@router.post(
    "/{case_id}/notes",
    response_model=CaseNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_note(
    case_id: UUID,
    req: CaseNoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.create_note(current_user, case_id, req)


@router.get("/{case_id}/notes", response_model=PaginatedResponse[CaseNoteResponse])
def get_notes(
    case_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.get_notes(current_user, case_id, skip, limit)


@router.get("/{case_id}/notes/{note_id}", response_model=CaseNoteResponse)
def get_note(
    case_id: UUID,
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.get_note_by_id(current_user, case_id, note_id)


@router.patch("/{case_id}/notes/{note_id}", response_model=CaseNoteResponse)
def update_note(
    case_id: UUID,
    note_id: UUID,
    req: CaseNoteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    return case_service.update_note(current_user, case_id, note_id, req)


@router.delete("/{case_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    case_id: UUID,
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_service = CaseService(db)
    case_service.delete_note(current_user, case_id, note_id)


# --------------------------------------------------------------------------
# CASE CONSULTATIONS
# --------------------------------------------------------------------------


@router.post(
    "/{case_id}/consultations",
    response_model=ConsultationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_case_consultation(
    case_id: UUID,
    req: ConsultationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req.case_id = case_id
    consultation_service = ConsultationService(db)
    return consultation_service.request_consultation(current_user, req)


@router.get(
    "/{case_id}/consultations",
    response_model=PaginatedResponse[ConsultationResponse],
)
def get_case_consultations(
    case_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.get_consultations(
        current_user, case_id=case_id, skip=skip, limit=limit
    )


# --------------------------------------------------------------------------
# COLLABORATION & MATTER COMMUNICATION 4.0
# --------------------------------------------------------------------------


@router.get(
    "/{case_id}/collaboration/participants",
    response_model=list[MatterParticipantDetailResponse],
)
def get_matter_participants_detailed(
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = CollaborationService(db)
    return service.get_matter_participants_detailed(current_user, case_id)


@router.get(
    "/{case_id}/collaboration/brief",
    response_model=MatterBriefResponse,
)
def get_matter_brief(
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = CollaborationService(db)
    return service.get_matter_brief(current_user, case_id)


@router.get(
    "/{case_id}/collaboration/messages",
    response_model=list[CaseMessageResponse],
)
def get_case_messages(
    case_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = CollaborationService(db)
    return service.get_case_messages(current_user, case_id, skip=skip, limit=limit)


@router.post(
    "/{case_id}/collaboration/messages",
    response_model=CaseMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_case_message(
    case_id: UUID,
    req: CaseMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = CollaborationService(db)
    return service.send_case_message(current_user, case_id, req)


@router.get(
    "/{case_id}/collaboration/requests",
    response_model=list[MatterRequestResponse],
)
def get_matter_requests(
    case_id: UUID,
    status: MatterRequestStatus | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = CollaborationService(db)
    return service.get_matter_requests(current_user, case_id, status=status)


@router.post(
    "/{case_id}/collaboration/requests",
    response_model=MatterRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_matter_request(
    case_id: UUID,
    req: MatterRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = CollaborationService(db)
    return service.create_matter_request(current_user, case_id, req)


@router.post(
    "/{case_id}/collaboration/requests/{request_id}/submit",
    response_model=MatterRequestResponse,
)
def submit_matter_request(
    case_id: UUID,
    request_id: UUID,
    req: MatterRequestSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = CollaborationService(db)
    return service.submit_matter_request(current_user, case_id, request_id, req)


@router.post(
    "/{case_id}/collaboration/requests/{request_id}/review",
    response_model=MatterRequestResponse,
)
def review_matter_request(
    case_id: UUID,
    request_id: UUID,
    req: MatterRequestReview,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = CollaborationService(db)
    return service.review_matter_request(current_user, case_id, request_id, req)

