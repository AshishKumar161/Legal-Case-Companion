from fastapi.testclient import TestClient


def _setup_user(client: TestClient, role: str, email: str, full_name: str):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePassword123!",
            "role": role,
            "full_name": full_name,
        },
    )
    user_id = res_reg.json().get("id")
    res = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"}
    )
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_document_upload_validation(client: TestClient):
    _owner_id, owner_headers = _setup_user(
        client, "CLIENT", "doc_owner@test.com", "Doc Owner"
    )

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Doc Case", "description": "Doc Case Desc"},
        headers=owner_headers,
    )
    case_id = res_case.json()["id"]

    # Test Oversized File
    res_huge = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "huge.pdf",
            "mime_type": "application/pdf",
            "file_size": 20 * 1024 * 1024,
        },
        headers=owner_headers,
    )
    assert res_huge.status_code == 422
    assert "exceeds maximum allowed size" in res_huge.text

    # Test Empty File
    res_empty = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "empty.pdf", "mime_type": "application/pdf", "file_size": 0},
        headers=owner_headers,
    )
    assert res_empty.status_code == 422
    assert "greater than zero" in res_empty.text

    # Test Invalid MIME type
    res_exe = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "malware.exe",
            "mime_type": "application/x-msdownload",
            "file_size": 1024,
        },
        headers=owner_headers,
    )
    assert res_exe.status_code == 422
    assert "Unsupported file type" in res_exe.text

    # Test Path Traversal Filename
    res_trav = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "../../../etc/passwd",
            "mime_type": "application/pdf",
            "file_size": 1024,
        },
        headers=owner_headers,
    )
    assert res_trav.status_code == 422


def test_document_lifecycle_and_pagination(client: TestClient):
    _owner_id, owner_headers = _setup_user(
        client, "CLIENT", "life_owner@test.com", "Life Owner"
    )
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Life Case", "description": "Life Case Desc"},
        headers=owner_headers,
    )
    case_id = res_case.json()["id"]

    # Upload 3 valid documents
    doc_ids = []
    for i in range(3):
        res = client.post(
            f"/api/v1/cases/{case_id}/documents/upload-init",
            json={
                "filename": f"doc_{i}.pdf",
                "mime_type": "application/pdf",
                "file_size": 1024 * 1024,
            },
            headers=owner_headers,
        )
        assert res.status_code == 201
        doc_id = res.json()["document"]["id"]
        doc_ids.append(doc_id)

        # Complete upload
        res_comp = client.post(
            f"/api/v1/documents/{doc_id}/complete", headers=owner_headers
        )
        assert res_comp.status_code == 200
        assert res_comp.json()["security_status"] == "QUARANTINED"

        # Simulate Scan -> SAFE
        res_scan = client.post(
            f"/api/v1/documents/{doc_id}/scan?is_safe=true", headers=owner_headers
        )
        assert res_scan.status_code == 200

    # Test Pagination
    res_list = client.get(
        f"/api/v1/cases/{case_id}/documents?limit=2", headers=owner_headers
    )
    assert res_list.status_code == 200
    assert res_list.json()["total"] == 3
    assert len(res_list.json()["items"]) == 2

    # Test Download
    target_doc = doc_ids[0]
    res_dl = client.get(
        f"/api/v1/documents/{target_doc}/download", headers=owner_headers
    )
    assert res_dl.status_code == 200
    assert "download_url" in res_dl.json()

    # Test Soft Delete
    res_del = client.delete(f"/api/v1/documents/{target_doc}", headers=owner_headers)
    assert res_del.status_code == 204

    # Ensure deleted doc is hidden from list
    res_list_after = client.get(
        f"/api/v1/cases/{case_id}/documents", headers=owner_headers
    )
    assert res_list_after.json()["total"] == 2
    assert target_doc not in [d["id"] for d in res_list_after.json()["items"]]


def test_document_bola_and_roles(client: TestClient):
    _ownerA_id, headersA = _setup_user(client, "CLIENT", "docA@test.com", "Doc A")
    _ownerB_id, headersB = _setup_user(client, "CLIENT", "docB@test.com", "Doc B")
    viewer_id, viewer_headers = _setup_user(
        client, "CLIENT", "viewer@test.com", "Viewer"
    )

    # Case A
    res_caseA = client.post(
        "/api/v1/cases",
        json={"title": "Case A", "description": "Desc A"},
        headers=headersA,
    )
    caseA_id = res_caseA.json()["id"]

    # Add Viewer to Case A
    client.post(
        f"/api/v1/cases/{caseA_id}/participants",
        json={"user_id": viewer_id, "participant_role": "VIEWER"},
        headers=headersA,
    )

    # Owner A uploads Doc
    res_docA = client.post(
        f"/api/v1/cases/{caseA_id}/documents/upload-init",
        json={"filename": "A.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=headersA,
    )
    docA_id = res_docA.json()["document"]["id"]

    # Viewer tries to upload to Case A -> Forbidden (Insufficient permissions to modify)
    res_viewer_upload = client.post(
        f"/api/v1/cases/{caseA_id}/documents/upload-init",
        json={"filename": "V.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=viewer_headers,
    )
    assert res_viewer_upload.status_code == 403

    # Viewer tries to delete Doc A -> Forbidden
    res_viewer_del = client.delete(
        f"/api/v1/documents/{docA_id}", headers=viewer_headers
    )
    assert res_viewer_del.status_code == 403

    # Viewer CAN view metadata (List)
    res_viewer_list = client.get(
        f"/api/v1/cases/{caseA_id}/documents", headers=viewer_headers
    )
    assert res_viewer_list.status_code == 200
    assert res_viewer_list.json()["total"] == 1

    # Owner B tries to access Case A documents -> 404
    res_B_list = client.get(f"/api/v1/cases/{caseA_id}/documents", headers=headersB)
    assert res_B_list.status_code == 404

    # Owner B tries to download Doc A -> 404
    res_B_dl = client.get(f"/api/v1/documents/{docA_id}/download", headers=headersB)
    assert res_B_dl.status_code == 404


def test_deleted_document_download(client: TestClient):
    _owner_id, owner_headers = _setup_user(
        client, "CLIENT", "del_owner@test.com", "Del Owner"
    )
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Del Case", "description": "Del Case Desc"},
        headers=owner_headers,
    )
    case_id = res_case.json()["id"]

    res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "del.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=owner_headers,
    )
    doc_id = res.json()["document"]["id"]

    client.post(f"/api/v1/documents/{doc_id}/complete", headers=owner_headers)
    client.post(f"/api/v1/documents/{doc_id}/scan?is_safe=true", headers=owner_headers)

    client.delete(f"/api/v1/documents/{doc_id}", headers=owner_headers)

    res_dl = client.get(f"/api/v1/documents/{doc_id}/download", headers=owner_headers)
    assert res_dl.status_code == 404
