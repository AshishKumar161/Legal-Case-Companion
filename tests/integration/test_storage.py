from fastapi.testclient import TestClient

from app.models.document import DocumentSecurityStatus


def _setup_user(
    client: TestClient,
    email: str,
    password: str,
    role: str = "CLIENT",
    full_name: str = "Test User",
):
    """Register a user and return access token + headers."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": role,
            "full_name": full_name,
        },
    )
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


def test_unauthorized_document_upload(client: TestClient, db):
    # A user cannot upload to a case they are not part of
    _, headers1 = _setup_user(
        client, "client1@test.com", "SecurePassword123!", full_name="Test User 1"
    )
    _, headers2 = _setup_user(
        client, "client2@test.com", "SecurePassword123!", full_name="Test User 2"
    )

    # Client 1 creates a case
    case_res = client.post(
        "/api/v1/cases",
        json={"title": "C1 Case", "description": "Desc"},
        headers=headers1,
    )
    case_id = case_res.json()["id"]

    # Client 2 tries to upload a document to Client 1's case
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "secret.pdf",
            "mime_type": "application/pdf",
            "file_size": 1024,
        },
        headers=headers2,
    )
    assert upload_res.status_code == 404  # IDOR protection acts as 404


def test_document_lifecycle_and_download(client: TestClient, db):
    _, headers = _setup_user(
        client, "doc@test.com", "SecurePassword123!", full_name="Doc User"
    )
    _, other_headers = _setup_user(
        client, "other@test.com", "SecurePassword123!", full_name="Other User"
    )

    # Create case
    case_res = client.post(
        "/api/v1/cases",
        json={"title": "My Case", "description": "Desc"},
        headers=headers,
    )
    case_id = case_res.json()["id"]

    # Request Upload (PENDING state)
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "test.pdf",
            "mime_type": "application/pdf",
            "file_size": 1024,
        },
        headers=headers,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document"]["id"]
    upload_url = upload_res.json()["upload_url"]

    assert "mock-storage/upload" in upload_url  # Mock storage in testing
    assert upload_res.json()["document"]["security_status"] == "PENDING"

    # Try to download PENDING document -> should fail
    download_res = client.get(f"/api/v1/documents/{doc_id}/download", headers=headers)
    assert download_res.status_code == 403
    assert "not approved" in download_res.json()["error"]["message"].lower()

    # Unauthorized completion attempt
    unauth_comp_res = client.post(
        f"/api/v1/documents/{doc_id}/complete", headers=other_headers
    )
    assert unauth_comp_res.status_code == 404

    # Completion of nonexistent object
    import uuid

    non_existent_id = str(uuid.uuid4())
    missing_comp_res = client.post(
        f"/api/v1/documents/{non_existent_id}/complete", headers=headers
    )
    assert missing_comp_res.status_code == 404

    # Complete upload
    comp_res = client.post(f"/api/v1/documents/{doc_id}/complete", headers=headers)
    assert comp_res.status_code == 200
    assert comp_res.json()["security_status"] == "QUARANTINED"

    # Repeated completion (Invalid state transition from QUARANTINED)
    repeat_comp = client.post(f"/api/v1/documents/{doc_id}/complete", headers=headers)
    assert repeat_comp.status_code == 422

    # Manually transition to SCANNING, REJECTED and verify download is blocked
    import uuid

    for state in ["SCANNING", "REJECTED"]:
        from app.models.document import Document

        # Manual db update for testing non-SAFE states
        doc = db.query(Document).filter(Document.id == uuid.UUID(doc_id)).first()
        doc.security_status = getattr(DocumentSecurityStatus, state)
        db.commit()

        # Verify download blocked
        res = client.get(f"/api/v1/documents/{doc_id}/download", headers=headers)
        assert res.status_code == 403

    # Simulate upload completion and scan to SAFE
    doc = db.query(Document).filter(Document.id == uuid.UUID(doc_id)).first()
    doc.security_status = DocumentSecurityStatus.QUARANTINED
    db.commit()
    scan_res = client.post(
        f"/api/v1/documents/{doc_id}/scan?is_safe=true", headers=headers
    )
    assert scan_res.status_code == 200

    # Try download SAFE document -> should succeed
    download_res = client.get(f"/api/v1/documents/{doc_id}/download", headers=headers)
    assert download_res.status_code == 200
    assert "mock-storage/download" in download_res.json()["download_url"]

    # Try download with another user's headers -> should fail (404 for IDOR)
    other_download = client.get(
        f"/api/v1/documents/{doc_id}/download", headers=other_headers
    )
    assert other_download.status_code == 404

    # Delete document (soft-delete only)
    delete_res = client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert delete_res.status_code == 204

    # Verify deletion prevents download
    get_res = client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert get_res.status_code == 404

    download_deleted = client.get(
        f"/api/v1/documents/{doc_id}/download", headers=headers
    )
    assert download_deleted.status_code == 404

    # Verify Audit log created for deletion
    res_audit = client.get("/api/v1/audit", headers=headers)
    if res_audit.status_code == 200:
        events = res_audit.json().get("items", [])
        assert any(
            e["event_type"] == "DOCUMENT_DELETED" and e["entity_id"] == doc_id
            for e in events
        )


def test_document_mime_type_validation(client: TestClient, db):
    """Phase 8: Only PDF, PNG, JPEG are allowed."""
    _, headers = _setup_user(
        client, "mimetype@test.com", "SecurePassword123!", full_name="MIME User"
    )
    case_res = client.post(
        "/api/v1/cases",
        json={"title": "MIME Case", "description": "Desc"},
        headers=headers,
    )
    case_id = case_res.json()["id"]

    # Attempt upload with unsupported MIME type
    res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "script.js",
            "mime_type": "application/javascript",
            "file_size": 100,
        },
        headers=headers,
    )
    assert res.status_code == 422
    assert "Unsupported file type" in res.json()["error"]["message"]

    # Attempt upload with allowed MIME type should succeed
    res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "photo.png", "mime_type": "image/png", "file_size": 5000},
        headers=headers,
    )
    assert res.status_code == 201


def test_document_file_size_validation(client: TestClient, db):
    """Phase 8: File size must be > 0 and <= 10MB."""
    _, headers = _setup_user(
        client, "filesize@test.com", "SecurePassword123!", full_name="Size User"
    )
    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Size Case", "description": "Desc"},
        headers=headers,
    )
    case_id = case_res.json()["id"]

    # Zero file size
    res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "empty.pdf", "mime_type": "application/pdf", "file_size": 0},
        headers=headers,
    )
    assert res.status_code == 422

    # Over 10MB
    res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "huge.pdf",
            "mime_type": "application/pdf",
            "file_size": 11_000_000,
        },
        headers=headers,
    )
    assert res.status_code == 422
    assert "maximum" in res.json()["error"]["message"].lower()
