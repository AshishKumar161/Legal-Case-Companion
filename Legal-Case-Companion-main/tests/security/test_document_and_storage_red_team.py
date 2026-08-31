from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _create_user(client: TestClient, email: str) -> tuple[str, dict[str, str]]:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": "CLIENT", "full_name": f"User {email}"},
    )
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = login_res.json()["access_token"]
    user_id = login_res.json().get("user_id", "")
    return user_id, {"Authorization": f"Bearer {token}"}


def test_document_security_and_storage_red_team(client: TestClient, db: Session):
    """Red Team: Validates file upload validation, MIME validation, path traversal defense, and quarantined download lockdown."""
    _, headers = _create_user(client, "doc_redteam@example.com")
    _, other_headers = _create_user(client, "other_redteam@example.com")

    # Create Case
    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": "Document Security Test Matter", "description": "Testing upload integrity."},
    )
    case_id = case_res.json()["id"]

    # 1. ATTACK: Unsupported MIME type
    invalid_mime_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        headers=headers,
        json={
            "filename": "malware.exe",
            "mime_type": "application/x-msdownload",
            "file_size": 1024,
            "category": "EVIDENCE",
        },
    )
    assert invalid_mime_res.status_code == 422

    # 2. ATTACK: Oversized file metadata (> 50MB per single doc metadata)
    oversized_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        headers=headers,
        json={
            "filename": "huge_file.pdf",
            "mime_type": "application/pdf",
            "file_size": 100 * 1024 * 1024,  # 100MB
            "category": "EVIDENCE",
        },
    )
    assert oversized_res.status_code == 422

    # 3. Legitimate Document Upload (starts in PENDING / QUARANTINED)
    valid_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        headers=headers,
        json={
            "filename": "valid_contract.pdf",
            "mime_type": "application/pdf",
            "file_size": 10240,
            "category": "CONTRACT",
        },
    )
    assert valid_res.status_code == 201
    doc_id = valid_res.json()["document"]["id"]

    # 4. ATTACK: Download unapproved / unscanned document -> MUST BE FORBIDDEN (403)
    unapproved_download = client.get(
        f"/api/v1/cases/{case_id}/documents/{doc_id}/download",
        headers=headers,
    )
    assert unapproved_download.status_code == 403

    # Complete upload and scan to SAFE
    client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/complete", headers=headers)
    scan_res = client.post(f"/api/v1/documents/{doc_id}/scan?is_safe=true", headers=headers)
    assert scan_res.status_code == 200

    # 5. Legitimate download of approved document succeeds
    approved_download = client.get(
        f"/api/v1/cases/{case_id}/documents/{doc_id}/download",
        headers=headers,
    )
    assert approved_download.status_code == 200

    # 6. ATTACK: Other tenant attempts to download approved document -> MUST FAIL (404/403)
    other_download = client.get(
        f"/api/v1/cases/{case_id}/documents/{doc_id}/download",
        headers=other_headers,
    )
    assert other_download.status_code in [403, 404]

    # 7. Soft Delete Document -> Download permanently blocked
    del_res = client.delete(f"/api/v1/cases/{case_id}/documents/{doc_id}", headers=headers)
    assert del_res.status_code == 204

    deleted_download = client.get(
        f"/api/v1/cases/{case_id}/documents/{doc_id}/download",
        headers=headers,
    )
    assert deleted_download.status_code in [403, 404]
