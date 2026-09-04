from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import RequireOperatorPermission, get_db
from app.models.incident import (
    IncidentCategory,
    IncidentDetector,
    IncidentSeverity,
    IncidentStatus,
)
from app.models.operator import OperationalPermission
from app.models.user import User
from app.schemas.incident import (
    IncidentCreateRequest,
    IncidentResponse,
    IncidentTimelineResponse,
    IncidentTransitionRequest,
)
from app.services.incident_service import IncidentService

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentResponse])
def list_incidents(
    status_filter: IncidentStatus | None = Query(None, alias="status"),
    severity_filter: IncidentSeverity | None = Query(None, alias="severity"),
    category_filter: IncidentCategory | None = Query(None, alias="category"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.INCIDENT_MANAGE)),
    db: Session = Depends(get_db),
):
    """Lists production incidents with optional status, severity, and category filtering."""
    service = IncidentService(db)
    return service.list_incidents(
        status=status_filter,
        severity=severity_filter,
        category=category_filter,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def create_incident(
    req: IncidentCreateRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.INCIDENT_MANAGE)),
    db: Session = Depends(get_db),
):
    """Creates a new production incident, initializing its timeline and immutable audit trail."""
    service = IncidentService(db)
    return service.create_incident(
        summary=req.summary,
        severity=req.severity,
        category=req.category,
        affected_scope=req.affected_scope,
        detected_by=IncidentDetector.OPERATOR,
        actor=current_user,
        assigned_to_user_id=req.assigned_to_user_id,
        metadata_=req.metadata_,
    )


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(
    incident_id: str,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.INCIDENT_MANAGE)),
    db: Session = Depends(get_db),
):
    """Inspects a specific production incident, including full chronological timeline events."""
    service = IncidentService(db)
    return service.get_incident(incident_id)


@router.post("/{incident_id}/transition", response_model=IncidentResponse)
def transition_incident_status(
    incident_id: str,
    req: IncidentTransitionRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.INCIDENT_MANAGE)),
    db: Session = Depends(get_db),
):
    """Transitions incident status according to valid state machine rules with non-repudiation audit."""
    service = IncidentService(db)
    return service.transition_status(
        incident_id=incident_id,
        new_status=req.new_status,
        actor=current_user,
        notes=req.notes,
        root_cause=req.root_cause,
        mitigation=req.mitigation,
        resolution=req.resolution,
    )


@router.post("/{incident_id}/notes", response_model=IncidentTimelineResponse)
def add_incident_note(
    incident_id: str,
    message: str = Query(..., min_length=3),
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.INCIDENT_MANAGE)),
    db: Session = Depends(get_db),
):
    """Appends an operational note to the chronological incident timeline."""
    service = IncidentService(db)
    return service.add_timeline_note(
        incident_id=incident_id,
        actor=current_user,
        message=message,
    )
