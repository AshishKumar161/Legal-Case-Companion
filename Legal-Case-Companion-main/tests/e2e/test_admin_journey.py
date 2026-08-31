from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.models.user import (
    AccountStatus,
    User,
    UserRole,
)


def test_full_admin_e2e_journey(client: TestClient, db: Session):
    """E2E Test: Validates admin console operations, lawyer enrollment verification state machine, legal source sync, and operational metrics."""
    # 1. Seed Admin User in DB
    admin_id = generate_uuid7()
    admin_email = "admin_e2e_console@example.com"
    admin_pwd = "AdminSuperPass123!"
    admin_user = User(
        id=admin_id,
        email=admin_email,
        password_hash=hash_password(admin_pwd),
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(admin_user)
    db.commit()

    # 2. Login Admin
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": admin_pwd},
    )
    assert login_res.status_code == 200
    admin_token = login_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Register a Lawyer
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "pending_advocate_e2e@example.com",
            "password": "Pass123!Advocate",
            "role": "LAWYER",
            "full_name": "Adv. Suresh Menon",
        },
    )
    lawyer_login = client.post(
        "/api/v1/auth/login",
        json={"email": "pending_advocate_e2e@example.com", "password": "Pass123!Advocate"},
    )
    lawyer_token = lawyer_login.json()["access_token"]
    lawyer_headers = {"Authorization": f"Bearer {lawyer_token}"}

    # Lawyer submits verification
    verif_submit = client.post(
        "/api/v1/profiles/lawyer/verification",
        headers=lawyer_headers,
        json={"enrollment_number": "D/1234/2020", "state_bar_council": "Bar Council of Delhi"},
    )
    assert verif_submit.status_code == 200
    verif_id = verif_submit.json()["id"]

    # 4. Admin views pending lawyer verifications
    verif_list = client.get("/api/v1/admin/verifications", headers=admin_headers)
    assert verif_list.status_code == 200
    items = verif_list.json().get("items", [])
    assert any(v["id"] == verif_id for v in items)

    # 5. Admin approves lawyer verification
    approve_res = client.post(
        f"/api/v1/admin/verifications/{verif_id}/approve",
        headers=admin_headers,
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    # 6. Admin synchronizes curated Indian legal fixtures
    sync_res = client.post(
        "/api/v1/admin/legal-sources/sync-fixtures",
        headers=admin_headers,
    )
    assert sync_res.status_code in [200, 201]

    # 7. Admin checks background jobs queue
    jobs_res = client.get("/api/v1/admin/jobs", headers=admin_headers)
    assert jobs_res.status_code == 200
    assert "items" in jobs_res.json() or isinstance(jobs_res.json(), list)

    # 8. Admin checks operational telemetry & metrics
    metrics_res = client.get("/api/v1/admin/metrics", headers=admin_headers)
    assert metrics_res.status_code == 200
    metrics_data = metrics_res.json()
    assert "uptime_seconds" in metrics_data or "total_requests" in metrics_data

    # 9. Non-Admin (Client) access to Admin endpoint is strictly rejected (403)
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "regular_client_e2e@example.com",
            "password": "Pass123!Client",
            "role": "CLIENT",
            "full_name": "Regular Client",
        },
    )
    client_login = client.post(
        "/api/v1/auth/login",
        json={"email": "regular_client_e2e@example.com", "password": "Pass123!Client"},
    )
    client_token = client_login.json()["access_token"]
    unauth_headers = {"Authorization": f"Bearer {client_token}"}

    forbidden_res = client.get("/api/v1/admin/metrics", headers=unauth_headers)
    assert forbidden_res.status_code == 403
