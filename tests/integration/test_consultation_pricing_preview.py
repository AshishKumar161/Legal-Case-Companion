import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus
from app.core.identifiers import generate_uuid7


def _setup_user(
    client: TestClient,
    email: str,
    password: str,
    role: str = "LAWYER",
    full_name: str = "Advocate Test",
):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": role,
            "full_name": full_name,
        },
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_consultation_pricing_preview_calculation(client: TestClient, db: Session):
    # Setup lawyer with specific consultation fee
    email = f"lawyer.pricing.{uuid.uuid4().hex[:8]}@example.com"
    lawyer_id, _ = _setup_user(client, email, "Pass123!", "LAWYER", "Adv. R. K. Sharma")

    l_prof = (
        db.query(LawyerProfile).filter(LawyerProfile.user_id == uuid.UUID(lawyer_id)).first()
    )
    assert l_prof is not None
    l_prof.consultation_fee = 1000.0

    ver = LawyerVerification(
        id=generate_uuid7(),
        lawyer_profile_id=l_prof.id,
        enrollment_number="D/9876/2018",
        state_bar_council="Bar Council of Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()

    # 1. Test 30-minute consultation pricing preview
    res = client.get(f"/api/v1/consultations/pricing-preview?lawyer_id={l_prof.id}&duration_minutes=30")
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["fee_amount"] == 1000.0
    assert data["gst_rate"] == 0.18
    assert data["gst_amount"] == 180.0
    assert data["platform_fee"] == 0.0
    assert data["total_amount"] == 1180.0
    assert data["currency"] == "INR"
    assert data["breakdown"]["cgst"] == 90.0
    assert data["breakdown"]["sgst"] == 90.0
    assert "18% GST" in data["breakdown"]["description"]

    # 2. Test 60-minute duration scaling
    res60 = client.get(f"/api/v1/consultations/pricing-preview?lawyer_id={lawyer_id}&duration_minutes=60")
    assert res60.status_code == 200
    data60 = res60.json()
    assert data60["fee_amount"] == 2000.0
    assert data60["gst_amount"] == 360.0
    assert data60["total_amount"] == 2360.0

    # 3. Test non-existent lawyer
    fake_id = str(uuid.uuid4())
    res_fake = client.get(f"/api/v1/consultations/pricing-preview?lawyer_id={fake_id}")
    assert res_fake.status_code == 404
