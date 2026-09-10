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


def test_timeline_forgery_prevented(client: TestClient):
    _owner_id, owner_headers = _setup_user(
        client, "CLIENT", "forgery@test.com", "Forgery Test"
    )
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Test Case", "description": "Desc"},
        headers=owner_headers,
    )
    case_id = res_case.json()["id"]

    # Attempting to POST to timeline should fail with 404 or 405 because route is removed
    res = client.post(
        f"/api/v1/cases/{case_id}/timeline",
        json={"event_type": "FAKE", "description": "Fake event"},
        headers=owner_headers,
    )
    assert res.status_code in [404, 405]


def test_timeline_generation_and_bola(client: TestClient):
    _ownerA_id, headersA = _setup_user(client, "CLIENT", "timeA@test.com", "Owner A")
    lawyer_id, _headersL = _setup_user(client, "LAWYER", "timeL@test.com", "Lawyer L")
    _ownerB_id, headersB = _setup_user(client, "CLIENT", "timeB@test.com", "Owner B")

    # 1. Create case -> CASE_CREATED
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Timeline Case", "description": "Desc"},
        headers=headersA,
    )
    case_id = res_case.json()["id"]

    # 2. Add lawyer -> PARTICIPANT_ADDED + LAWYER_SELECTED
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=headersA,
    )

    # 3. Upload document -> DOCUMENT_UPLOADED
    client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "doc.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=headersA,
    )

    # Fetch Timeline
    res_time = client.get(f"/api/v1/cases/{case_id}/timeline", headers=headersA)
    assert res_time.status_code == 200

    events = res_time.json()["items"]
    assert len(events) == 4

    # Since it's DESC sort, index 0 is newest (Document)
    assert events[0]["event_type"] == "DOCUMENT_UPLOADED"
    assert "filename" in events[0]["event_metadata"]

    assert events[1]["event_type"] == "LAWYER_SELECTED"
    assert events[1]["event_metadata"]["target_user_id"] == lawyer_id

    assert events[2]["event_type"] == "PARTICIPANT_ADDED"

    assert events[3]["event_type"] == "CASE_CREATED"

    # Ensure BOLA works (Owner B cannot view timeline)
    res_B = client.get(f"/api/v1/cases/{case_id}/timeline", headers=headersB)
    assert res_B.status_code == 404
