from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.case import Case, CaseStatus
from app.models.document import Document, DocumentSecurityStatus
from app.models.user import LawyerProfile, LawyerVerification, VerificationStatus


def _setup_user(
    client: TestClient,
    email: str,
    password: str = "SecurePassword123!",
    role: str = "CLIENT",
    full_name: str = "Test User",
):
    """Register and authenticate a user."""
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


def _verify_lawyer(db: Session, lawyer_user_id: str):
    profile = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == UUID(lawyer_user_id))
        .first()
    )
    assert profile is not None
    ver = LawyerVerification(
        lawyer_profile_id=profile.id,
        enrollment_number=f"BAR/{str(lawyer_user_id)[:6]}/2020",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()
    db.refresh(profile)
    return profile


def test_document_upload_validation_and_storage_key_partitioning(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "doc_up_owner@test.com", role="CLIENT")
    _other_id, h_other = _setup_user(client, "doc_up_other@test.com", role="CLIENT")

    # 1. Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Contract Breach Matter", "description": "Vendor non-delivery"},
        headers=h_owner,
    )
    assert res_case.status_code == 201
    case_id = res_case.json()["id"]

    # 2. Valid Document Upload Init with category, checksum, and description
    valid_checksum = "a" * 64
    res_up = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "Vendor_Agreement_2026.pdf",
            "mime_type": "application/pdf",
            "file_size": 1024 * 1024,  # 1 MB
            "document_type": "CONTRACT",
            "description": "Master Service Agreement between vendor and client",
            "checksum": valid_checksum,
            "is_confidential": True,
        },
        headers=h_owner,
    )
    assert res_up.status_code == 201
    up_data = res_up.json()
    doc = up_data["document"]
    doc_id = doc["id"]

    assert doc["filename"] == "Vendor_Agreement_2026.pdf"
    assert doc["document_type"] == "CONTRACT"
    assert doc["description"] == "Master Service Agreement between vendor and client"
    assert doc["checksum"] == valid_checksum
    assert doc["version"] == 1
    assert doc["is_confidential"] is True
    assert doc["security_status"] == "PENDING"
    assert doc["storage_key"] == f"cases/{case_id}/documents/{doc_id}"
    assert "upload_url" in up_data

    # 3. Path Traversal & Malformed Filename Rejections -> 422
    invalid_filenames = [
        "../secret.pdf",
        "dir/file.pdf",
        "dir\\file.pdf",
        "file\x00name.pdf",
        "",
        "   ",
        "a" * 256 + ".pdf",
    ]
    for bad_name in invalid_filenames:
        res_bad = client.post(
            f"/api/v1/cases/{case_id}/documents/upload-init",
            json={
                "filename": bad_name,
                "mime_type": "application/pdf",
                "file_size": 1024,
            },
            headers=h_owner,
        )
        assert res_bad.status_code == 422, f"Expected 422 for filename '{bad_name}', got {res_bad.status_code}"

    # 4. Unsupported MIME Types -> 422
    unsupported_mimes = ["application/x-executable", "text/html", "application/javascript", "image/gif"]
    for bad_mime in unsupported_mimes:
        res_mime = client.post(
            f"/api/v1/cases/{case_id}/documents/upload-init",
            json={
                "filename": "test.file",
                "mime_type": bad_mime,
                "file_size": 1024,
            },
            headers=h_owner,
        )
        assert res_mime.status_code == 422
        assert "Unsupported file type" in res_mime.json()["error"]["message"]

    # 5. Invalid File Size (0 bytes or > 10MB) -> 422
    assert client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "empty.pdf", "mime_type": "application/pdf", "file_size": 0},
        headers=h_owner,
    ).status_code == 422

    assert client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "huge.pdf", "mime_type": "application/pdf", "file_size": 15 * 1024 * 1024},
        headers=h_owner,
    ).status_code == 422

    # 6. Invalid Checksum Format -> 422
    assert client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "check.pdf",
            "mime_type": "application/pdf",
            "file_size": 1024,
            "checksum": "invalid_non_hex_or_too_short",
        },
        headers=h_owner,
    ).status_code == 422

    # 7. Non-participant upload attempt -> 404 (BOLA/IDOR protection)
    assert client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "other.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=h_other,
    ).status_code == 404


