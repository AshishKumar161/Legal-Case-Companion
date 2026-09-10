from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.security import create_access_token, hash_password
from app.models.consultation import Consultation, ConsultationStatus
from app.models.user import ClientProfile, LawyerProfile, User, UserRole


def test_complete_consultation(client: TestClient, db: Session):
    client_user = User(
        id=generate_uuid7(),
        email="client_comp@test.com",
        phone="1010101010",
        password_hash=hash_password("pass"),
        role=UserRole.CLIENT,
    )
    lawyer_user = User(
        id=generate_uuid7(),
        email="lawyer_comp@test.com",
        phone="1010101011",
        password_hash=hash_password("pass"),
        role=UserRole.LAWYER,
    )
    unauth_user = User(
        id=generate_uuid7(),
        email="unauth_comp@test.com",
        phone="1010101012",
        password_hash=hash_password("pass"),
        role=UserRole.CLIENT,
    )

    db.add(client_user)
    db.commit()
    db.add(lawyer_user)
    db.commit()
    db.add(unauth_user)
    db.commit()

    client_profile = ClientProfile(
        id=generate_uuid7(), user_id=client_user.id, full_name="Client Comp"
    )
    db.add(client_profile)

    lawyer_profile = LawyerProfile(
        id=generate_uuid7(),
        user_id=lawyer_user.id,
        full_name="Lawyer Comp",
        consultation_fee=100.0,
    )
    db.add(lawyer_profile)
    db.commit()

    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_profile.id,
        lawyer_id=lawyer_profile.id,
        scheduled_at=datetime.now(UTC),
        duration_minutes=30,
        fee_amount=100.0,
        currency="INR",
        status=ConsultationStatus.SCHEDULED,
    )
    db.add(consultation)
    db.commit()

    client_token = create_access_token(str(client_user.id), client_user.role)
    lawyer_token = create_access_token(str(lawyer_user.id), lawyer_user.role)
    unauth_token = create_access_token(str(unauth_user.id), unauth_user.role)

    # BOLA: Unauthorized user tries to complete -> 404
    res_unauth = client.post(
        f"/api/v1/consultations/{consultation.id}/complete",
        headers={"Authorization": f"Bearer {unauth_token}"},
    )
    assert res_unauth.status_code == 404

    # Client tries to complete -> 403 Forbidden (only lawyer or admin can complete)
    res_client = client.post(
        f"/api/v1/consultations/{consultation.id}/complete",
        headers={"Authorization": f"Bearer {client_token}"},
    )
    assert res_client.status_code == 403

    # Authorized lawyer completes -> 200 OK
    res_auth = client.post(
        f"/api/v1/consultations/{consultation.id}/complete",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )
    assert res_auth.status_code == 200
    assert res_auth.json()["status"] == "COMPLETED"
