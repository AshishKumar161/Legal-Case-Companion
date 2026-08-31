
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


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


def test_case_note_creation_visibility_matrix(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "cn_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(
        client, "cn_lawyer@test.com", role="LAWYER", full_name="Adv. Kapoor"
    )
    viewer_id, h_viewer = _setup_user(client, "cn_viewer@test.com", role="CLIENT")
    _unassigned_id, h_unassigned = _setup_user(
        client, "cn_unassigned@test.com", role="CLIENT"
    )

    # 1. Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Corporate Dispute", "description": "Shareholder agreement litigation"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    # Add Lawyer and Viewer
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": viewer_id, "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 2. Client creates CLIENT_PRIVATE note -> 201
    res_c_priv = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={
            "title": "Client Private Strategy",
            "content": "Confidential financial settlement ceiling",
            "visibility": "CLIENT_PRIVATE",
        },
        headers=h_owner,
    )
    assert res_c_priv.status_code == 201
    assert res_c_priv.json()["visibility"] == "CLIENT_PRIVATE"
    assert res_c_priv.json()["is_private"] is True

    # 3. Client creates SHARED note -> 201
    res_c_shared = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={
            "title": "Shared Incident Summary",
            "content": "Facts regarding breach of contract",
            "visibility": "SHARED",
        },
        headers=h_owner,
    )
    assert res_c_shared.status_code == 201
    assert res_c_shared.json()["visibility"] == "SHARED"
    assert res_c_shared.json()["is_private"] is False

    # 4. Client attempts to create LAWYER_PRIVATE note -> 422
    res_c_invalid = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={
            "title": "Spoofed Note",
            "content": "Attempting lawyer work-product creation",
            "visibility": "LAWYER_PRIVATE",
        },
        headers=h_owner,
    )
    assert res_c_invalid.status_code == 422
    assert "Clients cannot create lawyer" in res_c_invalid.json()["error"]["message"]

    # 5. Lawyer creates LAWYER_PRIVATE note -> 201
    res_l_priv = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={
            "title": "Advocate Legal Research",
            "content": "Assessment of precedent cases under Indian Companies Act",
            "visibility": "LAWYER_PRIVATE",
        },
        headers=h_lawyer,
    )
    assert res_l_priv.status_code == 201
    assert res_l_priv.json()["visibility"] == "LAWYER_PRIVATE"
    assert res_l_priv.json()["is_private"] is True

    # 6. Lawyer creates SHARED note -> 201
    res_l_shared = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={
            "title": "Counsel Recommendations",
            "content": "Next steps for documentary filing before High Court",
            "visibility": "SHARED",
        },
        headers=h_lawyer,
    )
    assert res_l_shared.status_code == 201
    assert res_l_shared.json()["visibility"] == "SHARED"
    assert res_l_shared.json()["is_private"] is False

    # 7. Lawyer attempts to create CLIENT_PRIVATE note -> 422
    res_l_invalid = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={
            "title": "Spoofed Client Note",
            "content": "Lawyer attempting client private note",
            "visibility": "CLIENT_PRIVATE",
        },
        headers=h_lawyer,
    )
    assert res_l_invalid.status_code == 422
    assert "Lawyers cannot create client-private" in res_l_invalid.json()["error"]["message"]

    # 8. Viewer attempts to create note -> 403
    res_v_create = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Viewer Note", "content": "Viewer input", "visibility": "SHARED"},
        headers=h_viewer,
    )
    assert res_v_create.status_code == 403

    # 9. Unassigned user attempts to create note -> 404 (Obscured)
    res_un_create = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Intruder Note", "content": "Intruder content", "visibility": "SHARED"},
        headers=h_unassigned,
    )
    assert res_un_create.status_code == 404


