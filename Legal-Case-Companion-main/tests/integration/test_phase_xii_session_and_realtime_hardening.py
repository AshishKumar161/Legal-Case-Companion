import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.consultation import Consultation, ConsultationStatus
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.services.lawyer_call_channel import incoming_call_channel_manager
from app.services.presence_service import presence_service


def _create_user_with_password(
    db: Session,
    email_prefix: str,
    role: UserRole,
    password: str = "SecurePass123!",
) -> User:
    uid = uuid.uuid4().hex[:6]
    user = User(
        email=f"{email_prefix}_{uid}@lcc.test",
        password_hash=hash_password(password),
        role=role,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    if role == UserRole.CLIENT:
        profile = ClientProfile(
            user_id=user.id,
            full_name=f"Client {email_prefix.capitalize()}",
        )
        db.add(profile)
    elif role == UserRole.LAWYER:
        profile = LawyerProfile(
            user_id=user.id,
            full_name=f"Advocate {email_prefix.capitalize()}",
            practice_areas=["Cyber Law", "Constitutional Law"],
            court_jurisdictions=["Supreme Court of India"],
            languages=["English", "Hindi"],
            experience_years=8,
            consultation_fee=1500.0,
        )
        db.add(profile)
        db.flush()
        verification = LawyerVerification(
            lawyer_profile_id=profile.id,
            enrollment_number=f"D/{uuid.uuid4().hex[:4].upper()}/2021",
            state_bar_council="Bar Council of Delhi",
            status=VerificationStatus.APPROVED,
        )
        db.add(verification)

    db.commit()
    db.refresh(user)
    return user


def _do_refresh(client: TestClient, refresh_token: str):
    csrf_val = "test_csrf_token_123"
    return client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
        cookies={"csrf_token": csrf_val},
        headers={"X-CSRF-Token": csrf_val},
    )


def test_client_lawyer_admin_simultaneous_session_isolation(client: TestClient, db: Session):
    password = "CommonPassword123!"
    client_user = _create_user_with_password(db, "tab_client", UserRole.CLIENT, password)
    lawyer_user = _create_user_with_password(db, "tab_lawyer", UserRole.LAWYER, password)
    admin_user = _create_user_with_password(db, "tab_admin", UserRole.ADMIN, password)

    # Tab A (CLIENT) logs in
    res_a = client.post("/api/v1/auth/login", json={"email": client_user.email, "password": password})
    assert res_a.status_code == 200
    tab_a_data = res_a.json()
    assert "access_token" in tab_a_data
    assert "refresh_token" in tab_a_data
    tab_a_token = tab_a_data["access_token"]

    # Tab B (LAWYER) logs in
    res_b = client.post("/api/v1/auth/login", json={"email": lawyer_user.email, "password": password})
    assert res_b.status_code == 200
    tab_b_data = res_b.json()
    tab_b_token = tab_b_data["access_token"]

    # Tab C (ADMIN) logs in
    res_c = client.post("/api/v1/auth/login", json={"email": admin_user.email, "password": password})
    assert res_c.status_code == 200
    tab_c_data = res_c.json()
    tab_c_token = tab_c_data["access_token"]

    # Verify Tab A identity
    me_a = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tab_a_token}"})
    assert me_a.status_code == 200
    assert me_a.json()["role"] == "CLIENT"
    assert me_a.json()["id"] == str(client_user.id)

    # Verify Tab B identity
    me_b = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tab_b_token}"})
    assert me_b.status_code == 200
    assert me_b.json()["role"] == "LAWYER"
    assert me_b.json()["id"] == str(lawyer_user.id)

    # Verify Tab C identity
    me_c = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tab_c_token}"})
    assert me_c.status_code == 200
    assert me_c.json()["role"] == "ADMIN"
    assert me_c.json()["id"] == str(admin_user.id)

    # Verify Tab A is still CLIENT (zero cross-contamination)
    me_a_repeat = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tab_a_token}"})
    assert me_a_repeat.status_code == 200
    assert me_a_repeat.json()["role"] == "CLIENT"


