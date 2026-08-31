import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.document import (
    Document,
    DocumentCategory,
    DocumentProcessingStatus,
    DocumentSecurityStatus,
)
from app.models.task import CaseTask, TaskPriority, TaskStatus


def _setup_perf_user(client: TestClient, email: str = "scaling_user@example.com") -> tuple[str, dict[str, str]]:
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "ScalingPassword123!", "role": "CLIENT", "full_name": "Scaling User"},
    )
    user_id = reg_res.json()["id"]
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "ScalingPassword123!"})
    token = login_res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_workspace_aggregation_scaling(client: TestClient, db: Session):
    """Measures Case Workspace aggregation performance with scaling volumes of documents and tasks."""
    user_id, headers = _setup_perf_user(client, "perf_workspace_scaling@example.com")

    # Create Case
    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": "Heavy Case Workspace", "description": "Stress testing workspace aggregation."},
    )
    case_id = case_res.json()["id"]
    case_uuid = uuid.UUID(case_id)
    user_uuid = uuid.UUID(user_id)

    # 1. Bulk seed 30 documents
    docs = [
        Document(
            id=generate_uuid7(),
            case_id=case_uuid,
            uploaded_by=user_uuid,
            filename=f"contract_exhibit_{i}.pdf",
            storage_key=f"cases/{case_id}/docs/{i}.pdf",
            mime_type="application/pdf",
            file_size=1024 * (i + 1),
            security_status=DocumentSecurityStatus.SAFE,
            processing_status=DocumentProcessingStatus.READY,
            document_type=DocumentCategory.EVIDENCE,
            version=1,
        )
        for i in range(30)
    ]
    db.add_all(docs)

    # 2. Bulk seed 20 tasks
    tasks = [
        CaseTask(
            id=generate_uuid7(),
            case_id=case_uuid,
            created_by_user_id=user_uuid,
            title=f"Procedural Task #{i}",
            priority=TaskPriority.MEDIUM,
            status=TaskStatus.PENDING if i % 2 == 0 else TaskStatus.COMPLETED,
        )
        for i in range(20)
    ]
    db.add_all(tasks)
    db.commit()

    # 3. Measure Workspace Aggregation Latency with full dataset
    t0 = time.perf_counter()
    res_ws = client.get(f"/api/v1/cases/{case_id}/workspace", headers=headers)
    lat_ms = (time.perf_counter() - t0) * 1000.0

    assert res_ws.status_code == 200
    ws_data = res_ws.json()
    assert ws_data.get("document_count") >= 30
    assert "tasks_summary" in ws_data
    assert lat_ms < 500.0  # Even with 50+ records, must aggregate in < 500ms
