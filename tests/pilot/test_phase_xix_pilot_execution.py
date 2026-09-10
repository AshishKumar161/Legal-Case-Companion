import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.metrics import metrics_collector
from app.core.security import create_access_token
from app.models.ai_review import (
    AIReviewCategory,
    AIReviewOutcome,
    AIReviewRecord,
    AIReviewSeverity,
    AIReviewStatus,
)
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole
from app.models.consultation import Consultation, ConsultationStatus
from app.models.data_quality import DataQualityRunStatus
from app.models.experiment import ExperimentStatus, PilotExperiment
from app.models.feedback import FeedbackCategory, FeedbackType, PilotFeedback
from app.models.job import BackgroundJob, JobStatus, JobType
from app.models.operator import OperationalPermission
from app.models.support import SupportCase, SupportCaseSeverity, SupportCaseStatus
from app.models.user import AccountStatus, User, UserRole
from app.domain.ai.ai_evaluation_service import AIEvaluationService
from app.domain.ai.ai_review_service import AIReviewService
from app.domain.governance.experiment_service import ExperimentService
from app.domain.users.operator_service import OperatorService
from app.domain.payments.reconciliation_service import ReconciliationService
from app.domain.users.support_service import SupportService
from app.domain.governance.workflow_telemetry_service import (
    WorkflowExecutionStatus,
    WorkflowTelemetryService,
    WorkflowType,
)


def create_test_user(
    db: Session,
    email: str,
    role: UserRole = UserRole.CLIENT,
    account_status: AccountStatus = AccountStatus.ACTIVE,
) -> User:
    user = User(
        id=generate_uuid7(),
        email=email,
        password_hash="argon2id$mock$hash",
        role=role,
        account_status=account_status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id), role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------
# 1. PILOT EXPERIMENTATION FRAMEWORK
# --------------------------------------------------------------------------


