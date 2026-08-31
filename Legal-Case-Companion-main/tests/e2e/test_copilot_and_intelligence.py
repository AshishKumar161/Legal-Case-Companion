from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.case_intelligence import (
    CaseFact,
    FactSourceType,
    FactVerificationStatus,
)


def test_copilot_grounding_and_intelligence_e2e(client: TestClient, db: Session):
    """E2E Test: Validates AI Copilot claim verification, grounding status, and case intelligence fact tracking."""
    # 1. Register & Login User
    email = "copilot_intel_e2e@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "CopilotPass123!", "role": "CLIENT", "full_name": "Copilot User"},
    )
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "CopilotPass123!"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Case
    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": "Arbitration Matter", "description": "Arbitration agreement enforcement under 1996 Act."},
    )
    case_id = case_res.json()["id"]

    # 3. Create Conversation
    conv_res = client.post(
        f"/api/v1/cases/{case_id}/ai/conversations",
        headers=headers,
        json={"title": "Arbitration Clause Analysis"},
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # 4. Send Message with External Legal Authority Flag
    msg_res = client.post(
        f"/api/v1/cases/{case_id}/ai/conversations/{conv_id}/messages",
        headers=headers,
        json={
            "query": "Is Section 9 interim relief maintainable before constitution of arbitral tribunal?",
            "include_legal_authority": True,
        },
    )
    assert msg_res.status_code == 200
    msg_data = msg_res.json()
    assert "content" in msg_data
    assert msg_data.get("grounding_status") is not None

    # 5. Case Intelligence: Seed a Fact and Update Verification State
    fact = CaseFact(
        case_id=case_id,
        fact_text="Notice of arbitration was issued on 10 October 2023.",
        source_type=FactSourceType.CASE_EVIDENCE,
        verification_status=FactVerificationStatus.UNVERIFIED,
        confidence_score=0.95,
    )
    db.add(fact)
    db.commit()
    db.refresh(fact)

    # Human lawyer confirms fact
    fact_patch = client.patch(
        f"/api/v1/cases/{case_id}/intelligence/facts/{fact.id}",
        headers=headers,
        json={"verification_status": "HUMAN_CONFIRMED"},
    )
    assert fact_patch.status_code == 200
    assert fact_patch.json()["verification_status"] == "HUMAN_CONFIRMED"
