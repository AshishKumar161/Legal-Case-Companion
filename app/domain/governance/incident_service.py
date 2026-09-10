import uuid
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, NotFoundError
from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.incident import (
    IncidentCategory,
    IncidentDetector,
    IncidentSeverity,
    IncidentStatus,
    IncidentTimelineEvent,
    ProductionIncident,
)
from app.models.user import User


class IncidentService:
    """Manages the full lifecycle of production operational, security, and compliance incidents."""

    ALLOWED_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
        IncidentStatus.DETECTED: {
            IncidentStatus.ACKNOWLEDGED,
            IncidentStatus.INVESTIGATING,
            IncidentStatus.CLOSED,  # e.g., false positive
        },
        IncidentStatus.ACKNOWLEDGED: {
            IncidentStatus.INVESTIGATING,
            IncidentStatus.MITIGATED,
            IncidentStatus.CLOSED,
        },
        IncidentStatus.INVESTIGATING: {
            IncidentStatus.MITIGATED,
            IncidentStatus.RESOLVED,
            IncidentStatus.CLOSED,
        },
        IncidentStatus.MITIGATED: {
            IncidentStatus.RESOLVED,
            IncidentStatus.INVESTIGATING,  # regression / mitigation failed
        },
        IncidentStatus.RESOLVED: {
            IncidentStatus.CLOSED,
            IncidentStatus.INVESTIGATING,  # re-opened after resolution testing
        },
        IncidentStatus.CLOSED: {
            IncidentStatus.INVESTIGATING,  # reopened with new evidence
        },
    }

    def __init__(self, db: Session):
        self.db = db

    def _generate_incident_id(self) -> str:
        today_str = datetime.now(UTC).strftime("%Y%m%d")
        count = (
            self.db.query(func.count(ProductionIncident.id))
            .filter(ProductionIncident.incident_id.like(f"INC-{today_str}-%"))
            .scalar()
            or 0
        )
        return f"INC-{today_str}-{count + 1:04d}"

    def create_incident(
        self,
        summary: str,
        severity: IncidentSeverity,
        category: IncidentCategory,
        affected_scope: str | None = None,
        detected_by: IncidentDetector = IncidentDetector.OPERATOR,
        actor: User | None = None,
        assigned_to_user_id: uuid.UUID | None = None,
        metadata_: dict | None = None,
    ) -> ProductionIncident:
        now = datetime.now(UTC)
        incident_code = self._generate_incident_id()

        incident = ProductionIncident(
            id=generate_uuid7(),
            incident_id=incident_code,
            severity=severity,
            category=category,
            status=IncidentStatus.DETECTED,
            detected_at=now,
            summary=summary,
            affected_scope=affected_scope,
            detected_by=detected_by,
            assigned_to_user_id=assigned_to_user_id,
            postmortem_required=severity in (IncidentSeverity.SEV1_CRITICAL, IncidentSeverity.SEV2_HIGH),
            metadata_=metadata_ or {},
            created_at=now,
            updated_at=now,
        )
        self.db.add(incident)

        timeline = IncidentTimelineEvent(
            id=generate_uuid7(),
            incident_id=incident.id,
            actor_user_id=actor.id if actor else None,
            event_type="INCIDENT_CREATED",
            message=f"Incident created with severity {severity.value} in category {category.value}: {summary}",
            metadata_={"severity": severity.value, "category": category.value},
            timestamp=now,
        )
        self.db.add(timeline)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=actor.id if actor else None,
            event_type="PRODUCTION_INCIDENT_CREATED",
            entity_type="PRODUCTION_INCIDENT",
            entity_id=incident.id,
            action="CREATE",
            timestamp=now,
            metadata_={
                "incident_id": incident.incident_id,
                "severity": severity.value,
                "category": category.value,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def create_security_incident(
        self,
        category: IncidentCategory,
        summary: str,
        affected_scope: str,
        metadata_: dict,
        severity: IncidentSeverity = IncidentSeverity.SEV2_HIGH,
    ) -> ProductionIncident:
        """Automated incident factory for detected security anomalies, prompt injections, and abuse."""
        return self.create_incident(
            summary=summary,
            severity=severity,
            category=category,
            affected_scope=affected_scope,
            detected_by=IncidentDetector.AUTOMATED_MONITOR,
            actor=None,
            metadata_=metadata_,
        )

    def transition_status(
        self,
        incident_id: str | uuid.UUID,
        new_status: IncidentStatus,
        actor: User,
        notes: str,
        root_cause: str | None = None,
        mitigation: str | None = None,
        resolution: str | None = None,
    ) -> ProductionIncident:
        incident = self.get_incident(incident_id)
        current_status = incident.status

        # Validate transition
        allowed = self.ALLOWED_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise AppException(
                status_code=400,
                code="INVALID_INCIDENT_TRANSITION",
                message=f"Cannot transition incident from {current_status.value} to {new_status.value}. Allowed transitions: {[s.value for s in allowed]}",
            )

        # Precondition checks
        if new_status == IncidentStatus.RESOLVED and not (resolution or incident.resolution or mitigation or incident.mitigation):
            raise AppException(
                status_code=400,
                code="RESOLUTION_NOTES_REQUIRED",
                message="Resolution or mitigation notes are mandatory before transitioning an incident to RESOLVED.",
            )

        now = datetime.now(UTC)
        incident.status = new_status
        incident.updated_at = now

        if new_status == IncidentStatus.ACKNOWLEDGED and not incident.acknowledged_at:
            incident.acknowledged_at = now
        elif new_status == IncidentStatus.MITIGATED:
            incident.mitigated_at = now
            if mitigation:
                incident.mitigation = mitigation
        elif new_status == IncidentStatus.RESOLVED:
            incident.resolved_at = now
            if resolution:
                incident.resolution = resolution
            if root_cause:
                incident.root_cause = root_cause
        elif new_status == IncidentStatus.CLOSED:
            incident.closed_at = now

        timeline = IncidentTimelineEvent(
            id=generate_uuid7(),
            incident_id=incident.id,
            actor_user_id=actor.id,
            event_type="STATUS_TRANSITION",
            message=f"Status transitioned from {current_status.value} to {new_status.value}. Notes: {notes}",
            metadata_={
                "from_status": current_status.value,
                "to_status": new_status.value,
                "notes": notes,
            },
            timestamp=now,
        )
        self.db.add(timeline)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=actor.id,
            event_type="PRODUCTION_INCIDENT_TRANSITIONED",
            entity_type="PRODUCTION_INCIDENT",
            entity_id=incident.id,
            action="UPDATE",
            timestamp=now,
            metadata_={
                "incident_id": incident.incident_id,
                "from_status": current_status.value,
                "to_status": new_status.value,
                "actor_email": actor.email,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def add_timeline_note(
        self,
        incident_id: str | uuid.UUID,
        actor: User,
        message: str,
        metadata_: dict | None = None,
    ) -> IncidentTimelineEvent:
        incident = self.get_incident(incident_id)
        now = datetime.now(UTC)

        event = IncidentTimelineEvent(
            id=generate_uuid7(),
            incident_id=incident.id,
            actor_user_id=actor.id,
            event_type="OPERATOR_NOTE",
            message=message,
            metadata_=metadata_ or {},
            timestamp=now,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_incident(self, identifier: str | uuid.UUID) -> ProductionIncident:
        query = self.db.query(ProductionIncident)
        if isinstance(identifier, uuid.UUID):
            incident = query.filter(ProductionIncident.id == identifier).first()
        else:
            try:
                parsed_uuid = uuid.UUID(str(identifier))
                incident = query.filter(
                    (ProductionIncident.id == parsed_uuid) | (ProductionIncident.incident_id == str(identifier))
                ).first()
            except ValueError:
                incident = query.filter(ProductionIncident.incident_id == str(identifier)).first()

        if not incident:
            raise NotFoundError(f"Incident '{identifier}' not found")
        return incident

    def list_incidents(
        self,
        status: IncidentStatus | None = None,
        severity: IncidentSeverity | None = None,
        category: IncidentCategory | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ProductionIncident]:
        query = self.db.query(ProductionIncident)
        if status:
            query = query.filter(ProductionIncident.status == status)
        if severity:
            query = query.filter(ProductionIncident.severity == severity)
        if category:
            query = query.filter(ProductionIncident.category == category)
        return (
            query.order_by(ProductionIncident.detected_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
