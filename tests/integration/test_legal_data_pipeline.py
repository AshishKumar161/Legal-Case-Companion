import datetime
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.models.job import BackgroundJob, JobStatus, JobType
from app.models.legal_authority import (
    AuthorityLevel,
    LegalAuthorityType,
    LegalJurisdiction,
    LegalSource,
    LegalSourceVersion,
)
from app.models.user import User, UserRole
from app.domain.jobs.job_worker import JobWorker
from app.domain.ai.legal_data_pipeline import LegalDataPipeline
from app.domain.ai.legal_source_providers.curated_fixtures import (
    CuratedFixtureSourceProvider,
)


@pytest.fixture(autouse=True)
def mock_openai_api_key():
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "dummy-test-key"
    yield
    settings.OPENAI_API_KEY = original_key


def _setup_admin(client: TestClient, db: Session, email: str = "admin_pipeline@test.com"):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": "CLIENT", "full_name": "Admin Pipeline"},
    )
    user = db.query(User).filter(User.email == email).first()
    user.role = UserRole.ADMIN
    db.commit()

    res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res.json()["access_token"]
    return user.id, {"Authorization": f"Bearer {token}"}


def _setup_client(client: TestClient, email: str = "client_pipeline@test.com"):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": "CLIENT", "full_name": "Client User"},
    )
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_raw_source_ingestion_and_checksum_idempotency(db: Session):
    """Verifies raw source ingestion, SHA-256 calculation, and idempotent deduplication."""
    pipeline = LegalDataPipeline(db)
    provider = CuratedFixtureSourceProvider()
    payload = provider.fetch_source("IN-ACT-1881-26")

    # 1. First Ingestion
    raw1 = pipeline.ingest_raw_payload(payload)
    db.commit()
    assert raw1.id is not None
    assert raw1.content_checksum == payload.content_checksum
    assert raw1.status == "RAW_INGESTED"

    # 2. Second Ingestion with identical content -> returns same record
    raw2 = pipeline.ingest_raw_payload(payload)
    db.commit()
    assert raw2.id == raw1.id
    assert raw2.content_checksum == raw1.content_checksum

    # 3. Process Raw Record -> Canonical LegalSource
    source = pipeline.process_raw_source(raw1.id)
    assert source.canonical_identifier == "IN-ACT-1881-26"
    assert len(source.versions) >= 4

    # 4. Verify Raw Record status updated to INDEXED
    db.refresh(raw1)
    assert raw1.status == "INDEXED"
    assert raw1.canonical_source_id == source.id


def test_sync_curated_fixtures_and_temporal_amendments(db: Session):
    """Verifies full sync of standard Indian legal fixtures and temporal amendment separation."""
    pipeline = LegalDataPipeline(db)
    sync_res = pipeline.sync_curated_fixtures()
    assert sync_res["status"] == "SUCCESS"
    assert sync_res["total_fixtures"] >= 5

    # Verify Negotiable Instruments Act Section 138 versions
    ni_source = db.query(LegalSource).filter(LegalSource.canonical_identifier == "IN-ACT-1881-26").first()
    assert ni_source is not None
    assert ni_source.name == "The Negotiable Instruments Act, 1881"

    v_current = (
        db.query(LegalSourceVersion)
        .filter(
            LegalSourceVersion.source_id == ni_source.id,
            LegalSourceVersion.section_number == "138",
            LegalSourceVersion.is_current.is_(True),
        )
        .first()
    )
    assert v_current is not None
    assert "two years" in v_current.content
    assert v_current.effective_from == datetime.date(2018, 9, 1)

    v_historical = (
        db.query(LegalSourceVersion)
        .filter(
            LegalSourceVersion.source_id == ni_source.id,
            LegalSourceVersion.section_number == "138",
            LegalSourceVersion.is_current.is_(False),
        )
        .first()
    )
    assert v_historical is not None
    assert "one year" in v_historical.content
    assert v_historical.effective_to == datetime.date(2018, 8, 31)


def test_judicial_precedent_ingestion(db: Session):
    """Verifies ingestion and structure of Supreme Court judgments."""
    pipeline = LegalDataPipeline(db)
    provider = CuratedFixtureSourceProvider()
    payload = provider.fetch_source("IN-SC-2020-VIDYA-DROLIA")

    raw = pipeline.ingest_raw_payload(payload)
    source = pipeline.process_raw_source(raw.id)

    assert source.canonical_identifier == "IN-SC-2020-VIDYA-DROLIA"
    assert source.source_type == LegalAuthorityType.JUDICIAL_DECISION
    assert source.authority_level == AuthorityLevel.APEX_JUDICIAL.value
    assert source.jurisdiction == LegalJurisdiction.SUPREME_COURT_OF_INDIA.value

    holding = source.versions[0]
    assert "non-arbitrability" in holding.title.lower() or "arbitrable" in holding.content.lower()