def test_logout_isolation(client: TestClient, db: Session):
    password = "SecurePassword123!"
    client_user = _create_user_with_password(db, "iso_client", UserRole.CLIENT, password)
    lawyer_user = _create_user_with_password(db, "iso_lawyer", UserRole.LAWYER, password)

    res_a = client.post("/api/v1/auth/login", json={"email": client_user.email, "password": password})
    tab_a_access = res_a.json()["access_token"]
    tab_a_refresh = res_a.json()["refresh_token"]

    res_b = client.post("/api/v1/auth/login", json={"email": lawyer_user.email, "password": password})
    tab_b_access = res_b.json()["access_token"]
    tab_b_refresh = res_b.json()["refresh_token"]

    logout_res = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tab_a_refresh},
        headers={"Authorization": f"Bearer {tab_a_access}"},
    )
    assert logout_res.status_code == 200

    refresh_a = _do_refresh(client, tab_a_refresh)
    assert refresh_a.status_code == 401

    me_b = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tab_b_access}"})
    assert me_b.status_code == 200
    assert me_b.json()["role"] == "LAWYER"

    refresh_b = _do_refresh(client, tab_b_refresh)
    assert refresh_b.status_code == 200
    assert "access_token" in refresh_b.json()


def test_refresh_isolation_and_rotation(client: TestClient, db: Session):
    password = "SecurePassword123!"
    client_user = _create_user_with_password(db, "ref_client", UserRole.CLIENT, password)
    lawyer_user = _create_user_with_password(db, "ref_lawyer", UserRole.LAWYER, password)

    res_a = client.post("/api/v1/auth/login", json={"email": client_user.email, "password": password})
    tab_a_refresh = res_a.json()["refresh_token"]

    res_b = client.post("/api/v1/auth/login", json={"email": lawyer_user.email, "password": password})
    tab_b_refresh = res_b.json()["refresh_token"]
    tab_b_access = res_b.json()["access_token"]

    rotate_a = _do_refresh(client, tab_a_refresh)
    assert rotate_a.status_code == 200
    new_tab_a_access = rotate_a.json()["access_token"]
    new_tab_a_refresh = rotate_a.json()["refresh_token"]
    assert new_tab_a_refresh != tab_a_refresh

    me_a = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_tab_a_access}"})
    assert me_a.status_code == 200
    assert me_a.json()["role"] == "CLIENT"

    me_b = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tab_b_access}"})
    assert me_b.status_code == 200
    assert me_b.json()["role"] == "LAWYER"

    rotate_b = _do_refresh(client, tab_b_refresh)
    assert rotate_b.status_code == 200
    assert rotate_b.json()["access_token"] != tab_b_access


def test_refresh_failure_isolation(client: TestClient, db: Session):
    password = "SecurePassword123!"
    lawyer_user = _create_user_with_password(db, "fail_lawyer", UserRole.LAWYER, password)

    res_b = client.post("/api/v1/auth/login", json={"email": lawyer_user.email, "password": password})
    tab_b_access = res_b.json()["access_token"]
    tab_b_refresh = res_b.json()["refresh_token"]

    invalid_refresh = _do_refresh(client, "invalid_bogus_token")
    assert invalid_refresh.status_code == 401

    me_b = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tab_b_access}"})
    assert me_b.status_code == 200
    assert me_b.json()["role"] == "LAWYER"

    rotate_b = _do_refresh(client, tab_b_refresh)
    assert rotate_b.status_code == 200


def test_websocket_ticket_lifecycle_and_rbac(client: TestClient, db: Session):
    lawyer_user = _create_user_with_password(db, "ws_lawyer", UserRole.LAWYER)
    client_user = _create_user_with_password(db, "ws_client", UserRole.CLIENT)

    lawyer_token = create_access_token(str(lawyer_user.id), lawyer_user.role.value)
    client_token = create_access_token(str(client_user.id), client_user.role.value)

    client_ticket_res = client.post(
        "/api/v1/consultations/ws-ticket",
        headers={"Authorization": f"Bearer {client_token}"},
    )
    assert client_ticket_res.status_code == 403

    ticket_res = client.post(
        "/api/v1/consultations/ws-ticket",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )
    assert ticket_res.status_code == 200
    ticket_data = ticket_res.json()
    assert "ticket" in ticket_data
    assert ticket_data["expires_in"] == 60
    ticket = ticket_data["ticket"]

    with client.websocket_connect(f"/api/v1/consultations/ws/incoming-calls?ticket={ticket}") as ws:
        ws.send_text("ping")
        resp = ws.receive_text()
        assert resp == "pong"

    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/consultations/ws/incoming-calls?ticket={ticket}") as ws_reused:
            ws_reused.receive_text()

    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/consultations/ws/incoming-calls?ticket=completely_fake_ticket") as ws_fake:
            ws_fake.receive_text()