def test_cross_leakage_and_workspace_notes_isolation(client: TestClient):
    _owner_id, h_owner = _setup_user(client, "leak_owner@test.com", role="CLIENT")
    lawyer_a_id, h_lawyer_a = _setup_user(
        client, "leak_la@test.com", role="LAWYER", full_name="Adv. Anand"
    )
    lawyer_b_id, h_lawyer_b = _setup_user(
        client, "leak_lb@test.com", role="LAWYER", full_name="Adv. Bose"
    )
    viewer_id, h_viewer = _setup_user(client, "leak_view@test.com", role="CLIENT")
    _unrelated_id, h_unrelated = _setup_user(
        client, "leak_unrel@test.com", role="CLIENT"
    )

    # 1. Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "IP Trademark Dispute", "description": "Infringement lawsuit"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    # Add Lawyer A, Lawyer B, and Viewer
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_a_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_b_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": viewer_id, "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 2. Create 4 Notes:
    # Note 1: Client Private
    note_cp_id = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "CP", "content": "Client only", "visibility": "CLIENT_PRIVATE"},
        headers=h_owner,
    ).json()["id"]

    # Note 2: Lawyer A Private
    note_la_id = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "LA_Priv", "content": "Lawyer A work-product", "visibility": "LAWYER_PRIVATE"},
        headers=h_lawyer_a,
    ).json()["id"]

    # Note 3: Lawyer B Private
    note_lb_id = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "LB_Priv", "content": "Lawyer B work-product", "visibility": "LAWYER_PRIVATE"},
        headers=h_lawyer_b,
    ).json()["id"]

    # Note 4: Shared Note (created by Lawyer A)
    note_sh_id = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Shared", "content": "Shared between counsel and client", "visibility": "SHARED"},
        headers=h_lawyer_a,
    ).json()["id"]

    # 3. Workspace Notes Count Isolation Check:
    # Total notes in DB = 4
    # Owner must see: CP + Shared = 2
    ws_owner = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_owner).json()
    assert ws_owner["notes_count"] == 2

    # Lawyer A must see: LA_Priv + Shared = 2
    ws_la = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_lawyer_a).json()
    assert ws_la["notes_count"] == 2

    # Lawyer B must see: LB_Priv + Shared = 2
    ws_lb = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_lawyer_b).json()
    assert ws_lb["notes_count"] == 2

    # Viewer must see: Shared = 1
    ws_view = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_viewer).json()
    assert ws_view["notes_count"] == 1

    # 4. Note List & ID-level Cross-Leakage Checks:
    # Lawyer A Private Note:
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_la_id}", headers=h_lawyer_a).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_la_id}", headers=h_owner).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_la_id}", headers=h_lawyer_b).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_la_id}", headers=h_viewer).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_la_id}", headers=h_unrelated).status_code == 404

    # Lawyer B Private Note:
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_lb_id}", headers=h_lawyer_b).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_lb_id}", headers=h_lawyer_a).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_lb_id}", headers=h_owner).status_code == 404

    # Client Private Note:
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_cp_id}", headers=h_owner).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_cp_id}", headers=h_lawyer_a).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_cp_id}", headers=h_lawyer_b).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_cp_id}", headers=h_viewer).status_code == 404

    # Shared Note:
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_sh_id}", headers=h_owner).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_sh_id}", headers=h_lawyer_a).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_sh_id}", headers=h_lawyer_b).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_sh_id}", headers=h_viewer).status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_sh_id}", headers=h_unrelated).status_code == 404


