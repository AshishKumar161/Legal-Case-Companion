import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _setup_user(client: TestClient, role: str, email: str, full_name: str):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePassword123!",
            "role": role,
            "full_name": full_name,
        },
    )
    user_id = res_reg.json().get("id")
    res = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"}
    )
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_lawyer_discovery_filtering(client: TestClient, db: Session):
    # Setup some lawyers
    lA_id, tokenA_h = _setup_user(client, "LAWYER", "lawyerA@test.com", "Alice")
    lB_id, tokenB_h = _setup_user(client, "LAWYER", "lawyerB@test.com", "Bob")

    # Update lawyer A profile
    client.patch(
        "/api/v1/profiles/lawyer",
        headers=tokenA_h,
        json={
            "location": "Mumbai",
            "practice_areas": ["Criminal", "Family"],
            "experience_years": 10,
            "court_jurisdictions": ["Bombay High Court"],
            "consultation_fee": 3000.0,
        },
    )

    # Update lawyer B profile
    client.patch(
        "/api/v1/profiles/lawyer",
        headers=tokenB_h,
        json={
            "location": "Delhi",
            "practice_areas": ["Corporate"],
            "experience_years": 5,
            "court_jurisdictions": ["Delhi High Court", "Supreme Court of India"],
            "consultation_fee": 1500.0,
        },
    )

    # Approve verifications for both lawyers
    from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus

    for l_uid in (lA_id, lB_id):
        lp = db.query(LawyerProfile).filter(LawyerProfile.user_id == uuid.UUID(l_uid)).first()
        assert lp is not None
        v = LawyerVerification(
            lawyer_profile_id=lp.id,
            enrollment_number=f"ENR/{l_uid[:6]}",
            state_bar_council="Test Bar",
            status=VerificationStatus.APPROVED,
        )
        db.add(v)
    db.commit()

    # Client search
    _client_id, client_headers = _setup_user(
        client, "CLIENT", "searchclient@test.com", "Client"
    )

    # 1. Search by location
    res_mum = client.get("/api/v1/lawyers?location=Mumbai", headers=client_headers)
    assert res_mum.status_code == 200
    assert len(res_mum.json()["items"]) == 1
    assert res_mum.json()["items"][0]["full_name"] == "Alice"

    # 2. Search by practice area
    res_corp = client.get(
        "/api/v1/lawyers?practice_area=Corporate", headers=client_headers
    )
    assert res_corp.status_code == 200
    assert len(res_corp.json()["items"]) == 1
    assert res_corp.json()["items"][0]["full_name"] == "Bob"

    # 3. Search by court jurisdiction
    res_court = client.get(
        "/api/v1/lawyers?court_jurisdiction=Supreme+Court", headers=client_headers
    )
    assert res_court.status_code == 200
    assert len(res_court.json()["items"]) == 1
    assert res_court.json()["items"][0]["full_name"] == "Bob"

    # 4. Search by experience
    res_exp = client.get(
        "/api/v1/lawyers?min_experience=8", headers=client_headers
    )
    assert res_exp.status_code == 200
    assert len(res_exp.json()["items"]) == 1
    assert res_exp.json()["items"][0]["full_name"] == "Alice"

    # 5. Search empty
    res_empty = client.get(
        "/api/v1/lawyers?location=UnknownCity", headers=client_headers
    )
    assert res_empty.status_code == 200
    assert len(res_empty.json()["items"]) == 0