def test_cross_lawyer_event_isolation(client: TestClient, db: Session):
    lawyer_a = _create_user_with_password(db, "lawyer_a", UserRole.LAWYER)
    lawyer_b = _create_user_with_password(db, "lawyer_b", UserRole.LAWYER)

    token_a = create_access_token(str(lawyer_a.id), lawyer_a.role.value)
    token_b = create_access_token(str(lawyer_b.id), lawyer_b.role.value)

    ticket_res_a = client.post("/api/v1/consultations/ws-ticket", headers={"Authorization": f"Bearer {token_a}"})
    ticket_a = ticket_res_a.json()["ticket"]

    ticket_res_b = client.post("/api/v1/consultations/ws-ticket", headers={"Authorization": f"Bearer {token_b}"})
    ticket_b = ticket_res_b.json()["ticket"]

    with client.websocket_connect(f"/api/v1/consultations/ws/incoming-calls?ticket={ticket_a}") as ws_a, \
         client.websocket_connect(f"/api/v1/consultations/ws/incoming-calls?ticket={ticket_b}") as ws_b:

        lawyer_a_profile = db.query(LawyerProfile).filter(LawyerProfile.user_id == lawyer_a.id).first()
        call_payload = {
            "id": str(uuid.uuid4()),
            "client_name": "Test Client",
            "fee": 1500.0,
            "created_at": datetime.now(UTC).isoformat(),
            "ring_timeout_seconds": 45,
        }

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            incoming_call_channel_manager.notify_incoming_call(lawyer_a_profile.id, call_payload)
        )

        msg_a = ws_a.receive_json()
        assert msg_a["type"] == "incoming_consultation"
        assert msg_a["consultation_id"] == call_payload["id"]
        assert "event_id" in msg_a
        assert "server_timestamp" in msg_a
        assert msg_a["lawyer_id"] == str(lawyer_a_profile.id)

        ws_b.send_text("ping")
        pong = ws_b.receive_text()
        assert pong == "pong"


def test_presence_isolation(client: TestClient, db: Session):
    lawyer_a = _create_user_with_password(db, "pres_a", UserRole.LAWYER)
    lawyer_b = _create_user_with_password(db, "pres_b", UserRole.LAWYER)

    token_a = create_access_token(str(lawyer_a.id), lawyer_a.role.value)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    res = client.post("/api/v1/lawyers/heartbeat", json={"available_for_instant": True}, headers=headers_a)
    assert res.status_code == 200

    profile_a = db.query(LawyerProfile).filter(LawyerProfile.user_id == lawyer_a.id).first()
    profile_b = db.query(LawyerProfile).filter(LawyerProfile.user_id == lawyer_b.id).first()

    pres_a = client.get(f"/api/v1/lawyers/{profile_a.id}/presence", headers=headers_a)
    assert pres_a.status_code == 200
    assert pres_a.json()["is_online"] is True

    pres_b = client.get(f"/api/v1/lawyers/{profile_b.id}/presence", headers=headers_a)
    assert pres_b.status_code == 200
    assert pres_b.json()["is_online"] is False


def test_consultation_concurrency_and_terminal_locking(client: TestClient, db: Session):
    client_user = _create_user_with_password(db, "conc_client", UserRole.CLIENT)
    lawyer_user = _create_user_with_password(db, "conc_lawyer", UserRole.LAWYER)

    c_profile = db.query(ClientProfile).filter(ClientProfile.user_id == client_user.id).first()
    l_profile = db.query(LawyerProfile).filter(LawyerProfile.user_id == lawyer_user.id).first()

    consultation = Consultation(
        client_id=c_profile.id,
        lawyer_id=l_profile.id,
        status=ConsultationStatus.REQUESTED,
        fee_amount=1000.0,
        currency="INR",
        scheduled_at=datetime.now(UTC) + timedelta(days=1),
        duration_minutes=30,
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)

    lawyer_token = create_access_token(str(lawyer_user.id), lawyer_user.role.value)
    headers = {"Authorization": f"Bearer {lawyer_token}"}

    res1 = client.post(f"/api/v1/consultations/{consultation.id}/accept", headers=headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "ACCEPTED"

    res2 = client.post(f"/api/v1/consultations/{consultation.id}/accept", headers=headers)
    assert res2.status_code == 200
    assert res2.json()["status"] == "ACCEPTED"

    reject_res = client.post(
        f"/api/v1/consultations/{consultation.id}/reject",
        json={"reason": "Should fail"},
        headers=headers,
    )
    assert reject_res.status_code in (400, 422)
