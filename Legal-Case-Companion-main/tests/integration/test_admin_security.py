import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import AccountStatus, User, UserRole


def _create_admin_user(db: Session, email: str = "superadmin@test.com", password: str = "AdminPass123!") -> tuple[str, str]:
    admin = User(
        email=email,
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return str(admin.id), password


def _setup_user(
    client: TestClient,
    email: str,
    password: str = "SecurePass123!",
    role: str = "CLIENT",
    full_name: str = "Test User",
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


def test_admin_rbac_and_privilege_escalation_protection(client: TestClient, db: Session):
    _admin_id, admin_pass = _create_admin_user(db, "rbac_admin@test.com")
    res_login = client.post("/api/v1/auth/login", json={"email": "rbac_admin@test.com", "password": admin_pass})
    h_admin = {"Authorization": f"Bearer {res_login.json()['access_token']}"}

    _client_id, h_client = _setup_user(client, "rbac_client@test.com", role="CLIENT")
    _lawyer_id, h_lawyer = _setup_user(client, "rbac_lawyer@test.com", role="LAWYER")

    # 1. Unauthenticated access denied
    assert client.get("/api/v1/admin/verifications").status_code == 401
    assert client.get("/api/v1/admin/audit").status_code == 401
    assert client.get("/api/v1/audit").status_code == 401
    assert client.get("/api/v1/analytics/funnel").status_code == 401

    # 2. Client access denied (403)
    assert client.get("/api/v1/admin/verifications", headers=h_client).status_code == 403
    assert client.get("/api/v1/admin/audit", headers=h_client).status_code == 403
    assert client.get("/api/v1/audit", headers=h_client).status_code == 403
    assert client.get("/api/v1/analytics/funnel", headers=h_client).status_code == 403

    # 3. Lawyer access denied (403)
    assert client.get("/api/v1/admin/verifications", headers=h_lawyer).status_code == 403
    assert client.get("/api/v1/admin/audit", headers=h_lawyer).status_code == 403
    assert client.get("/api/v1/audit", headers=h_lawyer).status_code == 403
    assert client.get("/api/v1/analytics/funnel", headers=h_lawyer).status_code == 403

    # 4. Admin access allowed (200)
    assert client.get("/api/v1/admin/verifications", headers=h_admin).status_code == 200
    assert client.get("/api/v1/admin/audit", headers=h_admin).status_code == 200
    assert client.get("/api/v1/audit", headers=h_admin).status_code == 200
    assert client.get("/api/v1/analytics/funnel", headers=h_admin).status_code == 200

    # 5. Privilege Escalation: Client cannot change role or admin fields via profile update
    res_esc = client.patch("/api/v1/profiles/client", json={"role": "ADMIN"}, headers=h_client)
    assert res_esc.status_code == 422  # Extra fields forbidden


def test_lawyer_verification_queue_and_state_machine(client: TestClient, db: Session):
    _admin_id, admin_pass = _create_admin_user(db, "verif_admin@test.com")
    res_login = client.post("/api/v1/auth/login", json={"email": "verif_admin@test.com", "password": admin_pass})
    h_admin = {"Authorization": f"Bearer {res_login.json()['access_token']}"}

    _lawyer_id, h_lawyer = _setup_user(client, "verif_lawyer@test.com", role="LAWYER")

    # 1. Lawyer submits verification
    res_sub = client.post(
        "/api/v1/profiles/lawyer/verification",
        json={"enrollment_number": "D/1234/2020", "state_bar_council": "Bar Council of Delhi"},
        headers=h_lawyer,
    )
    assert res_sub.status_code == 200
    verif_id = res_sub.json()["id"]
    assert res_sub.json()["status"] == "PENDING"

    # 2. Admin inspects queue
    res_queue = client.get("/api/v1/admin/verifications", headers=h_admin)
    assert res_queue.status_code == 200
    assert any(v["id"] == verif_id for v in res_queue.json()["items"])

    # 3. Admin approves verification
    res_app = client.post(f"/api/v1/admin/verifications/{verif_id}/approve", headers=h_admin)
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "APPROVED"

    # 4. State Machine Freeze: Re-approving or rejecting processed verification is rejected (403)
    assert client.post(f"/api/v1/admin/verifications/{verif_id}/approve", headers=h_admin).status_code == 403
    assert client.post(f"/api/v1/admin/verifications/{verif_id}/reject", headers=h_admin).status_code == 403

    # 5. Non-existent verification -> 404
    fake_verif = str(uuid.uuid4())
    assert client.post(f"/api/v1/admin/verifications/{fake_verif}/approve", headers=h_admin).status_code == 404


def test_public_visibility_integration_with_verification_and_suspension(client: TestClient, db: Session):
    _admin_id, admin_pass = _create_admin_user(db, "vis_admin@test.com")
    res_login = client.post("/api/v1/auth/login", json={"email": "vis_admin@test.com", "password": admin_pass})
    h_admin = {"Authorization": f"Bearer {res_login.json()['access_token']}"}

    _client_id, h_client = _setup_user(client, "vis_client@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(client, "vis_lawyer@test.com", role="LAWYER", full_name="Advocate Sharma")

    # 1. Initially unverified lawyer is hidden from public discovery
    res_search1 = client.get("/api/v1/lawyers", headers=h_client)
    assert not any(l["user_id"] == lawyer_id for l in res_search1.json()["items"])

    # 2. Lawyer submits verification and admin approves
    res_sub = client.post(
        "/api/v1/profiles/lawyer/verification",
        json={"enrollment_number": "MH/5678/2018", "state_bar_council": "Bar Council of Maharashtra"},
        headers=h_lawyer,
    )
    verif_id = res_sub.json()["id"]
    client.post(f"/api/v1/admin/verifications/{verif_id}/approve", headers=h_admin)

    # 3. Approved + Active lawyer is now publicly discoverable
    res_search2 = client.get("/api/v1/lawyers", headers=h_client)
    assert any(l["user_id"] == lawyer_id for l in res_search2.json()["items"])
    assert client.get(f"/api/v1/lawyers/{lawyer_id}", headers=h_client).status_code == 200

    # 4. Admin suspends lawyer account
    res_susp = client.post(f"/api/v1/admin/users/{lawyer_id}/suspend", headers=h_admin)
    assert res_susp.status_code == 200
    assert res_susp.json()["account_status"] == "SUSPENDED"

    # 5. Suspended lawyer disappears from public discovery and returns 404 on direct lookup
    res_search3 = client.get("/api/v1/lawyers", headers=h_client)
    assert not any(l["user_id"] == lawyer_id for l in res_search3.json()["items"])
    assert client.get(f"/api/v1/lawyers/{lawyer_id}", headers=h_client).status_code == 404

    # 6. Admin reactivates lawyer account
    res_react = client.post(f"/api/v1/admin/users/{lawyer_id}/reactivate", headers=h_admin)
    assert res_react.status_code == 200
    assert res_react.json()["account_status"] == "ACTIVE"

    # 7. Reactivated lawyer reappears
    res_search4 = client.get("/api/v1/lawyers", headers=h_client)
    assert any(l["user_id"] == lawyer_id for l in res_search4.json()["items"])


def test_admin_self_suspension_protection_and_audit_logs(client: TestClient, db: Session):
    admin_id, admin_pass = _create_admin_user(db, "self_admin@test.com")
    res_login = client.post("/api/v1/auth/login", json={"email": "self_admin@test.com", "password": admin_pass})
    h_admin = {"Authorization": f"Bearer {res_login.json()['access_token']}"}

    client_id, h_client = _setup_user(client, "target_client@test.com", role="CLIENT")

    # 1. Admin cannot suspend self (403)
    res_self = client.post(f"/api/v1/admin/users/{admin_id}/suspend", headers=h_admin)
    assert res_self.status_code == 403
    assert "cannot suspend their own account" in res_self.json()["error"]["message"]

    # 2. Admin suspends target user -> Audit Log created
    client.post(f"/api/v1/admin/users/{client_id}/suspend", headers=h_admin)

    # 3. Query audit logs via both /api/v1/admin/audit and /api/v1/audit
    res_audit1 = client.get("/api/v1/admin/audit?event_type=USER_ACCOUNT_SUSPENDED", headers=h_admin)
    assert res_audit1.status_code == 200
    assert res_audit1.json()["total"] >= 1
    item = res_audit1.json()["items"][0]
    assert item["event_type"] == "USER_ACCOUNT_SUSPENDED"
    assert item["entity_id"] == client_id
    assert item["actor_user_id"] == admin_id

    res_audit2 = client.get("/api/v1/audit?event_type=USER_ACCOUNT_SUSPENDED", headers=h_admin)
    assert res_audit2.status_code == 200
    assert res_audit2.json()["total"] >= 1

    # 4. Suspended client immediately loses access to protected endpoints (401 Inactive)
    assert client.get("/api/v1/cases", headers=h_client).status_code == 401
