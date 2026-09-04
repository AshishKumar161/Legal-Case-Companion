from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import RequireOperatorPermission, get_db
from app.models.experiment import ExperimentStatus
from app.models.operator import OperationalPermission
from app.models.user import User
from app.schemas.experiment import (
    ExperimentCreateRequest,
    ExperimentResponse,
    ExperimentTransitionRequest,
)
from app.services.experiment_service import ExperimentService

router = APIRouter(prefix="/pilot/experiments", tags=["pilot-experiments"])


@router.get("", response_model=list[ExperimentResponse])
def list_experiments(
    status_filter: ExperimentStatus | None = Query(None, alias="status"),
    cohort_filter: str | None = Query(None, alias="cohort"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.PILOT_GOVERNANCE)),
    db: Session = Depends(get_db),
):
    """Lists structured pilot experiments and hypothesis outcomes."""
    service = ExperimentService(db)
    return service.list_experiments(status=status_filter, cohort=cohort_filter, skip=skip, limit=limit)


@router.post("", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
def create_experiment(
    req: ExperimentCreateRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.PILOT_GOVERNANCE)),
    db: Session = Depends(get_db),
):
    """Creates a new pilot cohort experiment with explicit success/failure criteria."""
    service = ExperimentService(db)
    return service.create_experiment(
        experiment_id=req.experiment_id,
        hypothesis=req.hypothesis,
        cohort=req.cohort,
        success_metrics=req.success_metrics,
        failure_metrics=req.failure_metrics,
        owner_user=current_user,
        notes=req.notes,
        start_at=req.start_at,
        end_at=req.end_at,
    )


@router.get("/{experiment_id}", response_model=ExperimentResponse)
def get_experiment(
    experiment_id: str,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.PILOT_GOVERNANCE)),
    db: Session = Depends(get_db),
):
    """Retrieves an experiment by ID or human-readable identifier."""
    service = ExperimentService(db)
    return service.get_experiment(experiment_id)


@router.post("/{experiment_id}/transition", response_model=ExperimentResponse)
def transition_experiment_status(
    experiment_id: str,
    req: ExperimentTransitionRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.PILOT_GOVERNANCE)),
    db: Session = Depends(get_db),
):
    """Transitions experiment status and records the formal operational decision."""
    service = ExperimentService(db)
    return service.transition_experiment(
        experiment_identifier=experiment_id,
        new_status=req.new_status,
        actor=current_user,
        decision=req.decision,
        notes=req.notes,
    )
