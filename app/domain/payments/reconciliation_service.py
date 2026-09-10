from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.case import Case, CaseParticipant
from app.models.consultation import Consultation, ConsultationStatus
from app.models.data_quality import (
    DataQualityRun,
    DataQualityRunStatus,
    DataQualityRunType,
)
from app.models.evidence import Evidence, EvidenceCustodyEvent, EvidenceVersion
from app.models.job import BackgroundJob, JobStatus
from app.models.user import User


class ReconciliationService:
    """Operational data-quality auditing and idempotent reconciliation engine (Part S)."""

    def __init__(self, db: Session):
        self.db = db

    def _generate_run_id(self) -> str:
        today_str = datetime.now(UTC).strftime("%Y%m%d")
        count = (
            self.db.query(func.count(DataQualityRun.id))
            .filter(DataQualityRun.run_id.like(f"DQR-{today_str}-%"))
            .scalar()
            or 0
        )
        return f"DQR-{today_str}-{count + 1:04d}"

    def audit_and_reconcile(
        self,
        repair: bool = False,
        actor: User | None = None,
    ) -> DataQualityRun:
        now = datetime.now(UTC)
        run_id = self._generate_run_id()
        run_type = DataQualityRunType.AUDIT_AND_REPAIR if repair else DataQualityRunType.AUDIT_ONLY

        run = DataQualityRun(
            id=generate_uuid7(),
            run_id=run_id,
            run_type=run_type,
            status=DataQualityRunStatus.RUNNING,
            started_at=now,
            triggered_by_user_id=actor.id if actor else None,
            is_automated=actor is None,
            anomaly_breakdown={},
            repair_summary={},
        )
        self.db.add(run)
        self.db.commit()

        anomalies_detected = 0
        repairs_executed = 0
        anomaly_breakdown: dict[str, Any] = {}
        repair_summary: dict[str, Any] = {}
        total_entities_audited = 0

        try:
            # 1. Stale Running Background Jobs (running for > 30 minutes)
            stale_threshold = now - timedelta(minutes=30)
            stale_jobs = (
                self.db.query(BackgroundJob)
                .filter(BackgroundJob.status == JobStatus.RUNNING, BackgroundJob.started_at < stale_threshold)
                .all()
            )
            total_entities_audited += len(stale_jobs)
            if stale_jobs:
                anomalies_detected += len(stale_jobs)
                anomaly_breakdown["stale_running_jobs"] = [str(j.id) for j in stale_jobs]
                if repair:
                    for j in stale_jobs:
                        j.status = JobStatus.PENDING
                        j.attempt_count += 1
                        j.last_error = "Reconciled by automated data quality job (stale worker lease)"
                        repairs_executed += 1
                    repair_summary["stale_jobs_reset"] = len(stale_jobs)

            # 2. Expired Unconfirmed Consultations (requested > 24 hours ago, past scheduled time)
            expired_consult_cutoff = now - timedelta(hours=24)
            expired_consults = (
                self.db.query(Consultation)
                .filter(
                    Consultation.status == ConsultationStatus.REQUESTED,
                    Consultation.scheduled_at < expired_consult_cutoff,
                )
                .all()
            )
            total_entities_audited += len(expired_consults)
            if expired_consults:
                anomalies_detected += len(expired_consults)
                anomaly_breakdown["expired_requested_consultations"] = [str(c.id) for c in expired_consults]
                if repair:
                    for c in expired_consults:
                        c.status = ConsultationStatus.CANCELLED
                        repairs_executed += 1
                    repair_summary["expired_consultations_cancelled"] = len(expired_consults)

            # 3. Orphaned Case Participants (case_id does not exist)
            valid_case_ids = {c.id for c in self.db.query(Case.id).all()}
            all_participants = self.db.query(CaseParticipant).all()
            total_entities_audited += len(all_participants)
            orphaned_parts = [p for p in all_participants if p.case_id not in valid_case_ids]
            if orphaned_parts:
                anomalies_detected += len(orphaned_parts)
                anomaly_breakdown["orphaned_case_participants"] = [str(p.id) for p in orphaned_parts]
                if repair:
                    for p in orphaned_parts:
                        self.db.delete(p)
                        repairs_executed += 1
                    repair_summary["orphaned_participants_pruned"] = len(orphaned_parts)

            # 4. Orphaned Evidence Versions (evidence_id does not exist)
            valid_evidence_ids = {e.id for e in self.db.query(Evidence.id).all()}
            all_versions = self.db.query(EvidenceVersion).all()
            total_entities_audited += len(all_versions)
            orphaned_versions = [v for v in all_versions if v.evidence_id not in valid_evidence_ids]
            if orphaned_versions:
                anomalies_detected += len(orphaned_versions)
                anomaly_breakdown["orphaned_evidence_versions"] = [str(v.id) for v in orphaned_versions]
                if repair:
                    for v in orphaned_versions:
                        self.db.delete(v)
                        repairs_executed += 1
                    repair_summary["orphaned_versions_pruned"] = len(orphaned_versions)

            # 5. Custody Ledger Continuity Gaps
            custody_events = self.db.query(EvidenceCustodyEvent).all()
            total_entities_audited += len(custody_events)
            custody_event_ids = {ce.id for ce in custody_events}
            broken_links = [
                ce for ce in custody_events
                if ce.previous_event_id is not None and ce.previous_event_id not in custody_event_ids
            ]
            if broken_links:
                anomalies_detected += len(broken_links)
                anomaly_breakdown["custody_chain_gap_events"] = [str(ce.id) for ce in broken_links]

            # Complete run status
            run.completed_at = datetime.now(UTC)
            run.entities_audited = total_entities_audited
            run.anomalies_detected = anomalies_detected
            run.repairs_executed = repairs_executed
            run.anomaly_breakdown = anomaly_breakdown
            run.repair_summary = repair_summary

            if anomalies_detected == 0:
                run.status = DataQualityRunStatus.COMPLETED_CLEAN
            elif repair and repairs_executed > 0:
                run.status = DataQualityRunStatus.COMPLETED_WITH_REPAIRS
            else:
                run.status = DataQualityRunStatus.COMPLETED_WITH_ANOMALIES

            audit = AuditEvent(
                id=generate_uuid7(),
                actor_user_id=actor.id if actor else None,
                event_type="DATA_QUALITY_RECONCILIATION_COMPLETED",
                entity_type="DATA_QUALITY_RUN",
                entity_id=run.id,
                action="AUDIT" if not repair else "REPAIR",
                timestamp=run.completed_at,
                metadata_={
                    "run_id": run.run_id,
                    "anomalies": anomalies_detected,
                    "repairs": repairs_executed,
                    "status": run.status.value,
                },
            )
            self.db.add(audit)
            self.db.commit()
            self.db.refresh(run)
            return run

        except Exception as e:
            self.db.rollback()
            run.status = DataQualityRunStatus.FAILED
            run.error_message = str(e)
            run.completed_at = datetime.now(UTC)
            self.db.commit()
            raise
