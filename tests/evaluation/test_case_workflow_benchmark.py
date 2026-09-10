from datetime import date
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.case_intelligence import (
    CaseChronologyEvent,
    CaseEvidenceGap,
    DatePrecision,
    EvidenceGapStatus,
    EvidenceGapType,
    RiskSeverity,
)


def _setup_client_user(client: TestClient, email: str):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": "LAWYER", "full_name": "Bench Lawyer"},
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_case_workflow_operations_benchmark(client: TestClient, db: Session):
    """Benchmark evaluating task suggestion precision, unconfirmed state safety,

    deadline scheduling accuracy, and duplicate suppression.
    """
    _user_id, headers = _setup_client_user(client, "bench_wf@test.com")
    res_c = client.post("/api/v1/cases", json={"title": "Benchmark Workflow Case", "description": "Benchmark"}, headers=headers)
    case_id = res_c.json()["id"]

    # 1. Seed 2 Evidence Gaps & 2 Chronology Events
    gap1 = CaseEvidenceGap(
        id=generate_uuid7(), case_id=UUID(case_id),
        description="Missing signature on settlement addendum.",
        gap_type=EvidenceGapType.MISSING_SIGNATURE, severity=RiskSeverity.HIGH,
        status=EvidenceGapStatus.NOT_FOUND_IN_AVAILABLE_MATERIALS,
    )
    gap2 = CaseEvidenceGap(
        id=generate_uuid7(), case_id=UUID(case_id),
        description="Proof of statutory deposit under Section 148 NI Act not found.",
        gap_type=EvidenceGapType.MISSING_PAYMENT_PROOF, severity=RiskSeverity.CRITICAL,
        status=EvidenceGapStatus.NOT_FOUND_IN_AVAILABLE_MATERIALS,
    )
    ev_hearing = CaseChronologyEvent(
        id=generate_uuid7(), case_id=UUID(case_id),
        event_date=date(2026, 10, 15), date_text="15 Oct 2026",
        date_precision=DatePrecision.EXACT_DATE, event_type="HEARING_SCHEDULED",
        description="Matter listed for final arguments before the District & Sessions Court.",
    )
    ev_notice = CaseChronologyEvent(
        id=generate_uuid7(), case_id=UUID(case_id),
        event_date=date(2026, 9, 1), date_text="01 Sept 2026",
        date_precision=DatePrecision.EXACT_DATE, event_type="DEMAND_NOTICE_SERVED",
        description="Statutory demand notice served upon the respondent.",
    )
    db.add_all([gap1, gap2, ev_hearing, ev_notice])
    db.commit()

    # 2. Trigger Workflow Suggestions
    res_sugg = client.post(f"/api/v1/cases/{case_id}/workflow/suggestions/generate", headers=headers)
    assert res_sugg.status_code == 200
    sugg_data = res_sugg.json()
    assert sugg_data["suggested_tasks_count"] == 2
    assert sugg_data["suggested_hearings_count"] == 1
    assert sugg_data["suggested_deadlines_count"] == 1

    # 3. Benchmark Metric: All suggestions must remain UNCONFIRMED initially
    res_wf = client.get(f"/api/v1/cases/{case_id}/workflow", headers=headers)
    assert res_wf.status_code == 200
    wf = res_wf.json()
    assert wf["operations_summary"]["unconfirmed_suggestions_count"] == 4
    assert all(not t["is_confirmed"] for t in wf["tasks"])
    assert all(not d["is_confirmed"] for d in wf["deadlines"])
    assert all(not h["is_confirmed"] for h in wf["hearings"])

    # 4. Benchmark Metric: Duplicate suppression on re-generation
    res_sugg2 = client.post(f"/api/v1/cases/{case_id}/workflow/suggestions/generate", headers=headers)
    assert res_sugg2.json()["suggested_tasks_count"] == 0
    assert res_sugg2.json()["suggested_hearings_count"] == 0
    assert res_sugg2.json()["suggested_deadlines_count"] == 0