def test_reindex_legal_source(db: Session):
    """Verifies vector re-indexing on existing legal source versions."""
    pipeline = LegalDataPipeline(db)
    provider = CuratedFixtureSourceProvider()
    payload = provider.fetch_source("IN-ACT-1996-26")
    raw = pipeline.ingest_raw_payload(payload)
    source = pipeline.process_raw_source(raw.id)

    # Reindex
    reindexed_count = pipeline.reindex_source(source.id)
    assert reindexed_count >= 3


def test_admin_api_endpoints_and_rbac(client: TestClient, db: Session):
    """Verifies admin REST endpoints for legal data operations and RBAC protection."""
    _admin_id, h_admin = _setup_admin(client, db, "admin_legal_api@test.com")
    h_client = _setup_client(client, "client_legal_api@test.com")

    # 1. Non-admin blocked
    res_client = client.post("/api/v1/admin/legal-sources/sync-fixtures", headers=h_client)
    assert res_client.status_code == 403

    # 2. Admin sync fixtures
    res_admin = client.post("/api/v1/admin/legal-sources/sync-fixtures", headers=h_admin)
    assert res_admin.status_code == 200
    assert res_admin.json()["status"] == "SUCCESS"

    # 3. Admin import raw payload
    raw_payload_data = {
        "source_system": "TEST_ADMIN_IMPORT",
        "external_identifier": "IN-TEST-ACT-2026",
        "source_type": "PRIMARY_LEGISLATION",
        "raw_content": json.dumps(
            {
                "canonical_identifier": "IN-TEST-ACT-2026",
                "name": "The Legal Tech Test Act, 2026",
                "year": 2026,
                "provisions": [
                    {
                        "canonical_provision_id": "IN-TEST-ACT-2026-SEC-1",
                        "section_number": "1",
                        "title": "Short title and commencement",
                        "content": "This Act may be called the Legal Tech Test Act, 2026.",
                        "is_current": True,
                    }
                ],
            }
        ),
    }

    res_import = client.post("/api/v1/admin/legal-sources/import-raw", json=raw_payload_data, headers=h_admin)
    assert res_import.status_code == 201
    imported_data = res_import.json()
    assert imported_data["canonical_identifier"] == "IN-TEST-ACT-2026"
    assert imported_data["status"] == "INDEXED"

    # 4. Admin reindex
    source_id = imported_data["source_id"]
    res_reindex = client.post(f"/api/v1/admin/legal-sources/{source_id}/reindex", headers=h_admin)
    assert res_reindex.status_code == 200
    assert res_reindex.json()["reindexed_count"] == 1


def test_background_worker_legal_authority_job_execution(db: Session):
    """Verifies that background worker processes LEGAL_AUTHORITY_INGESTION and LEGAL_AUTHORITY_REINDEX jobs."""
    pipeline = LegalDataPipeline(db)
    provider = CuratedFixtureSourceProvider()
    payload = provider.fetch_source("IN-CONST-1950")
    raw = pipeline.ingest_raw_payload(payload)
    db.commit()

    # Create BackgroundJob for ingestion
    job_ingest = BackgroundJob(
        id=generate_uuid7(),
        job_type=JobType.LEGAL_AUTHORITY_INGESTION,
        payload={"raw_source_id": str(raw.id)},
        status=JobStatus.PENDING,
    )
    db.add(job_ingest)
    db.commit()

    worker = JobWorker(db, worker_id="test-legal-worker")
    executed_job = worker.execute_job(job_ingest.id)
    assert executed_job.status == JobStatus.SUCCEEDED
    assert executed_job.result_metadata["canonical_identifier"] == "IN-CONST-1950"

    source_id = executed_job.result_metadata["source_id"]

    # Create BackgroundJob for reindex
    job_reindex = BackgroundJob(
        id=generate_uuid7(),
        job_type=JobType.LEGAL_AUTHORITY_REINDEX,
        payload={"source_id": source_id},
        status=JobStatus.PENDING,
    )
    db.add(job_reindex)
    db.commit()

    executed_reindex = worker.execute_job(job_reindex.id)
    assert executed_reindex.status == JobStatus.SUCCEEDED
    assert executed_reindex.result_metadata["reindexed_count"] >= 3
