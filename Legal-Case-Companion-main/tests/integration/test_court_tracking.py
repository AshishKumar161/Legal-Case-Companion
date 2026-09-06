from datetime import UTC, datetime
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.models.court_case import CourtCase, UserFollowedCase
from app.models.user import AccountStatus, User, UserRole
from app.core.security import create_access_token
from app.core.identifiers import generate_uuid7

client = TestClient(app)


@pytest.fixture
def auth_client():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "test_court_client@example.com").first()
        if not user:
            user = User(
                id=generate_uuid7(),
                email="test_court_client@example.com",
                role=UserRole.CLIENT,
                account_status=AccountStatus.ACTIVE,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        token = create_access_token(subject=str(user.id), role=user.role.value)
        return TestClient(app, headers={"Authorization": f"Bearer {token}"}), user.id
    finally:
        db.close()


def test_search_court_cases_by_cnr():
    response = client.get("/api/v1/court-cases?search=DLHC010041202025&mode=cnr")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["cnr"] == "DLHC010041202025"
    assert data[0]["case_number"] == "CS(COMM) 412/2025"
    assert data[0]["source_provenance"] == "OFFICIAL COURT DATA"


def test_search_court_cases_by_case_number():
    response = client.get("/api/v1/court-cases?search=412/2025&mode=case_no")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert "412/2025" in data[0]["case_number"]


def test_search_court_cases_by_party():
    response = client.get("/api/v1/court-cases?search=Sharma Estates&mode=party")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert "Sharma Estates" in data[0]["petitioner"]


def test_search_court_cases_by_advocate():
    response = client.get("/api/v1/court-cases?search=Vikramaditya Sen&mode=advocate")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert "Vikramaditya Sen" in data[0]["petitioner_advocate"]


def test_get_court_case_detail_by_cnr():
    response = client.get("/api/v1/court-cases/DLHC010041202025")
    assert response.status_code == 200
    detail = response.json()
    assert detail["cnr"] == "DLHC010041202025"
    assert detail["technical_status"] == "Judgment Reserved"
    assert len(detail["history"]) >= 1
    assert detail["cause_list"] is not None
    assert detail["cause_list"]["court_room"] == "Court Room 4"
    assert len(detail["orders"]) >= 1


def test_get_nonexistent_court_case_returns_404():
    response = client.get("/api/v1/court-cases/NONEXISTENT999999")
    assert response.status_code == 404


def test_follow_and_sync_court_case(auth_client):
    authed, user_id = auth_client
    # Follow
    follow_res = authed.post("/api/v1/court-cases/DLHC010041202025/follow")
    assert follow_res.status_code == 200
    assert follow_res.json()["is_followed"] is True

    # Check detail shows is_followed == True
    detail_res = authed.get("/api/v1/court-cases/DLHC010041202025")
    assert detail_res.status_code == 200
    assert detail_res.json()["is_followed"] is True

    # Sync
    sync_res = authed.post("/api/v1/court-cases/DLHC010041202025/sync")
    assert sync_res.status_code == 200
    assert sync_res.json()["sync_status"] == "SYNCED"

    # Unfollow
    unfollow_res = authed.delete("/api/v1/court-cases/DLHC010041202025/follow")
    assert unfollow_res.status_code == 200
    assert unfollow_res.json()["is_followed"] is False
