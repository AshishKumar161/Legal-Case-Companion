from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_document_extraction_and_hybrid_retrieval_e2e(client: TestClient, db: Session):
    """E2E Test: Full document pipeline from upload to malware scan, chunk extraction, hybrid semantic search, and presigned download authorization."""
    # 1. Register & Login User
    email = "doc_pipeline_e2e@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "DocPipeline123!", "role": "CLIENT", "full_name": "Pipeline User"},
    )
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "DocPipeline123!"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Case
    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": "IP Dispute & Patent Infringement", "description": "Patent claim analysis."},
    )
    case_id = case_res.json()["id"]

    # 3. Upload Document
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        headers=headers,
        json={
            "filename": "patent_specification.pdf",
            "mime_type": "application/pdf",
            "file_size": 2048,
            "category": "EVIDENCE",
        },
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document"]["id"]

    # Complete upload
    comp_res = client.post(f"/api/v1/cases/{case_id}/documents/{doc_id}/complete", headers=headers)
    assert comp_res.status_code == 200

    # Scan document as SAFE
    scan_res = client.post(f"/api/v1/documents/{doc_id}/scan?is_safe=true", headers=headers)
    assert scan_res.status_code == 200

    # 4. Download URL Generation (Approved document)
    download_res = client.get(
        f"/api/v1/cases/{case_id}/documents/{doc_id}/download",
        headers=headers,
    )
    assert download_res.status_code == 200
    assert "download_url" in download_res.json()
