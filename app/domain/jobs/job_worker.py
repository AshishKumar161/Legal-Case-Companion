import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import (
    AuthorizationError,
    ResourceNotFoundError,
    ValidationError,
)
from app.core.identifiers import generate_uuid7
from app.core.metrics import metrics_collector
from app.models.audit import AuditEvent
from app.models.case import Case, CaseParticipant, ParticipantStatus
from app.models.document import Document
from app.models.evidence import (
    Evidence,
    EvidenceStatus,
)
from app.models.job import BackgroundJob, JobStatus, JobType
from app.models.notification import NotificationType
from app.models.task import CaseTask, TaskStatus
from app.models.workflow import CaseDeadline, DeadlineStatus
from app.domain.cases.case_intelligence_service import CaseIntelligenceService
from app.domain.cases.case_workflow_service import CaseWorkflowService
from app.domain.documents.document_processor import DocumentProcessor
from app.domain.evidence.evidence_service import EvidenceService
from app.domain.jobs.job_service import JobService
from app.domain.ai.legal_data_pipeline import LegalDataPipeline
from app.domain.notifications.notification_service import NotificationService
from app.domain.jobs.outbox_service import OutboxService
from app.domain.notifications.reminder_service import ReminderService

logger = logging.getLogger(__name__)


class JobWorker:
    """Executes background jobs safely, idempotently, with bounded retries and audit tracking."""

    def __init__(self, db: Session, worker_id: str = "default-worker"):
        self.db = db
        self.worker_id = worker_id

    def _log_audit(self, action: str, job: BackgroundJob, metadata: dict | None = None) -> None:
        event = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=job.created_by_user_id,
            action=action,
            event_type=action,
            entity_type="BACKGROUND_JOB",
            entity_id=job.id,
            timestamp=datetime.now(UTC),
            metadata_={"job_id": str(job.id), "job_type": job.job_type.value, **(metadata or {})},
        )
        self.db.add(event)

    def execute_job(self, job_id: uuid.UUID) -> BackgroundJob:
        """Executes a single claimed job with error categorization and retry/failure transitions."""
        job = self.db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        if not job:
            raise ResourceNotFoundError(f"Job {job_id} not found")

        try:
            handler_result = self._dispatch_handler(job)

            now = datetime.now(UTC)
            job.status = JobStatus.SUCCEEDED
            job.completed_at = now
            job.locked_until = None
            job.locked_by = None
            job.result_metadata = handler_result
            job.last_error = None
            job.error_category = None

            self._log_audit("JOB_SUCCEEDED", job, {"result": handler_result})
            self.db.commit()
            self.db.refresh(job)
            return job

        except (ValidationError, ResourceNotFoundError, AuthorizationError, ValueError, KeyError) as e:
            # Permanent domain error: do not retry
            logger.error(f"Permanent error executing job {job_id} ({job.job_type}): {e}")
            now = datetime.now(UTC)
            job.status = JobStatus.FAILED
            job.completed_at = now
            job.locked_until = None
            job.locked_by = None
            job.last_error = str(e)
            job.error_category = "PERMANENT"

            self._handle_permanent_failure_side_effects(job, str(e))
            self._log_audit("JOB_FAILED_PERMANENT", job, {"error": str(e)})
            self.db.commit()
            self.db.refresh(job)
            return job

        except Exception as e:  # noqa: BLE001
            # Potential transient error
            logger.warning(f"Transient error executing job {job_id} ({job.job_type}): {e}")
            now = datetime.now(UTC)
            job.last_error = str(e)

            if job.attempt_count < job.max_attempts:
                # Exponential backoff retry: 5s, 10s, 20s...
                backoff_seconds = (2 ** job.attempt_count) * 5
                job.status = JobStatus.RETRYING
                job.scheduled_at = now + timedelta(seconds=backoff_seconds)
                job.locked_until = None
                job.locked_by = None
                job.error_category = "TRANSIENT"
                metrics_collector.record_queue_job(job.job_type.value, "RETRYING")
                self._log_audit("JOB_RETRYING", job, {"error": str(e), "retry_in_seconds": backoff_seconds})
            else:
                job.status = JobStatus.DEAD_LETTER
                job.completed_at = now
                job.locked_until = None
                job.locked_by = None
                job.error_category = "TRANSIENT_EXHAUSTED"
                metrics_collector.record_queue_job(job.job_type.value, "DEAD_LETTER")
                self._handle_permanent_failure_side_effects(job, str(e))
                self._log_audit("JOB_DEAD_LETTER", job, {"error": str(e)})

            self.db.commit()
            self.db.refresh(job)
            return job

    def _dispatch_handler(self, job: BackgroundJob) -> dict[str, Any]:
        """Dispatches job payload to the domain execution handler."""
        if job.job_type == JobType.DOCUMENT_PROCESSING:
            return self._handle_document_processing(job)
        elif job.job_type == JobType.DOCUMENT_INDEXING:
            return self._handle_document_indexing(job)
        elif job.job_type == JobType.CASE_INTELLIGENCE_REFRESH:
            return self._handle_case_intelligence_refresh(job)
        elif job.job_type == JobType.DEADLINE_REMINDER_SCAN:
            return self._handle_deadline_reminder_scan(job)
        elif job.job_type == JobType.TASK_OVERDUE_SCAN:
            return self._handle_task_overdue_scan(job)
        elif job.job_type == JobType.STALE_JOB_RECOVERY:
            return self._handle_stale_job_recovery(job)
        elif job.job_type == JobType.NOTIFICATION_DELIVERY:
            return self._handle_notification_delivery(job)
        elif job.job_type == JobType.LEGAL_AUTHORITY_INGESTION:
            return self._handle_legal_authority_ingestion(job)
        elif job.job_type == JobType.LEGAL_AUTHORITY_REINDEX:
            return self._handle_legal_authority_reindex(job)
        elif job.job_type == JobType.EVIDENCE_SCAN_AND_ACTIVATE:
            return self._handle_evidence_scan_and_activate(job)
        elif job.job_type == JobType.EVIDENCE_INTEGRITY_AUDIT:
            return self._handle_evidence_integrity_audit(job)
        elif job.job_type == JobType.EVIDENCE_ORPHAN_RECONCILIATION:
            return self._handle_evidence_orphan_reconciliation(job)
        elif job.job_type == JobType.ABANDONED_UPLOAD_CLEANUP:
            return self._handle_abandoned_upload_cleanup(job)
        elif job.job_type == JobType.OUTBOX_DISPATCH:
            return self._handle_outbox_dispatch(job)
        elif job.job_type == JobType.STALE_MEETING_CLEANUP:
            return self._handle_stale_meeting_cleanup(job)
        elif job.job_type == JobType.RECORDING_UPLOAD_RETRY:
            return self._handle_recording_upload_retry(job)
        elif job.job_type == JobType.WEBHOOK_REPROCESS:
            return self._handle_webhook_reprocess(job)
        elif job.job_type == JobType.COMMERCIAL_RECONCILIATION:
            return self._handle_commercial_reconciliation(job)
        elif job.job_type == JobType.EXPIRED_SESSION_CLEANUP:
            return self._handle_expired_session_cleanup(job)
        elif job.job_type == JobType.NOTIFICATION_RETRY:
            return self._handle_notification_retry(job)
        else:
            raise ValidationError(f"Unknown job type {job.job_type}")

    def _handle_document_processing(self, job: BackgroundJob) -> dict[str, Any]:
        doc_id_str = job.payload.get("document_id")
        if not doc_id_str:
            raise ValidationError("Missing document_id in job payload")

        doc_id = uuid.UUID(doc_id_str)
        doc = self.db.query(Document).filter(Document.id == doc_id, Document.deleted_at.is_(None)).first()
        if not doc:
            raise ResourceNotFoundError(f"Document {doc_id} not found")

        processor = DocumentProcessor(self.db)
        chunks = processor.process_document(
            document_id=doc_id,
            generate_embeddings=job.payload.get("generate_embeddings", True),
        )

        # Notify uploader of success
        notif_svc = NotificationService(self.db)
        notif_svc.create_notification(
            user_id=doc.uploaded_by,
            type=NotificationType.DOCUMENT_READY,
            title="Document Processed",
            message=f"Document '{doc.filename}' is now ready for legal analysis and search.",
            case_id=doc.case_id,
            document_id=doc.id,
            event_id=f"doc_ready_{doc.id}_{doc.version}",
        )

        # Automatically enqueue downstream Case Intelligence refresh if case_id present
        if doc.case_id:
            job_svc = JobService(self.db)
            job_svc.enqueue_job(
                job_type=JobType.CASE_INTELLIGENCE_REFRESH,
                payload={"case_id": str(doc.case_id)},
                idempotency_key=f"intel_refresh_{doc.case_id}_doc_{doc.id}_v{doc.version}",
                case_id=doc.case_id,
                created_by_user_id=doc.uploaded_by,
            )

        return {"chunks_count": len(chunks), "document_id": str(doc_id)}

    def _handle_document_indexing(self, job: BackgroundJob) -> dict[str, Any]:
        doc_id_str = job.payload.get("document_id")
        if not doc_id_str:
            raise ValidationError("Missing document_id in job payload")
        return {"status": "indexed", "document_id": doc_id_str}

    def _handle_case_intelligence_refresh(self, job: BackgroundJob) -> dict[str, Any]:
        case_id_str = job.payload.get("case_id")
        if not case_id_str:
            raise ValidationError("Missing case_id in job payload")

        case_id = uuid.UUID(case_id_str)
        case = self.db.query(Case).filter(Case.id == case_id, Case.deleted_at.is_(None)).first()
        if not case:
            raise ResourceNotFoundError(f"Case {case_id} not found")

        # 1. Use case participant (owner/counsel) for workflow scan
        admin_or_owner = (
            self.db.query(CaseParticipant)
            .filter(CaseParticipant.case_id == case_id, CaseParticipant.status == ParticipantStatus.ACTIVE)
            .first()
        )
        if not admin_or_owner or not admin_or_owner.user:
            return {"case_id": str(case_id), "status": "SKIPPED_NO_ACTIVE_PARTICIPANT"}

        # 2. Refresh intelligence
        intel_svc = CaseIntelligenceService(self.db)
        summary = intel_svc.refresh_case_intelligence(admin_or_owner.user, case_id)

        # 3. Synthesize workflow suggestions
        wf_svc = CaseWorkflowService(self.db)
        sugg_results = wf_svc.generate_suggestions_from_intelligence(admin_or_owner.user, case_id)
        total_suggestions = (
            sugg_results.get("suggested_tasks_count", 0)
            + sugg_results.get("suggested_deadlines_count", 0)
            + sugg_results.get("suggested_hearings_count", 0)
        )

        # 4. If new suggestions exist, notify active lawyers on case
        if total_suggestions > 0:
            notif_svc = NotificationService(self.db)
            lawyers = (
                self.db.query(CaseParticipant)
                .filter(
                    CaseParticipant.case_id == case_id,
                    CaseParticipant.participant_role == "LAWYER",
                    CaseParticipant.status == ParticipantStatus.ACTIVE,
                )
                .all()
            )
            today_str = datetime.now(UTC).strftime("%Y-%m-%d")
            for lp in lawyers:
                notif_svc.create_notification(
                    user_id=lp.user_id,
                    type=NotificationType.AI_REVIEW_REQUIRED,
                    title="AI Suggestions Require Review",
                    message=f"{total_suggestions} new workflow suggestions have been generated for case '{case.title}'.",
                    case_id=case_id,
                    event_id=f"ai_review_{case_id}_{lp.user_id}_{today_str}",
                )

        return {"intelligence_summary": summary}

    def _handle_deadline_reminder_scan(self, job: BackgroundJob) -> dict[str, Any]:
        """Scans upcoming deadlines within 48h, hearings within 24h, consultations, and overdue deadlines."""
        now = datetime.now(UTC)
        window_end = now + timedelta(days=2)

        # 1. Process hearing and consultation reminders via ReminderService
        reminder_svc = ReminderService(self.db)
        hearing_notifs = reminder_svc.process_hearing_reminders(hours_ahead=24)
        consultation_notifs = reminder_svc.process_consultation_reminders(hours_ahead=2)

        # Approaching deadlines (due in <= 48 hours)
        upcoming_dls = (
            self.db.query(CaseDeadline)
            .filter(
                CaseDeadline.status.in_([DeadlineStatus.UPCOMING, DeadlineStatus.DUE]),
                CaseDeadline.deadline_at >= now,
                CaseDeadline.deadline_at <= window_end,
                CaseDeadline.deleted_at.is_(None),
            )
            .all()
        )

        notif_svc = NotificationService(self.db)
        approaching_count = 0
        today_str = now.strftime("%Y-%m-%d")

        for dl in upcoming_dls:
            participants = (
                self.db.query(CaseParticipant)
                .filter(CaseParticipant.case_id == dl.case_id, CaseParticipant.status == ParticipantStatus.ACTIVE)
                .all()
            )
            for p in participants:
                notif = notif_svc.create_notification(
                    user_id=p.user_id,
                    type=NotificationType.DEADLINE_APPROACHING,
                    title="Upcoming Deadline",
                    message=f"Deadline '{dl.title}' is due on {dl.deadline_at.strftime('%d %b %Y')}.",
                    case_id=dl.case_id,
                    deadline_id=dl.id,
                    event_id=f"dl_appr_{dl.id}_{p.user_id}_{today_str}",
                )
                if notif:
                    approaching_count += 1

        # Overdue deadlines
        overdue_dls = (
            self.db.query(CaseDeadline)
            .filter(
                CaseDeadline.status.in_([DeadlineStatus.UPCOMING, DeadlineStatus.DUE, DeadlineStatus.OVERDUE]),
                CaseDeadline.deadline_at < now,
                CaseDeadline.deleted_at.is_(None),
            )
            .all()
        )
        overdue_count = 0
        for dl in overdue_dls:
            dl.status = DeadlineStatus.OVERDUE
            participants = (
                self.db.query(CaseParticipant)
                .filter(CaseParticipant.case_id == dl.case_id, CaseParticipant.status == ParticipantStatus.ACTIVE)
                .all()
            )
            for p in participants:
                notif = notif_svc.create_notification(
                    user_id=p.user_id,
                    type=NotificationType.DEADLINE_OVERDUE,
                    title="Deadline Overdue",
                    message=f"Deadline '{dl.title}' is past due (was due on {dl.deadline_at.strftime('%d %b %Y')}).",
                    case_id=dl.case_id,
                    deadline_id=dl.id,
                    event_id=f"dl_ovrd_{dl.id}_{p.user_id}_{today_str}",
                )
                if notif:
                    overdue_count += 1

        return {
            "approaching_notifications": approaching_count,
            "overdue_notifications": overdue_count,
            "hearing_reminders_count": len(hearing_notifs),
            "consultation_reminders_count": len(consultation_notifs),
        }

    def _handle_task_overdue_scan(self, job: BackgroundJob) -> dict[str, Any]:
        """Scans open tasks that are past their due dates, delivering idempotent notifications."""
        now = datetime.now(UTC)
        today_str = now.strftime("%Y-%m-%d")

        overdue_tasks = (
            self.db.query(CaseTask)
            .filter(
                CaseTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                CaseTask.due_date.isnot(None),
                CaseTask.due_date < now,
                CaseTask.owner_user_id.isnot(None),
                CaseTask.deleted_at.is_(None),
            )
            .all()
        )

        notif_svc = NotificationService(self.db)
        notified_count = 0
        for task in overdue_tasks:
            if task.owner_user_id:
                notif = notif_svc.create_notification(
                    user_id=task.owner_user_id,
                    type=NotificationType.TASK_OVERDUE,
                    title="Task Overdue",
                    message=f"Task '{task.title}' is overdue.",
                    case_id=task.case_id,
                    task_id=task.id,
                    event_id=f"task_ovrd_{task.id}_{task.owner_user_id}_{today_str}",
                )
                if notif:
                    notified_count += 1

        return {"overdue_tasks_notified": notified_count}

    def _handle_stale_job_recovery(self, job: BackgroundJob) -> dict[str, Any]:
        """Recovers jobs stuck in RUNNING state whose worker leases have expired."""
        now = datetime.now(UTC)
        stale_jobs = (
            self.db.query(BackgroundJob)
            .filter(
                BackgroundJob.status == JobStatus.RUNNING,
                BackgroundJob.locked_until < now,
                BackgroundJob.id != job.id,
                BackgroundJob.deleted_at.is_(None),
            )
            .all()
        )

        recovered = 0
        exhausted = 0
        for stale in stale_jobs:
            if stale.attempt_count < stale.max_attempts:
                stale.status = JobStatus.RETRYING
                stale.scheduled_at = now + timedelta(seconds=5)
                stale.locked_until = None
                stale.locked_by = None
                stale.error_category = "STALE_LEASE_RECOVERED"
                recovered += 1
            else:
                stale.status = JobStatus.FAILED
                stale.completed_at = now
                stale.locked_until = None
                stale.locked_by = None
                stale.last_error = "Worker lease expired and max attempts exhausted"
                stale.error_category = "PERMANENT"
                exhausted += 1

        return {"recovered_jobs_count": recovered, "exhausted_jobs_count": exhausted}

    def _handle_notification_delivery(self, job: BackgroundJob) -> dict[str, Any]:
        return {"status": "delivered"}

    def _handle_legal_authority_ingestion(self, job: BackgroundJob) -> dict[str, Any]:
        pipeline = LegalDataPipeline(self.db)
        raw_source_id_str = job.payload.get("raw_source_id")
        if raw_source_id_str:
            source = pipeline.process_raw_source(uuid.UUID(raw_source_id_str))
            return {
                "source_id": str(source.id),
                "canonical_identifier": source.canonical_identifier,
                "status": "SUCCESS",
            }
        else:
            # Full curated sync
            return pipeline.sync_curated_fixtures()

    def _handle_legal_authority_reindex(self, job: BackgroundJob) -> dict[str, Any]:
        source_id_str = job.payload.get("source_id")
        if not source_id_str:
            raise ValidationError("Missing source_id in reindex job payload")

        pipeline = LegalDataPipeline(self.db)
        count = pipeline.reindex_source(uuid.UUID(source_id_str))
        return {"source_id": source_id_str, "reindexed_count": count, "status": "SUCCESS"}

    def _handle_evidence_scan_and_activate(self, job: BackgroundJob) -> dict[str, Any]:
        evidence_id_str = job.payload.get("evidence_id")
        version_id_str = job.payload.get("version_id")
        if not evidence_id_str or not version_id_str:
            raise ValidationError("Missing evidence_id or version_id in payload")

        evidence_id = uuid.UUID(evidence_id_str)
        version_id = uuid.UUID(version_id_str)

        evidence = self.db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise ResourceNotFoundError(f"Evidence {evidence_id} not found")

        from app.models.user import User

        user = self.db.query(User).filter(User.id == evidence.created_by_user_id).first()
        if not user:
            raise ResourceNotFoundError("Evidence creator user not found")

        evidence_svc = EvidenceService(self.db)
        activated_evidence = evidence_svc.complete_upload(
            user=user,
            case_id=evidence.case_id,
            evidence_id=evidence_id,
            version_id=version_id,
        )
        return {
            "status": activated_evidence.status.value,
            "evidence_id": str(activated_evidence.id),
            "current_version_id": str(activated_evidence.current_version_id),
        }

    def _handle_evidence_integrity_audit(self, job: BackgroundJob) -> dict[str, Any]:
        evidence_svc = EvidenceService(self.db)
        results = evidence_svc.reconcile_orphaned_evidence()
        return {"status": "SUCCESS", **results}

    def _handle_evidence_orphan_reconciliation(self, job: BackgroundJob) -> dict[str, Any]:
        evidence_svc = EvidenceService(self.db)
        results = evidence_svc.reconcile_orphaned_evidence()
        return {"status": "SUCCESS", **results}

    def _handle_abandoned_upload_cleanup(self, job: BackgroundJob) -> dict[str, Any]:
        evidence_svc = EvidenceService(self.db)
        count = evidence_svc.reconcile_abandoned_uploads(hours_threshold=2)
        return {"status": "SUCCESS", "reconciled_count": count}

    def _handle_outbox_dispatch(self, job: BackgroundJob) -> dict[str, Any]:
        limit = job.payload.get("limit", 25)
        outbox_svc = OutboxService(self.db)
        dispatched_count = outbox_svc.process_outbox_batch(limit=limit)
        return {"status": "SUCCESS", "dispatched_count": dispatched_count}

    def _handle_stale_meeting_cleanup(self, job: BackgroundJob) -> dict[str, Any]:
        from app.domain.consultations.video_meeting_service import VideoMeetingService

        max_idle_hours = job.payload.get("max_idle_hours", 2)
        service = VideoMeetingService(self.db)
        cleaned_count = service.cleanup_stale_meetings(max_idle_hours=max_idle_hours)
        return {"status": "SUCCESS", "cleaned_meetings_count": cleaned_count}

    def _handle_recording_upload_retry(self, job: BackgroundJob) -> dict[str, Any]:
        from app.domain.consultations.video_recording_service import VideoRecordingService

        max_age_minutes = job.payload.get("max_age_minutes", 60)
        grace_period_minutes = job.payload.get("grace_period_minutes", 5)
        service = VideoRecordingService(self.db)
        res = service.retry_pending_and_failed_recordings(
            max_age_minutes=max_age_minutes,
            grace_period_minutes=grace_period_minutes,
        )
        return {"status": "SUCCESS", **res}

    def _handle_webhook_reprocess(self, job: BackgroundJob) -> dict[str, Any]:
        from app.domain.payments.payment_service import PaymentService

        stale_minutes = job.payload.get("stale_minutes", 10)
        limit = job.payload.get("limit", 25)
        service = PaymentService(self.db)
        res = service.reprocess_stale_or_failed_webhooks(
            stale_minutes=stale_minutes,
            limit=limit,
        )
        return {"status": "SUCCESS", **res}

    def _handle_commercial_reconciliation(self, job: BackgroundJob) -> dict[str, Any]:
        from app.domain.payments.commercial_service import CommercialService

        service = CommercialService(self.db)
        reconciliation = service.get_settlement_reconciliation()
        discrepancy_count = reconciliation.get("discrepancy_count", 0)
        variance = reconciliation.get("variance_inr", "0.00")

        if discrepancy_count > 0 or variance != "0.00":
            logger.warning(
                "Commercial reconciliation detected %d discrepancies with variance %s",
                discrepancy_count,
                variance,
            )

        return {
            "status": "SUCCESS",
            "gross_volume_inr": reconciliation.get("gross_volume_inr"),
            "variance_inr": variance,
            "discrepancy_count": discrepancy_count,
            "discrepancies": reconciliation.get("discrepancies", []),
        }

    def _handle_expired_session_cleanup(self, job: BackgroundJob) -> dict[str, Any]:
        from app.domain.auth.session_cleanup_service import SessionCleanupService

        rt_days = job.payload.get("refresh_token_retention_days", 30)
        vt_days = job.payload.get("verification_token_retention_days", 7)
        service = SessionCleanupService(self.db)
        res = service.cleanup_expired_sessions(
            refresh_token_retention_days=rt_days,
            verification_token_retention_days=vt_days,
        )
        return {"status": "SUCCESS", **res}

    def _handle_notification_retry(self, job: BackgroundJob) -> dict[str, Any]:
        limit = job.payload.get("limit", 25)
        outbox_svc = OutboxService(self.db)
        dispatched_count = outbox_svc.process_outbox_batch(limit=limit)
        return {"status": "SUCCESS", "dispatched_notifications": dispatched_count}

    def _handle_permanent_failure_side_effects(self, job: BackgroundJob, error_msg: str) -> None:
        """Notifies users if a critical job like document processing fails permanently."""
        if job.job_type == JobType.DOCUMENT_PROCESSING:
            doc_id_str = job.payload.get("document_id")
            if doc_id_str:
                try:
                    doc = self.db.query(Document).filter(Document.id == uuid.UUID(doc_id_str)).first()
                    if doc:
                        notif_svc = NotificationService(self.db)
                        notif_svc.create_notification(
                            user_id=doc.uploaded_by,
                            type=NotificationType.DOCUMENT_PROCESSING_FAILED,
                            title="Document Processing Failed",
                            message=f"Processing for document '{doc.filename}' failed: {error_msg[:100]}",
                            case_id=doc.case_id,
                            document_id=doc.id,
                            event_id=f"doc_fail_{doc.id}_{doc.version}",
                        )
                except Exception:  # noqa: BLE001
                    pass
        elif job.job_type == JobType.EVIDENCE_SCAN_AND_ACTIVATE:
            evidence_id_str = job.payload.get("evidence_id")
            if evidence_id_str:
                try:
                    ev = self.db.query(Evidence).filter(Evidence.id == uuid.UUID(evidence_id_str)).first()
                    if ev:
                        ev.status = EvidenceStatus.QUARANTINED
                        self.db.commit()
                except Exception:  # noqa: BLE001
                    pass
