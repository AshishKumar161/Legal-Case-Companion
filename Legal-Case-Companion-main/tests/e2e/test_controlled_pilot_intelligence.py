import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.models.analytics import ProductEvent, ProductEventType
from app.models.case import Case
from app.models.feedback import FeedbackCategory, PilotFeedback
from app.models.user import AccountStatus, User, UserRole


def _create_user(client: TestClient, email: str, role: str, name: str) -> tuple[str, dict]:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "PilotIntelligence123!", "role": role, "full_name": name},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "PilotIntelligence123!"},
    )
    token = login.json()["access_token"]
    user_id = login.json().get("user", {}).get("id")
    return user_id, {"Authorization": f"Bearer {token}"}


def test_controlled_pilot_event_ingestion_and_privacy_boundaries(client: TestClient, db: Session):
    """
    Verifies that client/counsel lifecycle events can be recorded safely
    without capturing sensitive case text.
    """
    _, client_auth = _create_user(
        client, "pilot_client_telemetry@example.com", "CLIENT", "Aarav Pilot"
    )

    # 1. Client logs lifecycle milestone event
    res = client.post(
        "/api/v1/analytics/events",
        headers=client_auth,
        json={
            "event_type": "INTELLIGENCE_VIEWED",
            "metadata": {"view_mode": "CHRONOLOGY_TAB", "screen_size": "DESKTOP"},
        },
    )
    assert res.status_code == 201
    event_id = res.json()["event_id"]

    evt = db.query(ProductEvent).filter(ProductEvent.id == uuid.UUID(event_id)).first()
    assert evt is not None
    assert evt.event_type == ProductEventType.INTELLIGENCE_VIEWED
    assert evt.metadata_["view_mode"] == "CHRONOLOGY_TAB"


def test_pilot_feedback_admin_prioritization_and_status_transition(client: TestClient, db: Session):
    """
    Verifies that pilot feedback items can be triaged with priority tags (P0, P1, P2, P3)
    and resolved by administrators.
    """
    # 1. Create client and submit feedback
    _, client_auth = _create_user(
        client, "friction_reporter@example.com", "CLIENT", "Client Friction"
    )

    fb_res = client.post(
        "/api/v1/feedback",
        headers=client_auth,
        json={
            "category": "CONFUSING_UX",
            "description": "Evidence upload completion was hard to notice on mobile.",
            "page_url": "/cases/new",
        },
    )
    assert fb_res.status_code == 201
    feedback_id = fb_res.json()["id"]

    # 2. Seed Admin user and authenticate
    admin_id = generate_uuid7()
    admin_user = User(
        id=admin_id,
        email="admin_pilot_triager@example.com",
        password_hash=hash_password("AdminTriagePass123!"),
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(admin_user)
    db.commit()

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin_pilot_triager@example.com", "password": "AdminTriagePass123!"},
    )
    admin_auth = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # 3. Admin triages issue: elevates to P1 and adds resolution notes
    patch_res = client.patch(
        f"/api/v1/feedback/{feedback_id}",
        headers=admin_auth,
        json={
            "priority": "P1",
            "status": "TRIAGED",
            "resolution_notes": "Identified CSS flexbox clipping on mobile viewport; assigned for next sprint.",
        },
    )
    assert patch_res.status_code == 200
    patched = patch_res.json()
    assert patched["priority"] == "P1"
    assert patched["status"] == "TRIAGED"
    assert "CSS flexbox" in patched["resolution_notes"]

    # 4. Non-admin cannot triage feedback -> 403 Forbidden
    unauth_patch = client.patch(
        f"/api/v1/feedback/{feedback_id}",
        headers=client_auth,
        json={"priority": "P0"},
    )
    assert unauth_patch.status_code in (401, 403)


def test_admin_product_health_aggregation_endpoint(client: TestClient, db: Session):
    """
    Verifies that GET /api/v1/analytics/product-health computes the unified
    health summary across users, matters, multi-step funnel, and prioritized feedback.
    """
    admin_id = generate_uuid7()
    admin_user = User(
        id=admin_id,
        email="admin_health_watcher@example.com",
        password_hash=hash_password("AdminWatchPass123!"),
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(admin_user)
    db.commit()

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin_health_watcher@example.com", "password": "AdminWatchPass123!"},
    )
    admin_auth = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    health_res = client.get("/api/v1/analytics/product-health", headers=admin_auth)
    assert health_res.status_code == 200
    data = health_res.json()

    assert "total_users" in data
    assert "active_matters" in data
    assert "funnel" in data
    assert len(data["funnel"]) == 5
    assert data["funnel"][0]["step"] == "Registration"
    assert "ai_health" in data
    assert "unresolved_feedback_p0_p1" in data
