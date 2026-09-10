from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole


def test_analytics_funnel_requires_admin(client: TestClient, db: Session):
    user = User(
        email="normal_analytics@test.com",
        phone="1234567895",
        password_hash=hash_password("pass"),
        role=UserRole.CLIENT,
    )
    db.add(user)
    db.commit()

    token = create_access_token(str(user.id), role=user.role)

    response = client.get(
        "/api/v1/analytics/funnel", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_analytics_funnel_admin_access(client: TestClient, db: Session):
    admin = User(
        email="admin_analytics@test.com",
        phone="1234567896",
        password_hash=hash_password("pass"),
        role=UserRole.ADMIN,
    )
    db.add(admin)
    db.commit()

    token = create_access_token(str(admin.id), role=admin.role)

    response = client.get(
        "/api/v1/analytics/funnel", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200

    data = response.json()
    assert "total_users" in data
    assert "funnel" in data
    assert len(data["funnel"]) == 3
