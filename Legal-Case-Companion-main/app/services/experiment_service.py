import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import AppException, ResourceNotFoundError
from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.experiment import ExperimentStatus, PilotExperiment
from app.models.user import User


class ExperimentService:
    """Manages the lifecycle of controlled pilot hypotheses, success metrics, and progression decisions."""

    ALLOWED_TRANSITIONS: dict[ExperimentStatus, set[ExperimentStatus]] = {
        ExperimentStatus.PLANNED: {ExperimentStatus.ACTIVE, ExperimentStatus.TERMINATED},
        ExperimentStatus.ACTIVE: {ExperimentStatus.PAUSED, ExperimentStatus.COMPLETED, ExperimentStatus.TERMINATED},
        ExperimentStatus.PAUSED: {ExperimentStatus.ACTIVE, ExperimentStatus.TERMINATED},
        ExperimentStatus.COMPLETED: set(),  # Terminal
        ExperimentStatus.TERMINATED: set(),  # Terminal
    }

    def __init__(self, db: Session):
        self.db = db

    def create_experiment(
        self,
        experiment_id: str,
        hypothesis: str,
        cohort: str,
        success_metrics: dict,
        failure_metrics: dict,
        owner_user: User | None = None,
        notes: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> PilotExperiment:
        now = datetime.now(UTC)
        norm_id = experiment_id.strip().upper()

        existing = self.db.query(PilotExperiment).filter(PilotExperiment.experiment_id == norm_id).first()
        if existing:
            raise AppException(
                status_code=400,
                code="DUPLICATE_EXPERIMENT_ID",
                message=f"Experiment '{norm_id}' already exists.",
            )

        exp = PilotExperiment(
            id=generate_uuid7(),
            experiment_id=norm_id,
            hypothesis=hypothesis,
            cohort=cohort.strip(),
            start_at=start_at or now,
            end_at=end_at,
            success_metrics=success_metrics,
            failure_metrics=failure_metrics,
            owner_user_id=owner_user.id if owner_user else None,
            status=ExperimentStatus.PLANNED,
            notes=notes,
            created_at=now,
            updated_at=now,
        )
        self.db.add(exp)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=owner_user.id if owner_user else None,
            event_type="PILOT_EXPERIMENT_CREATED",
            entity_type="PILOT_EXPERIMENT",
            entity_id=exp.id,
            action="CREATE",
            timestamp=now,
            metadata_={"experiment_id": exp.experiment_id, "cohort": exp.cohort},
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(exp)
        return exp

    def transition_experiment(
        self,
        experiment_identifier: str | uuid.UUID,
        new_status: ExperimentStatus,
        actor: User,
        decision: str | None = None,
        notes: str | None = None,
    ) -> PilotExperiment:
        exp = self.get_experiment(experiment_identifier)
        current = exp.status

        allowed = self.ALLOWED_TRANSITIONS.get(current, set())
        if new_status not in allowed:
            raise AppException(
                status_code=400,
                code="INVALID_EXPERIMENT_TRANSITION",
                message=f"Cannot transition experiment from {current.value} to {new_status.value}. Allowed: {[s.value for s in allowed]}",
            )

        now = datetime.now(UTC)
        exp.status = new_status
        exp.updated_at = now
        if decision:
            exp.decision = decision
        if notes:
            exp.notes = f"{exp.notes}\n[Transition Note {now.isoformat()}]: {notes}" if exp.notes else notes
        if new_status in (ExperimentStatus.COMPLETED, ExperimentStatus.TERMINATED) and not exp.end_at:
            exp.end_at = now

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=actor.id,
            event_type="PILOT_EXPERIMENT_TRANSITIONED",
            entity_type="PILOT_EXPERIMENT",
            entity_id=exp.id,
            action="UPDATE",
            timestamp=now,
            metadata_={
                "experiment_id": exp.experiment_id,
                "from_status": current.value,
                "to_status": new_status.value,
                "decision": decision,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(exp)
        return exp

    def get_experiment(self, identifier: str | uuid.UUID) -> PilotExperiment:
        query = self.db.query(PilotExperiment)
        if isinstance(identifier, uuid.UUID):
            exp = query.filter(PilotExperiment.id == identifier).first()
        else:
            try:
                parsed_uuid = uuid.UUID(str(identifier))
                exp = query.filter((PilotExperiment.id == parsed_uuid) | (PilotExperiment.experiment_id == str(identifier))).first()
            except ValueError:
                exp = query.filter(PilotExperiment.experiment_id == str(identifier)).first()

        if not exp:
            raise ResourceNotFoundError(f"Experiment '{identifier}' not found.")
        return exp

    def list_experiments(
        self,
        status: ExperimentStatus | None = None,
        cohort: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[PilotExperiment]:
        query = self.db.query(PilotExperiment)
        if status:
            query = query.filter(PilotExperiment.status == status)
        if cohort:
            query = query.filter(PilotExperiment.cohort == cohort)
        return query.order_by(PilotExperiment.created_at.desc()).offset(skip).limit(limit).all()