def test_lawyer_discovery_unverified_and_rejected_hidden(client: TestClient, db: Session):
    _client_id, client_headers = _setup_user(
        client, "CLIENT", "disc_client_priv@test.com", "Client"
    )
    verif_id, _h_ver = _setup_user(
        client, "LAWYER", "disc_verif_l@test.com", "Verified Lawyer"
    )
    unverif_id, _h_unv = _setup_user(
        client, "LAWYER", "disc_unverif_l@test.com", "Unverified Lawyer"
    )
    rej_id, _h_rej = _setup_user(
        client, "LAWYER", "disc_rej_l@test.com", "Rejected Lawyer"
    )

    from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus

    lp_ver = db.query(LawyerProfile).filter(LawyerProfile.user_id == uuid.UUID(verif_id)).first()
    assert lp_ver is not None
    db.add(
        LawyerVerification(
            lawyer_profile_id=lp_ver.id,
            enrollment_number="VER/111",
            state_bar_council="Delhi",
            status=VerificationStatus.APPROVED,
        )
    )

    lp_rej = db.query(LawyerProfile).filter(LawyerProfile.user_id == uuid.UUID(rej_id)).first()
    assert lp_rej is not None
    db.add(
        LawyerVerification(
            lawyer_profile_id=lp_rej.id,
            enrollment_number="REJ/222",
            state_bar_council="Delhi",
            status=VerificationStatus.REJECTED,
        )
    )
    db.commit()

    # Public search must only return the verified lawyer
    res = client.get("/api/v1/lawyers", headers=client_headers)
    assert res.status_code == 200
    uids = [item["user_id"] for item in res.json()["items"]]
    assert verif_id in uids
    assert unverif_id not in uids
    assert rej_id not in uids


def test_lawyer_public_detail(client: TestClient):
    lawyer_id, _lawyer_headers = _setup_user(
        client, "LAWYER", "detail_lawyer@test.com", "Detail Lawyer"
    )
    _client_id, client_headers = _setup_user(
        client, "CLIENT", "detail_client@test.com", "Detail Client"
    )

    # Get detail
    res = client.get(f"/api/v1/lawyers/{lawyer_id}", headers=client_headers)
    assert res.status_code == 200
    assert res.json()["full_name"] == "Detail Lawyer"
    assert "password_hash" not in res.json()
    assert "password" not in res.json()
    assert "email" not in res.json()


def test_lawyer_detail_suspended_hidden(client: TestClient):
    lawyer_id, _lawyer_headers = _setup_user(
        client, "LAWYER", "susp_lawyer@test.com", "Susp Lawyer"
    )
    _client_id, client_headers = _setup_user(
        client, "CLIENT", "susp_client@test.com", "Susp Client"
    )

    import typing

    from fastapi import FastAPI

    from app.api.deps import get_db
    from app.models.user import AccountStatus, User

    app = typing.cast(FastAPI, client.app)
    db_gen = app.dependency_overrides.get(get_db, get_db)()
    db = next(db_gen)

    user = db.query(User).filter(User.id == uuid.UUID(lawyer_id)).first()
    assert user is not None
    user.account_status = AccountStatus.SUSPENDED
    db.commit()

    res = client.get(f"/api/v1/lawyers/{lawyer_id}", headers=client_headers)
    assert res.status_code == 404


def test_lawyer_selection_bola(client: TestClient):
    _userA_id, headersA = _setup_user(client, "CLIENT", "userA@test.com", "User A")
    _userB_id, headersB = _setup_user(client, "CLIENT", "userB@test.com", "User B")
    lawyer_id, _lawyer_headers = _setup_user(
        client, "LAWYER", "selectlawyer@test.com", "Select Lawyer"
    )

    # User A creates Case A
    resA = client.post(
        "/api/v1/cases",
        json={"title": "Case A", "description": "Desc A"},
        headers=headersA,
    )
    caseA_id = resA.json()["id"]

    # User B creates Case B
    resB = client.post(
        "/api/v1/cases",
        json={"title": "Case B", "description": "Desc B"},
        headers=headersB,
    )
    caseB_id = resB.json()["id"]

    # User A selects lawyer for Case A -> Success
    addA = client.post(
        f"/api/v1/cases/{caseA_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=headersA,
    )
    assert addA.status_code == 200

    # User A attempts to select lawyer for Case B -> Fail (404 for BOLA)
    addB = client.post(
        f"/api/v1/cases/{caseB_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=headersA,
    )
    assert addB.status_code == 404