def test_case_workspace_document_summary_and_aggregation(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "ws_doc_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(client, "ws_doc_lawyer@test.com", role="LAWYER", full_name="Adv. Bose")
    _verify_lawyer(db, lawyer_id)

    # 1. Create Case and add lawyer
    res_case = client.post("/api/v1/cases", json={"title": "Summary Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]
    client.post(f"/api/v1/cases/{case_id}/participants", json={"user_id": lawyer_id, "participant_role": "LAWYER"}, headers=h_owner)

    # 2. Upload multiple documents across categories
    categories = [
        ("contract.pdf", "CONTRACT", 2048),
        ("evidence1.png", "EVIDENCE", 4096),
        ("pleading.pdf", "PLEADINGS", 8192),
        ("order.pdf", "COURT_ORDER", 1024),
        ("notice.pdf", "NOTICE", 1024),
    ]
    doc_ids = []
    for fn, cat, sz in categories:
        res = client.post(
            f"/api/v1/cases/{case_id}/documents/upload-init",
            json={"filename": fn, "mime_type": "application/pdf" if fn.endswith(".pdf") else "image/png", "file_size": sz, "document_type": cat},
            headers=h_owner,
        )
        assert res.status_code == 201
        doc_ids.append(res.json()["document"]["id"])

    # Transition 2 to SAFE, 1 to QUARANTINED, 1 to REJECTED, 1 remains PENDING
    docs = db.query(Document).filter(Document.case_id == UUID(case_id)).all()
    docs[0].security_status = DocumentSecurityStatus.SAFE
    docs[1].security_status = DocumentSecurityStatus.SAFE
    docs[2].security_status = DocumentSecurityStatus.QUARANTINED
    docs[3].security_status = DocumentSecurityStatus.REJECTED
    # docs[4] is PENDING
    db.commit()

    # 3. Test GET /cases/{case_id}/documents/summary
    res_summary = client.get(f"/api/v1/cases/{case_id}/documents/summary", headers=h_owner)
    assert res_summary.status_code == 200
    s_data = res_summary.json()
    assert s_data["total"] == 5
    assert s_data["safe"] == 2
    assert s_data["pending"] == 1
    assert s_data["quarantined"] == 1
    assert s_data["rejected"] == 1
    assert s_data["by_category"]["CONTRACT"] == 1
    assert s_data["by_category"]["EVIDENCE"] == 1
    assert s_data["by_category"]["PLEADINGS"] == 1
    assert s_data["by_category"]["COURT_ORDER"] == 1
    assert s_data["by_category"]["NOTICE"] == 1

    # 4. Test GET /cases/{case_id}/workspace includes documents_summary
    res_ws = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_lawyer)
    assert res_ws.status_code == 200
    ws_data = res_ws.json()
    assert ws_data["document_count"] == 5
    assert ws_data["documents_summary"]["total"] == 5
    assert ws_data["documents_summary"]["safe"] == 2


def test_document_filtering_and_search(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "filter_owner@test.com", role="CLIENT")

    res_case = client.post("/api/v1/cases", json={"title": "Filter Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    # Upload test docs
    doc_meta = [
        ("Property_Deed.pdf", "CONTRACT"),
        ("Police_Complaint.pdf", "PLEADINGS"),
        ("CCTV_Footage_Photo.png", "EVIDENCE"),
        ("Notice_Reply.pdf", "NOTICE"),
    ]
    for fn, cat in doc_meta:
        mime = "application/pdf" if fn.endswith(".pdf") else "image/png"
        client.post(
            f"/api/v1/cases/{case_id}/documents/upload-init",
            json={"filename": fn, "mime_type": mime, "file_size": 2048, "document_type": cat},
            headers=h_owner,
        )

    # 1. Filter by category
    res_cat = client.get(f"/api/v1/cases/{case_id}/documents?document_type=CONTRACT", headers=h_owner)
    assert res_cat.status_code == 200
    assert len(res_cat.json()["items"]) == 1
    assert res_cat.json()["items"][0]["filename"] == "Property_Deed.pdf"

    # 2. Search by filename substring
    res_search = client.get(f"/api/v1/cases/{case_id}/documents?search=photo", headers=h_owner)
    assert res_search.status_code == 200
    assert len(res_search.json()["items"]) == 1
    assert res_search.json()["items"][0]["filename"] == "CCTV_Footage_Photo.png"

    # 3. Pagination verification
    res_pag = client.get(f"/api/v1/cases/{case_id}/documents?skip=0&limit=2", headers=h_owner)
    assert res_pag.status_code == 200
    assert len(res_pag.json()["items"]) == 2
    assert res_pag.json()["total"] == 4


def test_document_metadata_update_lifecycle(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "meta_owner@test.com", role="CLIENT")
    lawyer_id, _h_lawyer = _setup_user(client, "meta_lawyer@test.com", role="LAWYER")
    viewer_id, h_viewer = _setup_user(client, "meta_viewer@test.com", role="CLIENT")
    _other_id, h_other = _setup_user(client, "meta_other@test.com", role="CLIENT")

    res_case = client.post("/api/v1/cases", json={"title": "Meta Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]
    client.post(f"/api/v1/cases/{case_id}/participants", json={"user_id": lawyer_id, "participant_role": "LAWYER"}, headers=h_owner)
    client.post(f"/api/v1/cases/{case_id}/participants", json={"user_id": viewer_id, "participant_role": "VIEWER"}, headers=h_owner)

    # Owner uploads Doc 1
    res_up = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "Initial_Doc.pdf", "mime_type": "application/pdf", "file_size": 1024, "document_type": "MISCELLANEOUS"},
        headers=h_owner,
    )
    doc_id = res_up.json()["document"]["id"]

    # 1. Viewer tries to update metadata -> 403 Forbidden
    res_v_patch = client.patch(
        f"/api/v1/cases/{case_id}/documents/{doc_id}",
        json={"description": "Viewer edit"},
        headers=h_viewer,
    )
    assert res_v_patch.status_code == 403

    # 2. Non-participant tries to update -> 404
    res_un_patch = client.patch(
        f"/api/v1/cases/{case_id}/documents/{doc_id}",
        json={"description": "Hacker edit"},
        headers=h_other,
    )
    assert res_un_patch.status_code == 404

    # 3. Owner updates filename, category, description, confidentiality
    res_patch = client.patch(
        f"/api/v1/cases/{case_id}/documents/{doc_id}",
        json={
            "filename": "Revised_Agreement.pdf",
            "document_type": "CONTRACT",
            "description": "Amended terms and conditions",
            "is_confidential": True,
        },
        headers=h_owner,
    )
    assert res_patch.status_code == 200
    p_data = res_patch.json()
    assert p_data["filename"] == "Revised_Agreement.pdf"
    assert p_data["document_type"] == "CONTRACT"
    assert p_data["description"] == "Amended terms and conditions"
    assert p_data["is_confidential"] is True

    # 4. Top-level endpoint PATCH /documents/{doc_id} also works
    res_top_patch = client.patch(
        f"/api/v1/documents/{doc_id}",
        json={"description": "Final ratified agreement"},
        headers=h_owner,
    )
    assert res_top_patch.status_code == 200
    assert res_top_patch.json()["description"] == "Final ratified agreement"


def test_document_lifecycle_download_gating_and_cross_case_isolation(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "iso_owner@test.com", role="CLIENT")

    # Case A
    res_case_a = client.post("/api/v1/cases", json={"title": "Case A", "description": "D"}, headers=h_owner)
    case_a_id = res_case_a.json()["id"]

    # Case B
    res_case_b = client.post("/api/v1/cases", json={"title": "Case B", "description": "D"}, headers=h_owner)
    case_b_id = res_case_b.json()["id"]

    # Upload Doc in Case A
    res_up_a = client.post(
        f"/api/v1/cases/{case_a_id}/documents/upload-init",
        json={"filename": "CaseA_Doc.pdf", "mime_type": "application/pdf", "file_size": 2048},
        headers=h_owner,
    )
    doc_a_id = res_up_a.json()["document"]["id"]

    # 1. Complete upload: PENDING -> QUARANTINED
    res_comp = client.post(f"/api/v1/cases/{case_a_id}/documents/{doc_a_id}/complete", headers=h_owner)
    assert res_comp.status_code == 200
    assert res_comp.json()["security_status"] == "QUARANTINED"

    # 2. Download blocked for QUARANTINED -> 403
    res_dl_q = client.get(f"/api/v1/cases/{case_a_id}/documents/{doc_a_id}/download", headers=h_owner)
    assert res_dl_q.status_code == 403
    assert "not approved" in res_dl_q.json()["error"]["message"].lower()

    # 3. Simulate scan to SAFE
    doc = db.query(Document).filter(Document.id == UUID(doc_a_id)).first()
    assert doc is not None
    doc.security_status = DocumentSecurityStatus.SAFE
    db.commit()

    # 4. Download allowed for SAFE -> 200 with presigned URL
    res_dl_safe = client.get(f"/api/v1/cases/{case_a_id}/documents/{doc_a_id}/download", headers=h_owner)
    assert res_dl_safe.status_code == 200
    assert "download_url" in res_dl_safe.json()

    # 5. Cross-Case Resource Access Defense:
    # Attempting to access Doc A through Case B URL -> 404 (Cross-case IDOR lockout)
    assert client.get(f"/api/v1/cases/{case_b_id}/documents/{doc_a_id}", headers=h_owner).status_code == 404
    assert client.get(f"/api/v1/cases/{case_b_id}/documents/{doc_a_id}/download", headers=h_owner).status_code == 404
    assert client.patch(f"/api/v1/cases/{case_b_id}/documents/{doc_a_id}", json={"description": "hack"}, headers=h_owner).status_code == 404
    assert client.delete(f"/api/v1/cases/{case_b_id}/documents/{doc_a_id}", headers=h_owner).status_code == 404


def test_closed_and_archived_case_document_safeguards(client: TestClient, db: Session):
    _owner_id, h_owner = _setup_user(client, "closed_owner@test.com", role="CLIENT")

    res_case = client.post("/api/v1/cases", json={"title": "Closed Case", "description": "D"}, headers=h_owner)
    case_id = res_case.json()["id"]

    # Upload Doc while OPEN
    res_up = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "Pre_Close.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=h_owner,
    )
    doc_id = res_up.json()["document"]["id"]

    doc = db.query(Document).filter(Document.id == UUID(doc_id)).first()
    assert doc is not None
    doc.security_status = DocumentSecurityStatus.SAFE
    db.commit()

    # Close the case
    case_obj = db.query(Case).filter(Case.id == UUID(case_id)).first()
    assert case_obj is not None
    case_obj.status = CaseStatus.CLOSED
    db.commit()

    # 1. Uploading new document to CLOSED case -> 422
    res_up_closed = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "New_After_Close.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=h_owner,
    )
    assert res_up_closed.status_code == 422
    assert "closed or cancelled" in res_up_closed.json()["error"]["message"].lower()

    # 2. Deleting document in CLOSED case -> 422
    res_del_closed = client.delete(f"/api/v1/cases/{case_id}/documents/{doc_id}", headers=h_owner)
    assert res_del_closed.status_code == 422
    assert "closed or cancelled" in res_del_closed.json()["error"]["message"].lower()

    # 3. Updating document in CLOSED case -> 422
    res_upd_closed = client.patch(
        f"/api/v1/cases/{case_id}/documents/{doc_id}",
        json={"description": "closed update"},
        headers=h_owner,
    )
    assert res_upd_closed.status_code == 422
    assert "closed or cancelled" in res_upd_closed.json()["error"]["message"].lower()

    # 4. Downloading existing SAFE document in CLOSED case remains allowed for archival access -> 200
    res_dl = client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/download", headers=h_owner)
    assert res_dl.status_code == 200
    assert "download_url" in res_dl.json()