def test_note_mutation_rules_and_revocation(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "mut_owner@test.com", role="CLIENT")
    lawyer_a_id, h_lawyer_a = _setup_user(
        client, "mut_la@test.com", role="LAWYER", full_name="Adv. Roy"
    )
    lawyer_b_id, h_lawyer_b = _setup_user(
        client, "mut_lb@test.com", role="LAWYER", full_name="Adv. Sen"
    )
    viewer_id, h_viewer = _setup_user(client, "mut_view@test.com", role="CLIENT")

    # Create Case & Participants
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Arbitration Case", "description": "Construction dispute arbitration"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_a_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_b_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": viewer_id, "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 1. Lawyer A creates a private work-product note
    note_la_priv_id = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "A Private", "content": "Strategy draft", "visibility": "LAWYER_PRIVATE"},
        headers=h_lawyer_a,
    ).json()["id"]

    # 2. Lawyer A creates a shared note
    note_la_shared_id = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "A Shared", "content": "Drafting schedule", "visibility": "SHARED"},
        headers=h_lawyer_a,
    ).json()["id"]

    # Update Permissions:
    # Lawyer A updates their own private note -> 200
    res_up_la = client.patch(
        f"/api/v1/cases/{case_id}/notes/{note_la_priv_id}",
        json={"title": "A Private Updated", "content": "Updated strategy"},
        headers=h_lawyer_a,
    )
    assert res_up_la.status_code == 200
    assert res_up_la.json()["title"] == "A Private Updated"

    # Owner tries to update Lawyer A's private note -> 404 (Obscured)
    res_up_own_priv = client.patch(
        f"/api/v1/cases/{case_id}/notes/{note_la_priv_id}",
        json={"title": "Owner Hijack"},
        headers=h_owner,
    )
    assert res_up_own_priv.status_code == 404

    # Lawyer B tries to update Lawyer A's shared note -> 403 Forbidden
    res_up_lb_sh = client.patch(
        f"/api/v1/cases/{case_id}/notes/{note_la_shared_id}",
        json={"title": "Lawyer B Tamper"},
        headers=h_lawyer_b,
    )
    assert res_up_lb_sh.status_code == 403
    assert "Only the author or case owner" in res_up_lb_sh.json()["error"]["message"]

    # Owner updates Lawyer A's shared note -> 200
    res_up_own_sh = client.patch(
        f"/api/v1/cases/{case_id}/notes/{note_la_shared_id}",
        json={"title": "Owner Approved Schedule"},
        headers=h_owner,
    )
    assert res_up_own_sh.status_code == 200
    assert res_up_own_sh.json()["title"] == "Owner Approved Schedule"

    # Viewer tries to update shared note -> 403
    res_up_v = client.patch(
        f"/api/v1/cases/{case_id}/notes/{note_la_shared_id}",
        json={"title": "Viewer Edit"},
        headers=h_viewer,
    )
    assert res_up_v.status_code == 403

    # Delete Permissions:
    # Lawyer B tries to delete Lawyer A's shared note -> 403
    assert client.delete(f"/api/v1/cases/{case_id}/notes/{note_la_shared_id}", headers=h_lawyer_b).status_code == 403

    # Owner tries to delete Lawyer A's private note -> 404 (Obscured)
    assert client.delete(f"/api/v1/cases/{case_id}/notes/{note_la_priv_id}", headers=h_owner).status_code == 404

    # Lawyer A deletes their own private note -> 204
    assert client.delete(f"/api/v1/cases/{case_id}/notes/{note_la_priv_id}", headers=h_lawyer_a).status_code == 204

    # Revocation: Owner removes Lawyer A
    client.delete(f"/api/v1/cases/{case_id}/participants/{lawyer_a_id}", headers=h_owner)

    # Revoked Lawyer A cannot access notes list or note detail
    assert client.get(f"/api/v1/cases/{case_id}/notes", headers=h_lawyer_a).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/notes/{note_la_shared_id}", headers=h_lawyer_a).status_code == 404
    assert client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "Post Revocation", "content": "Content", "visibility": "SHARED"},
        headers=h_lawyer_a,
    ).status_code == 404

    # Audit Events Verification
    audits = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.metadata_json["case_id"].astext == case_id
            if db.bind.dialect.name == "postgresql"
            else AuditEvent.id.isnot(None)
        )
        .all()
    )
    audit_actions = [a.event_type for a in audits]
    assert "NOTE_CREATED" in audit_actions
    assert "NOTE_UPDATED" in audit_actions
    assert "NOTE_DELETED" in audit_actions
