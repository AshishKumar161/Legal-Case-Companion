import io
from fastapi.testclient import TestClient


def test_client_kyc_lifecycle_full(client: TestClient):
    # 1. Register Client
    email = "kyctest_client@test.com"
    password = "SecurePassword123!"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Rohan Sharma",
            "role": "CLIENT",
        },
    )
    assert reg_res.status_code == 201

    # 2. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Check /me before KYC - should show pending
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["kyc_status"] == "PENDING"
    assert me_data["is_kyc_completed"] is False

    # 4. Check /kyc/status
    status_res = client.get("/api/v1/kyc/status", headers=headers)
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["role"] == "CLIENT"
    assert status_data["kyc_status"] == "PENDING"
    assert status_data["is_kyc_completed"] is False

    # 5. Upload KYC ID proof document
    fake_doc = io.BytesIO(b"%PDF-1.4 Mock Aadhaar / Voter ID Proof Document Data")
    upload_res = client.post(
        "/api/v1/kyc/client/document",
        headers=headers,
        files={"file": ("aadhaar_proof.pdf", fake_doc, "application/pdf")},
    )
    assert upload_res.status_code == 201
    upload_data = upload_res.json()
    assert "storage_key" in upload_data
    assert upload_data["filename"].endswith(".pdf")
    assert len(upload_data["sha256_hash"]) == 64

    # 6. Test submission validation: invalid phone
    bad_submit = client.post(
        "/api/v1/kyc/client/submit",
        headers=headers,
        json={
            "full_name": "Rohan Sharma",
            "phone": "12345",  # Invalid phone
            "id_type": "AADHAAR",
            "id_number": "9999-8888-7777",
            "address": "42 Connaught Place",
            "city": "New Delhi",
            "state": "Delhi",
            "pincode": "110001",
            "dpdp_consent": True,
        },
    )
    assert bad_submit.status_code in (400, 422)

    # 7. Valid KYC submission
    submit_res = client.post(
        "/api/v1/kyc/client/submit",
        headers=headers,
        json={
            "full_name": "Rohan Sharma",
            "phone": "+91 98765 43210",
            "date_of_birth": "1992-05-15",
            "gender": "Male",
            "id_type": "AADHAAR",
            "id_number": "9999-8888-7777",
            "address": "Flat 402, Block B, Connaught Place",
            "city": "New Delhi",
            "state": "Delhi",
            "pincode": "110001",
            "kyc_document_storage_key": upload_data["storage_key"],
            "kyc_document_filename": upload_data["filename"],
            "dpdp_consent": True,
        },
    )
    assert submit_res.status_code == 200
    res_data = submit_res.json()
    assert res_data["kyc_status"] == "VERIFIED"
    assert res_data["is_kyc_completed"] is True
    assert res_data["phone"] == "9876543210"
    assert res_data["id_number"] == "9999-8888-7777"
    assert res_data["kyc_document_filename"] == upload_data["filename"]

    # 8. Re-check /me after KYC - must be verified!
    me_after = client.get("/api/v1/auth/me", headers=headers)
    assert me_after.status_code == 200
    assert me_after.json()["is_kyc_completed"] is True
    assert me_after.json()["kyc_status"] == "VERIFIED"


def test_lawyer_kyc_status_check(client: TestClient):
    # Register Lawyer
    email = "kyctest_lawyer@test.com"
    password = "SecurePassword123!"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Adv. Sunita Rao",
            "role": "LAWYER",
        },
    )
    assert reg_res.status_code == 201

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Check status
    res = client.get("/api/v1/kyc/status", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "LAWYER"
    assert data["kyc_status"] == "PENDING"
    assert data["is_kyc_completed"] is False
