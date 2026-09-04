import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import RequireOperatorPermission, RequireRole, get_db
from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.core.metrics import metrics_collector
from app.models.audit import AuditEvent
from app.models.incident import IncidentSeverity, IncidentStatus, ProductionIncident
from app.models.operator import OperationalPermission
from app.models.pilot import (
    AllowlistIdentifierType,
    AllowlistStatus,
    PilotAllowlistEntry,
)
from app.models.user import User, UserRole
from app.services.alert_service import AlertService

router = APIRouter(prefix="/pilot", tags=["pilot"])


# --------------------------------------------------------------------------
# SCHEMAS
# --------------------------------------------------------------------------


class AllowlistCreateRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=255)
    identifier_type: AllowlistIdentifierType = AllowlistIdentifierType.EMAIL
    role_target: UserRole | None = None
    valid_until: datetime | None = None
    notes: str | None = None


class AllowlistResponse(BaseModel):
    id: uuid.UUID
    identifier: str
    identifier_type: AllowlistIdentifierType
    role_target: UserRole | None
    status: AllowlistStatus
    valid_from: datetime
    valid_until: datetime | None
    notes: str | None
    added_by_user_id: uuid.UUID | None
    created_at: datetime


# --------------------------------------------------------------------------
# PILOT STATUS & OPERATIONAL DIAGNOSTICS
# --------------------------------------------------------------------------


