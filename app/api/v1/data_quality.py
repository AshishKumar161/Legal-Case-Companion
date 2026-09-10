from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import RequireOperatorPermission, get_db
from app.models.data_quality import DataQualityRun, DataQualityRunStatus
from app.models.operator import OperationalPermission
from app.models.user import User
from app.domain.payments.reconciliation_service import ReconciliationService

router = APIRouter(prefix="/data-quality", tags=["data-quality"])


@router.post("/reconcile", status_code=status.HTTP_200_OK)
def trigger_reconciliation(
    repair: bool = Query(False, description="If true, executes bounded, safe, idempotent repairs"),
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.SYSTEM_OPERATIONS)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Triggers an auditable operational data quality check and optional reconciliation repair."""
    service = ReconciliationService(db)
    run = service.audit_and_reconcile(repair=repair, actor=current_user)
    return {
        "run_id": run.run_id,
        "run_type": run.run_type.value,
        "status": run.status.value,
        "entities_audited": run.entities_audited,
        "anomalies_detected": run.anomalies_detected,
        "repairs_executed": run.repairs_executed,
        "anomaly_breakdown": run.anomaly_breakdown,
        "repair_summary": run.repair_summary,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


@router.get("/runs")
def list_reconciliation_runs(
    status_filter: DataQualityRunStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.SYSTEM_OPERATIONS)),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Lists historical data quality and reconciliation audit runs."""
    query = db.query(DataQualityRun)
    if status_filter:
        query = query.filter(DataQualityRun.status == status_filter)
    runs = query.order_by(DataQualityRun.started_at.desc()).offset(skip).limit(limit).all()
    return [
        {
            "run_id": r.run_id,
            "run_type": r.run_type.value,
            "status": r.status.value,
            "entities_audited": r.entities_audited,
            "anomalies_detected": r.anomalies_detected,
            "repairs_executed": r.repairs_executed,
            "started_at": r.started_at.isoformat(),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "is_automated": r.is_automated,
        }
        for r in runs
    ]