def test_pilot_experimentation_lifecycle(client: TestClient, db: Session):
    admin_user = create_test_user(db, f"exp_admin_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.ADMIN)
    OperatorService(db).grant_permission(admin_user, admin_user.id, OperationalPermission.PILOT_GOVERNANCE)
    headers = get_auth_headers(admin_user)

    exp_id = f"EXP-{uuid.uuid4().hex[:6].upper()}"

    # 1. Create experiment
    payload = {
        "experiment_id": exp_id,
        "hypothesis": "Simplified advocate availability configuration increases consultation booking rate by 20%",
        "cohort": "DELHI_BAR_COHORT_A",
        "success_metrics": {"consultation_booking_rate": ">0.25"},
        "failure_metrics": {"advocate_dropoff_rate": ">0.15"},
        "notes": "Testing wizard UI variant in Stage 2 pilot",
    }
    res = client.post("/api/v1/pilot/experiments", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["experiment_id"] == exp_id
    assert data["status"] == "PLANNED"

    # 2. Transition PLANNED -> ACTIVE
    res_trans = client.post(
        f"/api/v1/pilot/experiments/{exp_id}/transition",
        json={"new_status": "ACTIVE", "notes": "Activated for 50 advocates"},
        headers=headers,
    )
    assert res_trans.status_code == 200
    assert res_trans.json()["status"] == "ACTIVE"

    # 3. Transition ACTIVE -> COMPLETED with Decision
    res_comp = client.post(
        f"/api/v1/pilot/experiments/{exp_id}/transition",
        json={
            "new_status": "COMPLETED",
            "decision": "GRADUATE_TO_DEFAULT",
            "notes": "Hypothesis validated: bookings increased by 28%",
        },
        headers=headers,
    )
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"
    assert res_comp.json()["decision"] == "GRADUATE_TO_DEFAULT"


# --------------------------------------------------------------------------
# 2. PRIVACY-CONSCIOUS WORKFLOW & FUNNEL TELEMETRY
# --------------------------------------------------------------------------


def test_workflow_telemetry_and_privacy_sanitization(client: TestClient, db: Session):
    user = create_test_user(db, f"telemetry_user_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT)
    telemetry_svc = WorkflowTelemetryService(db)

    # Record event with sensitive data
    event = telemetry_svc.record_workflow_event(
        workflow=WorkflowType.CASE_CREATION,
        status=WorkflowExecutionStatus.SUCCESS,
        user_id=user.id,
        duration_ms=245.5,
        metadata={
            "password": "SuperSecretPassword123!",
            "access_token": "eyJhbGciOiJ...",
            "raw_content": "Confidential settlement agreement between parties...",
            "case_type": "COMMERCIAL_DISPUTE",
            "court": "DELHI_HIGH_COURT",
        },
    )

    # Verify sensitive keys are stripped (Part T)
    safe_meta = event.metadata_
    assert "password" not in safe_meta
    assert "access_token" not in safe_meta
    assert "raw_content" not in safe_meta
    assert safe_meta["case_type"] == "COMMERCIAL_DISPUTE"
    assert safe_meta["duration_ms"] == 245.5

    # Check funnel report
    funnel = telemetry_svc.get_funnel_summary()
    assert "client_funnel" in funnel
    assert "lawyer_funnel" in funnel
    assert funnel["sample_confidence"] in ("HIGH", "INSUFFICIENT_SAMPLE_SIZE")


# --------------------------------------------------------------------------
# 3. ZERO-TRUST SUPPORT INTELLIGENCE & CASE BOUNDARIES
# --------------------------------------------------------------------------


def test_support_case_lifecycle_and_zero_trust_boundaries(client: TestClient, db: Session):
    client_user = create_test_user(db, f"client_sup_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT)
    client_headers = get_auth_headers(client_user)

    operator_user = create_test_user(db, f"op_sup_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.ADMIN)
    OperatorService(db).grant_permission(operator_user, operator_user.id, OperationalPermission.USER_SUPPORT)
    op_headers = get_auth_headers(operator_user)

    other_client = create_test_user(db, f"other_client_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT)
    other_headers = get_auth_headers(other_client)

    # 1. Client creates support case
    case_payload = {
        "category": "CONSULTATION_TECHNICAL",
        "workflow": "VIDEO_CALL",
        "subject": "Camera permission issue during advocate consultation",
        "description": "Browser blocked WebRTC media tracks on Android Chrome",
        "severity": "SEV3_MEDIUM",
    }
    res = client.post("/api/v1/support/cases", json=case_payload, headers=client_headers)
    assert res.status_code == 201
    case_data = res.json()
    case_id = case_data["support_case_id"]
    assert case_data["status"] == "OPEN"

    # 2. Other client cannot view this support case (BOLA Defense)
    res_idor = client.get(f"/api/v1/support/cases/{case_id}", headers=other_headers)
    assert res_idor.status_code == 403

    # 3. Support operator can view and escalate ticket
    res_esc = client.post(
        f"/api/v1/support/cases/{case_id}/escalate",
        json={"target_level": 2, "notes": "Escalating to engineering for TURN check"},
        headers=op_headers,
    )
    assert res_esc.status_code == 200
    assert res_esc.json()["escalation_level"] == 2
    assert res_esc.json()["status"] == "IN_PROGRESS"

    # 4. Support operator resolves ticket
    res_res = client.post(
        f"/api/v1/support/cases/{case_id}/resolve",
        json={
            "resolution_code": "RESOLVED_EXPLAINED",
            "resolution_notes": "Advised user to allow camera permissions in Chrome site settings",
        },
        headers=op_headers,
    )
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "RESOLVED"
    assert res_res.json()["resolution_code"] == "RESOLVED_EXPLAINED"


# --------------------------------------------------------------------------
# 4. STRUCTURED USER FEEDBACK WITH URL SANITIZATION
# --------------------------------------------------------------------------


def test_structured_feedback_taxonomy_and_sanitization(client: TestClient, db: Session):
    user = create_test_user(db, f"fb_user_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.CLIENT)
    headers = get_auth_headers(user)

    # Submit feedback with secret query parameter in URL
    raw_page_url = "https://app.legalcasecompanion.in/cases/018f3a5b-0001?access_token=secret123&pii=confidential#section"
    payload = {
        "category": "CONFUSING_UX",
        "feedback_type": "USABILITY",
        "severity": "SEV3",
        "workflow": "EVIDENCE_UPLOAD",
        "sentiment": "FRUSTRATED",
        "reproducibility": "SOMETIMES",
        "description": "The file upload progress bar did not indicate completion clearly.",
        "page_url": raw_page_url,
    }
    res = client.post("/api/v1/feedback", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["feedback_type"] == "USABILITY"

    # Verify query parameters are stripped for privacy
    assert "access_token" not in data["page_url"]
    assert "secret123" not in data["page_url"]
    assert data["page_url"].startswith("/cases/018f3a5b-0001")


# --------------------------------------------------------------------------
# 5. AI QUALITY EVALUATION & BENCHMARK HARNESS
# --------------------------------------------------------------------------


def test_ai_benchmark_evaluation_harness():
    eval_service = AIEvaluationService()
    report = eval_service.run_benchmark()

    assert report["scenarios_total"] >= 5
    assert report["scenarios_passed"] == report["scenarios_total"]
    assert report["accuracy_pct"] == 100.0
    assert report["evaluation_result"] == "PASSED"

    # Verify prompt injection defanging scenario passed
    scen4 = next(r for r in report["results"] if r["scenario_id"] == "SCEN-004-PROMPT-INJECTION-DEFENSE")
    assert scen4["status"] == "PASSED"
    assert scen4["behavior"] == "PROMPT_INJECTION_DEFANGED"


# --------------------------------------------------------------------------
# 6. AI HUMAN-IN-THE-LOOP REVIEW WORKFLOW
# --------------------------------------------------------------------------


def test_ai_human_review_lifecycle(client: TestClient, db: Session):
    lawyer_user = create_test_user(db, f"lawyer_rev_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.LAWYER)
    lawyer_headers = get_auth_headers(lawyer_user)

    admin_user = create_test_user(db, f"compliance_admin_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.ADMIN)
    OperatorService(db).grant_permission(admin_user, admin_user.id, OperationalPermission.COMPLIANCE_OPERATIONS)
    admin_headers = get_auth_headers(admin_user)

    # 1. Submit AI review
    payload = {
        "category": "OUTDATED_LAW",
        "severity": "SEV2_HIGH",
        "review_outcome": "CONFIRMED_DEFECT",
        "original_prompt_snippet": "What section governs murder?",
        "original_answer_snippet": "Murder is governed under Section 302 of the Indian Penal Code.",
        "corrected_interpretation": "For offences post-July 1 2024, Section 103 BNS applies.",
        "model_version": "gpt-4o",
        "retrieval_config_version": "v1.0",
    }
    res = client.post("/api/v1/ai/reviews", json=payload, headers=lawyer_headers)
    assert res.status_code == 201
    rev_data = res.json()
    review_id = rev_data["review_id"]
    assert rev_data["status"] == "PENDING"
    assert rev_data["category"] == "OUTDATED_LAW"

    # 2. Compliance operator takes action on review
    res_act = client.post(
        f"/api/v1/ai/reviews/{review_id}/action",
        json={"action_taken": "Added mandatory system prompt guidance on BNS statutory enactment."},
        headers=admin_headers,
    )
    assert res_act.status_code == 200
    assert res_act.json()["status"] == "ACTIONED"
    assert "BNS statutory enactment" in res_act.json()["action_taken"]


# --------------------------------------------------------------------------
# 7. DATA QUALITY & RECONCILIATION ENGINE
# --------------------------------------------------------------------------


def test_data_quality_reconciliation_audit_and_repair(db: Session):
    recon_service = ReconciliationService(db)

    # Seed an anomaly: stale running background job
    stale_job = BackgroundJob(
        id=generate_uuid7(),
        job_type=JobType.DOCUMENT_PROCESSING,
        status=JobStatus.RUNNING,
        started_at=datetime.now(UTC) - timedelta(minutes=45),
        payload={},
        attempt_count=0,
    )
    db.add(stale_job)
    db.commit()

    # 1. Audit Only (repair=False)
    audit_run = recon_service.audit_and_reconcile(repair=False)
    assert audit_run.anomalies_detected >= 1
    assert audit_run.repairs_executed == 0
    assert audit_run.status == DataQualityRunStatus.COMPLETED_WITH_ANOMALIES
    assert "stale_running_jobs" in audit_run.anomaly_breakdown

    # 2. Audit & Repair (repair=True)
    repair_run = recon_service.audit_and_reconcile(repair=True)
    assert repair_run.repairs_executed >= 1
    assert repair_run.status == DataQualityRunStatus.COMPLETED_WITH_REPAIRS

    # Verify stale job was reset to PENDING
    db.refresh(stale_job)
    assert stale_job.status == JobStatus.PENDING
    assert stale_job.attempt_count == 1


# --------------------------------------------------------------------------
# 8. SRE OBSERVABILITY, STATISTICAL CONFIDENCE & COST MODEL
# --------------------------------------------------------------------------


def test_sre_slo_sample_confidence_and_cost_endpoints(client: TestClient, db: Session):
    admin_user = create_test_user(db, f"sre_obs_admin_{uuid.uuid4().hex[:6]}@example.com", role=UserRole.ADMIN)
    headers = get_auth_headers(admin_user)

    # 1. SLO Report with sample confidence
    res_slo = client.get("/api/v1/pilot/slos", headers=headers)
    assert res_slo.status_code == 200
    slo_data = res_slo.json()
    assert "confidence_limitation" in slo_data
    assert slo_data["confidence_limitation"] in ("STATISTICALLY_CONFIDENT", "INSUFFICIENT_SAMPLE_SIZE")

    # 2. Cost Observability Model endpoint
    res_cost = client.get("/api/v1/pilot/costs", headers=headers)
    assert res_cost.status_code == 200
    cost_data = res_cost.json()
    assert cost_data["currency"] == "USD"
    assert "workflow_breakdown" in cost_data
    assert "unit_cost_assumptions" in cost_data
