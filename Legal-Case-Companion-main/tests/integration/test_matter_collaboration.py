import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentCategory, DocumentSecurityStatus


def _create_user(client: TestClient, email: str, role: str) -> tuple[str, dict]:
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "role": role,
            "full_name": f"Test {role.capitalize()}",
        },
    )
    user_id = res.json()["id"]
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_matter_collaboration_and_requests_lifecycle(client: TestClient, db: Session):
    # 1. Setup client and lawyer
    client_id, client_headers = _create_user(client, "collab_client@lcc.in", "CLIENT")
    lawyer_id, lawyer_headers = _create_user(client, "collab_lawyer@lcc.in", "LAWYER")
    _intruder_id, intruder_headers = _create_user(client, "collab_intruder@lcc.in", "CLIENT")

    # 2. Client creates case
    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Tata Consumer v. Retail Vendor", "description": "Breach of distribution contract"},
        headers=client_headers,
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 3. Add lawyer as participant
    part_res = client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=client_headers,
    )
    assert part_res.status_code == 200

    # 4. Lawyer sends a general matter message
    msg_res = client.post(
        f"/api/v1/cases/{case_id}/collaboration/messages",
        json={
            "content": "Good morning. I have reviewed the initial intake and need the executed supply agreement.",
            "message_type": "GENERAL",
            "is_counsel_only": False,
        },
        headers=lawyer_headers,
    )
    assert msg_res.status_code == 201
    msg_data = msg_res.json()
    assert msg_data["content"].startswith("Good morning")
    assert msg_data["is_counsel_only"] is False

    # 5. Lawyer creates a counsel-only note/message
    counsel_msg_res = client.post(
        f"/api/v1/cases/{case_id}/collaboration/messages",
        json={
            "content": "Internal note: Potential limitation issue under Article 55 of Limitation Act 1963.",
            "message_type": "FORMAL_NOTICE",
            "is_counsel_only": True,
        },
        headers=lawyer_headers,
    )
    assert counsel_msg_res.status_code == 201

    # 6. Verify client CANNOT see counsel-only messages
    client_msgs = client.get(
        f"/api/v1/cases/{case_id}/collaboration/messages",
        headers=client_headers,
    )
    assert client_msgs.status_code == 200
    msgs = client_msgs.json()
    assert len(msgs) == 1
    assert msgs[0]["is_counsel_only"] is False

    # Lawyer CAN see counsel-only messages
    lawyer_msgs = client.get(
        f"/api/v1/cases/{case_id}/collaboration/messages",
        headers=lawyer_headers,
    )
    assert lawyer_msgs.status_code == 200
    assert len(lawyer_msgs.json()) == 2

    # 7. Intruder (unauthorized user) cannot read or send messages (BOLA / Isolation: returns 404 to obscure existence)
    intruder_msgs = client.get(
        f"/api/v1/cases/{case_id}/collaboration/messages",
        headers=intruder_headers,
    )
    assert intruder_msgs.status_code in (403, 404)

    # 8. Lawyer creates a structured Matter Request for document upload
    req_res = client.post(
        f"/api/v1/cases/{case_id}/collaboration/requests",
        json={
            "title": "Upload Executed 2023 Agreement",
            "description": "Please provide the fully signed and stamped master services agreement.",
            "request_type": "DOCUMENT_UPLOAD",
            "assigned_user_id": client_id,
        },
        headers=lawyer_headers,
    )
    assert req_res.status_code == 201
    request_id = req_res.json()["id"]
    assert req_res.json()["status"] == "PENDING"

    # Verify requests list
    req_list = client.get(
        f"/api/v1/cases/{case_id}/collaboration/requests",
        headers=client_headers,
    )
    assert req_list.status_code == 200
    assert len(req_list.json()) == 1
    assert req_list.json()[0]["title"] == "Upload Executed 2023 Agreement"

    # 9. Client submits document in response to request
    doc = Document(
        id=uuid.uuid4(),
        case_id=uuid.UUID(case_id),
        uploaded_by=uuid.UUID(client_id),
        filename="executed_agreement_2023.pdf",
        storage_key="docs/executed_agreement_2023.pdf",
        mime_type="application/pdf",
        file_size=10240,
        document_type=DocumentCategory.CONTRACT,
        security_status=DocumentSecurityStatus.SAFE,
    )
    db.add(doc)
    db.commit()

    submit_res = client.post(
        f"/api/v1/cases/{case_id}/collaboration/requests/{request_id}/submit",
        json={
            "submitted_document_id": str(doc.id),
            "response_notes": "Attached signed copy bearing the stamp of both parties.",
        },
        headers=client_headers,
    )
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "SUBMITTED"
    assert submit_res.json()["submitted_document_title"] == "executed_agreement_2023.pdf"

    # 10. Lawyer reviews and approves request
    review_res = client.post(
        f"/api/v1/cases/{case_id}/collaboration/requests/{request_id}/review",
        json={
            "review_notes": "Verified signature and seal. Formally admitted into evidence record.",
            "mark_status": "REVIEWED",
        },
        headers=lawyer_headers,
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == "REVIEWED"

    # 11. Verify Detailed Participants directory & Matter Brief
    participants_res = client.get(
        f"/api/v1/cases/{case_id}/collaboration/participants",
        headers=client_headers,
    )
    assert participants_res.status_code == 200
    parts = participants_res.json()
    assert len(parts) >= 2
    roles = [p["participant_role"] for p in parts]
    assert "OWNER" in roles
    assert "LAWYER" in roles

    brief_res = client.get(
        f"/api/v1/cases/{case_id}/collaboration/brief",
        headers=client_headers,
    )
    assert brief_res.status_code == 200
    brief = brief_res.json()
    assert brief["title"] == "Tata Consumer v. Retail Vendor"
    assert brief["participants_count"] >= 2


def test_counsel_only_and_cross_case_bola_isolation(client: TestClient, db: Session):
    # Setup 2 separate clients with their own cases
    _client_a_id, client_a_headers = _create_user(client, "client_a@lcc.in", "CLIENT")
    _client_b_id, client_b_headers = _create_user(client, "client_b@lcc.in", "CLIENT")

    case_a = client.post("/api/v1/cases", json={"title": "Case A", "description": "Matter A"}, headers=client_a_headers).json()["id"]
    case_b = client.post("/api/v1/cases", json={"title": "Case B", "description": "Matter B"}, headers=client_b_headers).json()["id"]
    assert case_b is not None

    # Client A creates a message in Case A
    res_a = client.post(
        f"/api/v1/cases/{case_a}/collaboration/messages",
        json={"content": "Privileged note for Matter A", "message_type": "GENERAL"},
        headers=client_a_headers,
    )
    assert res_a.status_code == 201

    # Client B tries to read Case A messages -> 404 (obscures existence)
    res_b_read = client.get(
        f"/api/v1/cases/{case_a}/collaboration/messages",
        headers=client_b_headers,
    )
    assert res_b_read.status_code in (403, 404)

    # Client B tries to post into Case A -> 404
    res_b_post = client.post(
        f"/api/v1/cases/{case_a}/collaboration/messages",
        json={"content": "Malicious inject", "message_type": "GENERAL"},
        headers=client_b_headers,
    )
    assert res_b_post.status_code in (403, 404)

    # Client B tries to read Case A requests -> 404
    res_b_req = client.get(
        f"/api/v1/cases/{case_a}/collaboration/requests",
        headers=client_b_headers,
    )
    assert res_b_req.status_code in (403, 404)

    # Client B tries to read Case A participants directory -> 404
    res_b_part = client.get(
        f"/api/v1/cases/{case_a}/collaboration/participants",
        headers=client_b_headers,
    )
    assert res_b_part.status_code in (403, 404)


def test_collaboration_pydantic_schema_validation_and_openapi(client: TestClient):
    _client_id, client_headers = _create_user(client, "typed_collab_client@lcc.in", "CLIENT")
    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Schema Validation Case", "description": "Testing Pydantic schema rejection"},
        headers=client_headers,
    )
    case_id = case_res.json()["id"]

    # 1. Message missing required "content" -> 422
    res_no_content = client.post(
        f"/api/v1/cases/{case_id}/collaboration/messages",
        json={"message_type": "GENERAL"},
        headers=client_headers,
    )
    assert res_no_content.status_code == 422

    # 2. Message empty content (min_length=1) -> 422
    res_empty_content = client.post(
        f"/api/v1/cases/{case_id}/collaboration/messages",
        json={"content": ""},
        headers=client_headers,
    )
    assert res_empty_content.status_code == 422

    # 3. Message with extra forbidden fields (extra="forbid") -> 422
    res_extra_field = client.post(
        f"/api/v1/cases/{case_id}/collaboration/messages",
        json={"content": "Valid message", "unrecognized_injection": "attack"},
        headers=client_headers,
    )
    assert res_extra_field.status_code == 422

    # 4. Matter Request missing title -> 422
    res_req_no_title = client.post(
        f"/api/v1/cases/{case_id}/collaboration/requests",
        json={"description": "Missing title field"},
        headers=client_headers,
    )
    assert res_req_no_title.status_code == 422

    # 5. Matter Request invalid request_type -> 422
    res_req_bad_type = client.post(
        f"/api/v1/cases/{case_id}/collaboration/requests",
        json={"title": "Valid Title", "description": "Valid Description", "request_type": "NON_EXISTENT"},
        headers=client_headers,
    )
    assert res_req_bad_type.status_code == 422

    # 6. Verify OpenAPI schema reflects typed models
    openapi_res = client.get("/api/v1/openapi.json")
    assert openapi_res.status_code == 200
    schema = openapi_res.json()
    paths = schema["paths"]

    # Check POST /cases/{case_id}/collaboration/messages
    msg_post_op = paths["/api/v1/cases/{case_id}/collaboration/messages"]["post"]
    assert "CaseMessageCreate" in str(msg_post_op["requestBody"])
    assert "CaseMessageResponse" in str(msg_post_op["responses"]["201"])

    # Check POST /cases/{case_id}/collaboration/requests
    req_post_op = paths["/api/v1/cases/{case_id}/collaboration/requests"]["post"]
    assert "MatterRequestCreate" in str(req_post_op["requestBody"])
    assert "MatterRequestResponse" in str(req_post_op["responses"]["201"])