@router.get("/status")
def get_pilot_status(
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.PILOT_GOVERNANCE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieves operational pilot state, capacity thresholds, active incidents, and SLO metrics."""
    now = datetime.now(UTC)

    # Active user counts
    active_clients = (
        db.query(func.count(User.id))
        .filter(User.role == UserRole.CLIENT, User.deleted_at.is_(None))
        .scalar()
        or 0
    )
    active_lawyers = (
        db.query(func.count(User.id))
        .filter(User.role == UserRole.LAWYER, User.deleted_at.is_(None))
        .scalar()
        or 0
    )

    # Active allowlist count
    allowlist_count = (
        db.query(func.count(PilotAllowlistEntry.id))
        .filter(PilotAllowlistEntry.status == AllowlistStatus.ACTIVE)
        .scalar()
        or 0
    )

    # Active incidents summary
    open_incidents = (
        db.query(ProductionIncident)
        .filter(ProductionIncident.status.in_([
            IncidentStatus.DETECTED,
            IncidentStatus.ACKNOWLEDGED,
            IncidentStatus.INVESTIGATING,
            IncidentStatus.MITIGATED,
        ]))
        .all()
    )
    incident_breakdown = {
        "sev1_critical": sum(1 for inc in open_incidents if inc.severity == IncidentSeverity.SEV1_CRITICAL),
        "sev2_high": sum(1 for inc in open_incidents if inc.severity == IncidentSeverity.SEV2_HIGH),
        "sev3_medium": sum(1 for inc in open_incidents if inc.severity == IncidentSeverity.SEV3_MEDIUM),
        "sev4_low": sum(1 for inc in open_incidents if inc.severity == IncidentSeverity.SEV4_LOW),
        "total_open": len(open_incidents),
    }

    # Time window status
    time_window_active = True
    if settings.PILOT_START_TIME and now < settings.PILOT_START_TIME:
        time_window_active = False
    if settings.PILOT_END_TIME and now > settings.PILOT_END_TIME:
        time_window_active = False

    return {
        "version": settings.APP_VERSION,
        "release_id": settings.RELEASE_ID,
        "environment": settings.ENVIRONMENT,
        "pilot_mode": settings.PILOT_MODE,
        "allowlist_enabled": settings.PILOT_ALLOWLIST_ENABLED,
        "signup_enabled": settings.PILOT_SIGNUP_ENABLED,
        "global_read_only": settings.PILOT_GLOBAL_READ_ONLY,
        "disabled_features": settings.PILOT_DISABLED_FEATURES,
        "time_window": {
            "start_time": settings.PILOT_START_TIME.isoformat() if settings.PILOT_START_TIME else None,
            "end_time": settings.PILOT_END_TIME.isoformat() if settings.PILOT_END_TIME else None,
            "is_active": time_window_active,
        },
        "capacity": {
            "clients": {
                "active": active_clients,
                "max": settings.PILOT_MAX_CLIENTS,
                "remaining": max(settings.PILOT_MAX_CLIENTS - active_clients, 0),
            },
            "lawyers": {
                "active": active_lawyers,
                "max": settings.PILOT_MAX_LAWYERS,
                "remaining": max(settings.PILOT_MAX_LAWYERS - active_lawyers, 0),
            },
        },
        "allowlist_active_count": allowlist_count,
        "active_incidents": incident_breakdown,
    }


# --------------------------------------------------------------------------
# ALLOWLIST MANAGEMENT
# --------------------------------------------------------------------------


@router.post("/allowlist", response_model=AllowlistResponse, status_code=status.HTTP_201_CREATED)
def add_allowlist_entry(
    req: AllowlistCreateRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.PILOT_GOVERNANCE)),
    db: Session = Depends(get_db),
):
    """Enrolls an identifier into the production pilot allowlist with full audit logging."""
    now = datetime.now(UTC)
    normalized = req.identifier.strip().lower()

    # Check if entry already active
    existing = (
        db.query(PilotAllowlistEntry)
        .filter(
            PilotAllowlistEntry.identifier == normalized,
            PilotAllowlistEntry.status == AllowlistStatus.ACTIVE,
        )
        .first()
    )
    if existing:
        return existing

    entry = PilotAllowlistEntry(
        id=generate_uuid7(),
        identifier=normalized,
        identifier_type=req.identifier_type,
        role_target=req.role_target,
        status=AllowlistStatus.ACTIVE,
        added_by_user_id=current_user.id,
        valid_from=now,
        valid_until=req.valid_until,
        notes=req.notes,
        created_at=now,
        updated_at=now,
    )
    db.add(entry)

    audit = AuditEvent(
        id=generate_uuid7(),
        actor_user_id=current_user.id,
        event_type="PILOT_ALLOWLIST_ENTRY_ADDED",
        entity_type="PILOT_ALLOWLIST_ENTRY",
        entity_id=entry.id,
        action="CREATE",
        timestamp=now,
        metadata_={
            "identifier": normalized,
            "type": req.identifier_type.value,
            "role_target": req.role_target.value if req.role_target else None,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/allowlist/{entry_id}", status_code=status.HTTP_200_OK)
def revoke_allowlist_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.PILOT_GOVERNANCE)),
    db: Session = Depends(get_db),
):
    """Revokes an approved allowlist entry immediately."""
    entry = db.query(PilotAllowlistEntry).filter(PilotAllowlistEntry.id == entry_id).first()
    if not entry:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Allowlist entry not found")

    now = datetime.now(UTC)
    entry.status = AllowlistStatus.REVOKED
    entry.updated_at = now

    audit = AuditEvent(
        id=generate_uuid7(),
        actor_user_id=current_user.id,
        event_type="PILOT_ALLOWLIST_ENTRY_REVOKED",
        entity_type="PILOT_ALLOWLIST_ENTRY",
        entity_id=entry.id,
        action="REVOKE",
        timestamp=now,
        metadata_={"identifier": entry.identifier},
    )
    db.add(audit)
    db.commit()
    return {"status": "REVOKED", "entry_id": str(entry_id), "identifier": entry.identifier}


@router.get("/allowlist", response_model=list[AllowlistResponse])
def list_allowlist(
    status_filter: AllowlistStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.PILOT_GOVERNANCE)),
    db: Session = Depends(get_db),
):
    """Lists pilot allowlist entries."""
    query = db.query(PilotAllowlistEntry)
    if status_filter:
        query = query.filter(PilotAllowlistEntry.status == status_filter)
    return query.order_by(PilotAllowlistEntry.created_at.desc()).offset(skip).limit(limit).all()


# --------------------------------------------------------------------------
# SRE OBSERVABILITY: SLOS & ALERT EVALUATION
# --------------------------------------------------------------------------


@router.get("/slos")
def get_slo_report(
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
) -> dict[str, Any]:
    """Retrieves machine-readable Service Level Objective (SLO) compliance and error-budget telemetry."""
    return metrics_collector.get_slo_report()


@router.get("/alerts")
def get_active_alerts(
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Evaluates actionable operational alert conditions against current metrics."""
    service = AlertService(db)
    return service.evaluate_alerts()


@router.get("/costs")
def get_cost_report(
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
) -> dict[str, Any]:
    """Retrieves operational infrastructure cost estimates per workflow (Part N)."""
    return metrics_collector.get_cost_observability_model()


@router.get("/funnel")
def get_funnel_report(
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieves client and lawyer journey funnel conversion and drop-off analytics (Part C)."""
    from app.services.workflow_telemetry_service import WorkflowTelemetryService

    service = WorkflowTelemetryService(db)
    return service.get_funnel_summary()

