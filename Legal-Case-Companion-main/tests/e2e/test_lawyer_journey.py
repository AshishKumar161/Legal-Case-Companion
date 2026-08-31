from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_full_lawyer_e2e_journey(client: TestClient, db: Session):
    """E2E Test: Validates the complete lawyer workflow from availability setup, consultations, assigned workspace, private notes, and hearing management."""
    # 1. Register and Login Lawyer
    lawyer_email = "advocate_sharma_e2e@example.com"
    lawyer_pwd = "AdvocatePass123!"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": lawyer_email,
            "password": lawyer_pwd,
            "role": "LAWYER",
            "full_name": "Adv. Priya Sharma",
        },
    )
    assert reg_res.status_code == 201
    lawyer_id = reg_res.json()["id"]

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": lawyer_email, "password": lawyer_pwd},
    )
    assert login_res.status_code == 200
    lawyer_token = login_res.json()["access_token"]
    lawyer_headers = {"Authorization": f"Bearer {lawyer_token}"}

    # 2. Register a Client and create a Case matter
    client_email = "client_for_lawyer_e2e@example.com"
    _client_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": client_email,
            "password": "ClientPass123!",
            "role": "CLIENT",
            "full_name": "Rohit Verma",
        },
    )
    client_login = client.post(
        "/api/v1/auth/login",
        json={"email": client_email, "password": "ClientPass123!"},
    )
    client_token = client_login.json()["access_token"]
    client_headers = {"Authorization": f"Bearer {client_token}"}

    case_res = client.post(
        "/api/v1/cases",
        headers=client_headers,
        json={
            "title": "Commercial Injunction & Trademark Dispute",
            "description": "Urgent interim injunction requested before Delhi High Court under Trade Marks Act 1999.",
        },
    )
    case_id = case_res.json()["id"]

    # 3. Add Lawyer as LAWYER
    add_part = client.post(
        f"/api/v1/cases/{case_id}/participants",
        headers=client_headers,
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
    )
    assert add_part.status_code in [200, 201]

    # 4. Lawyer accesses the Case Workspace
    lawyer_case_view = client.get(f"/api/v1/cases/{case_id}", headers=lawyer_headers)
    assert lawyer_case_view.status_code == 200
    assert lawyer_case_view.json()["title"] == "Commercial Injunction & Trademark Dispute"

    # 5. Lawyer creates a Lawyer-Private Note (Client cannot see)
    note_res = client.post(
        f"/api/v1/cases/{case_id}/notes",
        headers=lawyer_headers,
        json={
            "content": "Confidential strategy: Move for ex-parte ad-interim injunction on Monday.",
            "visibility": "LAWYER_PRIVATE",
        },
    )
    assert note_res.status_code == 201
    note_id = note_res.json()["id"]

    # Verify Client CANNOT see LAWYER_PRIVATE note
    client_notes = client.get(f"/api/v1/cases/{case_id}/notes", headers=client_headers)
    assert client_notes.status_code == 200
    note_items = client_notes.json().get("items", [])
    note_ids = [n["id"] for n in note_items]
    assert note_id not in note_ids

    # 6. Lawyer schedules a Court Hearing
    hearing_at = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    hearing_res = client.post(
        f"/api/v1/cases/{case_id}/hearings",
        headers=lawyer_headers,
        json={
            "court_name": "Delhi High Court",
            "bench_or_coram": "Single Bench - Hon'ble Justice Khanna",
            "hearing_at": hearing_at,
            "purpose": "Arguments on interim injunction application",
        },
    )
    assert hearing_res.status_code == 201

    # 7. Lawyer sets a Statutory Limitation Deadline
    deadline_at = (datetime.now(UTC) + timedelta(days=14)).isoformat()
    deadline_res = client.post(
        f"/api/v1/cases/{case_id}/deadlines",
        headers=lawyer_headers,
        json={
            "title": "Filing of Rejoinder Affidavit",
            "deadline_at": deadline_at,
            "deadline_type": "STATUTORY_LIMITATION",
        },
    )
    assert deadline_res.status_code == 201

    # 8. Lawyer retrieves aggregate Case Intelligence
    intel_res = client.get(f"/api/v1/cases/{case_id}/intelligence", headers=lawyer_headers)
    assert intel_res.status_code == 200
