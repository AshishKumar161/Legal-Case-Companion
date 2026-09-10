from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.security import create_access_token, hash_password
from app.models.case import (
    Case,
    CaseParticipant,
    CaseStatus,
    ParticipantRole,
    ParticipantStatus,
)
from app.models.document import Document, DocumentSecurityStatus
from app.models.note import CaseNote, CaseNoteVisibility
from app.models.task import CaseTask, TaskPriority, TaskStatus
from app.models.user import AccountStatus, User, UserRole


def _create_user(db: Session, email: str, role: UserRole = UserRole.CLIENT) -> tuple[User, dict[str, str]]:
    user = User(
        id=generate_uuid7(),
        email=email,
        password_hash=hash_password("SecurePassword123!"),
        role=role,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id), user.role.value)
    return user, {"Authorization": f"Bearer {token}"}


def _create_case(db: Session, owner: User, title: str = "Test Case") -> Case:
    case = Case(
        id=generate_uuid7(),
        title=title,
        description="Case description",
        status=CaseStatus.OPEN,
    )
    db.add(case)
    db.flush()

    participant = CaseParticipant(
        id=generate_uuid7(),
        case_id=case.id,
        user_id=owner.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
        joined_at=datetime.now(UTC),
    )
    db.add(participant)
    db.commit()
    db.refresh(case)
    return case


def test_repository_wide_idor_sweep(client: TestClient, db: Session):
    """Verifies that accessing unrelated or cross-user resources returns 404 Not Found."""
    user_a, _headers_a = _create_user(db, "idor_user_a@test.com")
    _user_b, headers_b = _create_user(db, "idor_user_b@test.com")

    # User A creates a case
    case_a = _create_case(db, user_a, "Secret Case A")

    # User A adds a note, task, and document
    note_a = CaseNote(
        id=generate_uuid7(),
        case_id=case_a.id,
        author_user_id=user_a.id,
        title="Note A",
        content="Secret Note Content",
        visibility=CaseNoteVisibility.CLIENT_PRIVATE,
    )
    task_a = CaseTask(
        id=generate_uuid7(),
        case_id=case_a.id,
        created_by_user_id=user_a.id,
        title="Task A",
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
    )
    doc_a = Document(
        id=generate_uuid7(),
        case_id=case_a.id,
        uploaded_by=user_a.id,
        filename="confidential.pdf",
        file_size=1024,
        mime_type="application/pdf",
        storage_key="cases/secret/confidential.pdf",
        security_status=DocumentSecurityStatus.SAFE,
    )
    db.add_all([note_a, task_a, doc_a])
    db.commit()

    # User B attempts to access User A's case -> 404
    res_case = client.get(f"/api/v1/cases/{case_a.id}", headers=headers_b)
    assert res_case.status_code == 404
    assert res_case.json()["error"]["code"] == "NOT_FOUND"

    # User B attempts to access User A's note -> 404
    res_note = client.get(f"/api/v1/cases/{case_a.id}/notes/{note_a.id}", headers=headers_b)
    assert res_note.status_code == 404

    # User B attempts to access User A's task -> 404
    res_task = client.get(f"/api/v1/cases/{case_a.id}/tasks/{task_a.id}", headers=headers_b)
    assert res_task.status_code == 404

    # User B attempts to download User A's document -> 404
    res_doc = client.get(f"/api/v1/documents/{doc_a.id}/download", headers=headers_b)
    assert res_doc.status_code == 404

    # User B attempts to access non-existent / random UUID -> 404
    random_uuid = generate_uuid7()
    res_random = client.get(f"/api/v1/cases/{random_uuid}", headers=headers_b)
    assert res_random.status_code == 404


def test_pagination_abuse_and_boundary_enforcement(client: TestClient, db: Session):
    """Verifies that extreme or negative pagination queries are rejected with 422."""
    _user, headers = _create_user(db, "pagination_test@test.com")

    # 1. Limit exceeding maximum allowed (100) -> 422
    res_huge = client.get("/api/v1/cases?limit=1000000", headers=headers)
    assert res_huge.status_code == 422
    assert res_huge.json()["error"]["code"] == "VALIDATION_ERROR"

    # 2. Negative limit -> 422
    res_neg_limit = client.get("/api/v1/cases?limit=-1", headers=headers)
    assert res_neg_limit.status_code == 422

    # 3. Negative skip -> 422
    res_neg_skip = client.get("/api/v1/cases?skip=-5", headers=headers)
    assert res_neg_skip.status_code == 422

    # 4. Valid pagination boundary -> 200
    res_valid = client.get("/api/v1/cases?skip=0&limit=100", headers=headers)
    assert res_valid.status_code == 200


def test_input_validation_and_malformed_types(client: TestClient, db: Session):
    """Verifies that invalid UUIDs and malformed enum payloads fail safely."""
    _user, headers = _create_user(db, "input_abuse@test.com")

    # 1. Malformed UUID in path
    res_bad_uuid = client.get("/api/v1/cases/not-a-valid-uuid", headers=headers)
    assert res_bad_uuid.status_code == 422
    assert res_bad_uuid.json()["error"]["code"] == "VALIDATION_ERROR"
    assert res_bad_uuid.json()["error"]["request_id"] is not None

    # 2. Invalid Enum value in query
    res_bad_enum = client.get("/api/v1/cases?status=INVALID_STATUS_ENUM", headers=headers)
    assert res_bad_enum.status_code == 422


def test_mass_assignment_protection_across_models(client: TestClient, db: Session):
    """Verifies that internal fields cannot be modified via update payloads."""
    user, headers = _create_user(db, "mass_assign@test.com")
    case = _create_case(db, user, "Original Title")

    # Attempt to inject internal fields into Case update
    res_case_update = client.patch(
        f"/api/v1/cases/{case.id}",
        json={"title": "Updated Title", "client_user_id": str(generate_uuid7()), "created_at": "2020-01-01T00:00:00Z"},
        headers=headers,
    )
    # Extra fields are forbidden by Pydantic CaseUpdate schema
    assert res_case_update.status_code == 422


def test_soft_deleted_resource_inaccessibility(client: TestClient, db: Session):
    """Verifies that soft-deleted cases and documents are never exposed."""
    user, headers = _create_user(db, "soft_delete_user@test.com")
    case = _create_case(db, user, "Case to delete")

    # 1. Delete case
    res_del = client.delete(f"/api/v1/cases/{case.id}", headers=headers)
    assert res_del.status_code == 204

    # 2. Direct get returns 404
    assert client.get(f"/api/v1/cases/{case.id}", headers=headers).status_code == 404

    # 3. List cases does not include deleted case
    res_list = client.get("/api/v1/cases", headers=headers)
    assert res_list.status_code == 200
    assert not any(c["id"] == str(case.id) for c in res_list.json()["items"])


def test_production_security_headers_present(client: TestClient):
    """Verifies that essential security headers are applied to responses."""
    res = client.get("/api/v1/health/live")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "default-src 'none'" in res.headers.get("Content-Security-Policy", "")
    assert "Strict-Transport-Security" in res.headers


def test_correlation_id_propagation_and_isolation(client: TestClient):
    """Verifies X-Request-ID propagation to response headers and error payload."""
    custom_id = "test-corr-id-1234567890"
    res = client.get("/api/v1/health/live", headers={"X-Request-ID": custom_id})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == custom_id

    # Test error response carries request ID
    res_err = client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000", headers={"X-Request-ID": custom_id})
    assert res_err.status_code == 401
    assert res_err.json()["error"]["request_id"] == custom_id
