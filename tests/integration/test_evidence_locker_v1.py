import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.core.storage import get_storage_provider
from app.models.case import Case, CaseParticipant, CaseTimelineEvent, ParticipantRole, ParticipantStatus
from app.models.evidence import (
    CaseExhibit,
    Evidence,
    EvidenceCategory,
    EvidenceCustodyAction,
    EvidenceCustodyEvent,
    EvidenceStatus,
)
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.models.workflow import CaseHearing, HearingSourceType, HearingStatus

VALID_PDF_BYTES = (
    b"%PDF-1.5\n%Valid forensic document container\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
)
VALID_PDF_BYTES_V2 = (
    b"%PDF-1.5\n%Valid forensic document version 2\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
)


def _create_user(
    db: Session,
    prefix: str,
    role: UserRole,
    password: str = "SecurePass123!",
) -> tuple[User, str]:
    uid = uuid.uuid4().hex[:6]
    user = User(
        email=f"{prefix}_{uid}@example.com",
        password_hash=hash_password(password),
        role=role,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    if role == UserRole.CLIENT:
        profile = ClientProfile(user_id=user.id, full_name=f"Client {prefix.capitalize()}")
        db.add(profile)
    elif role == UserRole.LAWYER:
        profile = LawyerProfile(
            user_id=user.id,
            full_name=f"Advocate {prefix.capitalize()}",
            practice_areas=["Commercial Law"],
            court_jurisdictions=["Delhi High Court"],
            languages=["English"],
            experience_years=8,
            consultation_fee=2000.0,
        )
        db.add(profile)
        db.flush()
        verif = LawyerVerification(
            lawyer_profile_id=profile.id,
            enrollment_number=f"D/{uuid.uuid4().hex[:4].upper()}/2021",
            state_bar_council="Bar Council of Delhi",
            status=VerificationStatus.APPROVED,
        )
        db.add(verif)

    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id), user.role.value)
    return user, token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_case(db: Session, owner: User) -> Case:
    case = Case(
        title="Commercial Property Dispute",
        description="High-value lease breach and tenant dispute litigation.",
    )
    db.add(case)
    db.flush()
    participant = CaseParticipant(
        case_id=case.id,
        user_id=owner.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(participant)
    db.commit()
    db.refresh(case)
    return case


def _upload_and_activate_evidence(
    client: TestClient,
    token: str,
    case_id: uuid.UUID,
    title: str = "Lease Agreement 2026",
    filename: str = "lease_agreement.pdf",
    category: str = "CONTRACTUAL",
    tags: list[str] | None = None,
    content_bytes: bytes = VALID_PDF_BYTES,
) -> tuple[str, str]:
    """Helper to deposit and activate an evidence item."""
    init_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/upload-init",
        json={
            "title": title,
            "original_filename": filename,
            "content_type": "application/pdf",
            "size_bytes": len(content_bytes),
            "category": category,
            "tags": tags or [],
        },
        headers=_auth_headers(token),
    )
    assert init_res.status_code == 201, init_res.text
    init_data = init_res.json()
    evidence_id = init_data["evidence_id"]
    version_id = init_data["version_id"]

    # Store bytes in mock storage
    storage = get_storage_provider()
    storage.put_object_bytes(init_data["storage_key"], content_bytes, "application/pdf")

    # Complete upload
    comp_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/complete",
        json={"version_id": version_id},
        headers=_auth_headers(token),
    )
    assert comp_res.status_code == 200, comp_res.text
    return evidence_id, version_id


class TestEvidenceLockerV1:
    """Production test suite for Evidence Locker V1: Exhibit Management, Case Timeline Integration,

    Batch Operations, Lifecycle (Archive/Restore), Server-Side Search, and Tagging.
    """

    def test_exhibit_creation_deterministic_numbering(self, client: TestClient, db: Session):
        """Tests sequential letter exhibit numbering (Exhibit A, Exhibit B), custom exhibit numbers,

        and collision prevention.
        """
        owner, token = _create_user(db, "exhibit_owner", UserRole.CLIENT)
        case = _create_case(db, owner)
        evidence_id, version_id = _upload_and_activate_evidence(
            client, token, case.id, title="Deed of Sale", filename="deed.pdf"
        )

        # 1. First exhibit: auto-allocation should produce "Exhibit A"
        res1 = client.post(
            f"/api/v1/cases/{case.id}/evidence/{evidence_id}/exhibits",
            json={"title": "Primary Sale Deed"},
            headers=_auth_headers(token),
        )
        assert res1.status_code == 201, res1.text
        data1 = res1.json()
        assert data1["exhibit_number"] == "Exhibit A"
        assert data1["evidence_id"] == evidence_id
        assert data1["version_id"] == version_id

        # 2. Second exhibit: auto-allocation should produce "Exhibit B"
        res2 = client.post(
            f"/api/v1/cases/{case.id}/evidence/{evidence_id}/exhibits",
            json={"title": "Schedule of Property Annexure"},
            headers=_auth_headers(token),
        )
        assert res2.status_code == 201, res2.text
        data2 = res2.json()
        assert data2["exhibit_number"] == "Exhibit B"

        # 3. Third exhibit: explicit custom number
        res3 = client.post(
            f"/api/v1/cases/{case.id}/evidence/{evidence_id}/exhibits",
            json={"title": "Petitioner Exhibit 1", "exhibit_number": "Exhibit P-1"},
            headers=_auth_headers(token),
        )
        assert res3.status_code == 201, res3.text
        data3 = res3.json()
        assert data3["exhibit_number"] == "Exhibit P-1"

        # 4. Duplicate collision attempt: attempting to allocate "Exhibit A" again must be rejected
        res_dup = client.post(
            f"/api/v1/cases/{case.id}/evidence/{evidence_id}/exhibits",
            json={"title": "Duplicate Deed", "exhibit_number": "Exhibit A"},
            headers=_auth_headers(token),
        )
        assert res_dup.status_code == 422
        assert "already in use" in res_dup.json()["error"]["message"]

        # 5. List exhibits for this evidence item
        res_list = client.get(
            f"/api/v1/cases/{case.id}/evidence/{evidence_id}/exhibits",
            headers=_auth_headers(token),
        )
        assert res_list.status_code == 200
        exhibits = res_list.json()
        assert len(exhibits) == 3
        numbers = [e["exhibit_number"] for e in exhibits]
        assert "Exhibit A" in numbers
        assert "Exhibit B" in numbers
        assert "Exhibit P-1" in numbers

    def test_exhibit_version_awareness(self, client: TestClient, db: Session):
        """Verifies that an exhibit explicitly references a specific evidence version,

        and subsequent version deposits do not silently mutate historical exhibit references.
        """
        owner, token = _create_user(db, "ver_owner", UserRole.CLIENT)
        case = _create_case(db, owner)
        evidence_id, v1_id = _upload_and_activate_evidence(
            client, token, case.id, title="Executed Contract", filename="contract_v1.pdf"
        )

        # Mark Exhibit A referencing Version 1
        res_ex = client.post(
            f"/api/v1/cases/{case.id}/evidence/{evidence_id}/exhibits",
            json={"title": "Executed Contract Exhibit", "version_id": v1_id},
            headers=_auth_headers(token),
        )
        assert res_ex.status_code == 201
        ex_id = res_ex.json()["id"]

        # Deposit Version 2 of the same evidence item
        v2_init = client.post(
            f"/api/v1/cases/{case.id}/evidence/{evidence_id}/versions/upload-init",
            json={
                "original_filename": "contract_v2_addendum.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(VALID_PDF_BYTES_V2),
            },
            headers=_auth_headers(token),
        )
        assert v2_init.status_code == 201
        v2_data = v2_init.json()
        v2_id = v2_data["version_id"]

        # Upload v2 bytes and complete
        storage = get_storage_provider()
        storage.put_object_bytes(v2_data["storage_key"], VALID_PDF_BYTES_V2, "application/pdf")
        comp_v2 = client.post(
            f"/api/v1/cases/{case.id}/evidence/{evidence_id}/versions/{v2_id}/complete",
            json={},
            headers=_auth_headers(token),
        )
        assert comp_v2.status_code == 200

        # Query Exhibit A: must still point to Version 1, not Version 2!
        get_ex = client.get(
            f"/api/v1/cases/{case.id}/exhibits/{ex_id}",
            headers=_auth_headers(token),
        )
        assert get_ex.status_code == 200
        ex_data = get_ex.json()
        assert ex_data["version_id"] == v1_id
        assert ex_data["version_number"] == 1
        assert "contract_v1.pdf" in ex_data["original_filename"]

    def test_exhibit_hearing_linking_and_case_timeline(self, client: TestClient, db: Session):
        """Tests linking an exhibit to a court hearing and verifies automatic CaseTimelineEvent emission."""
        owner, token = _create_user(db, "timeline_owner", UserRole.CLIENT)
        case = _create_case(db, owner)
        evidence_id, _ = _upload_and_activate_evidence(
            client, token, case.id, title="Forensic Report", filename="forensic.pdf"
        )

        # Create a Court Hearing for the case
        hearing = CaseHearing(
            case_id=case.id,
            court_name="Delhi High Court, Courtroom 4",
            hearing_at=datetime(2026, 9, 18, 10, 30, tzinfo=UTC),
            purpose="Cross Examination of Expert Witness",
            status=HearingStatus.SCHEDULED,
            source_type=HearingSourceType.MANUAL,
            created_by_user_id=owner.id,
        )
        db.add(hearing)
        db.commit()
        db.refresh(hearing)

        # Mark exhibit linked to the hearing
        res = client.post(
            f"/api/v1/cases/{case.id}/evidence/{evidence_id}/exhibits",
            json={
                "title": "Forensic Hard Disk Image Report",
                "hearing_id": str(hearing.id),
                "relevant_date": "2026-09-18T10:30:00Z",
            },
            headers=_auth_headers(token),
        )
        assert res.status_code == 201
        ex_data = res.json()
        assert ex_data["hearing_id"] == str(hearing.id)
        assert ex_data["hearing_purpose"] == "Cross Examination of Expert Witness"

        # Verify Case Timeline Event was generated
        timeline_events = (
            db.query(CaseTimelineEvent)
            .filter(
                CaseTimelineEvent.case_id == case.id,
                CaseTimelineEvent.event_type == "EXHIBIT_MARKED",
            )
            .all()
        )
        assert len(timeline_events) >= 1
        last_event = timeline_events[-1]
        assert "Exhibit A" in last_event.description
        assert "Forensic Hard Disk Image Report" in last_event.description
        assert last_event.event_metadata["hearing_id"] == str(hearing.id)

        # Verify case exhibits query by hearing_id filter
        hearing_exhibits = client.get(
            f"/api/v1/cases/{case.id}/exhibits?hearing_id={hearing.id}",
            headers=_auth_headers(token),
        )
        assert hearing_exhibits.status_code == 200
        assert len(hearing_exhibits.json()) == 1
        assert hearing_exhibits.json()[0]["exhibit_number"] == "Exhibit A"

    def test_batch_operations_atomic_authorization_and_isolation(self, client: TestClient, db: Session):
        """Tests batch operations (category assignment, tag update, archive, restore)

        and ensures fail-closed rejection when any resource ID belongs to another case.
        """
        owner, token = _create_user(db, "batch_owner", UserRole.CLIENT)
        case_a = _create_case(db, owner)
        case_b = _create_case(db, owner)

        # Deposit 3 items in Case A
        ev1, _ = _upload_and_activate_evidence(client, token, case_a.id, title="Invoice 1", filename="inv1.pdf")
        ev2, _ = _upload_and_activate_evidence(client, token, case_a.id, title="Invoice 2", filename="inv2.pdf")
        ev3, _ = _upload_and_activate_evidence(client, token, case_a.id, title="Invoice 3", filename="inv3.pdf")

        # Deposit 1 item in Case B (unrelated case)
        foreign_ev, _ = _upload_and_activate_evidence(
            client, token, case_b.id, title="Foreign Contract", filename="contract.pdf"
        )

        # 1. Valid Batch: Assign category FINANCIAL to all 3 items in Case A
        batch_res = client.post(
            f"/api/v1/cases/{case_a.id}/evidence/batch",
            json={
                "action": "ASSIGN_CATEGORY",
                "evidence_ids": [ev1, ev2, ev3],
                "category": "FINANCIAL",
            },
            headers=_auth_headers(token),
        )
        assert batch_res.status_code == 200, batch_res.text
        assert batch_res.json()["affected_count"] == 3

        # Verify category update on DB
        for eid in [ev1, ev2, ev3]:
            item = db.query(Evidence).filter(Evidence.id == uuid.UUID(eid)).first()
            assert item.category == EvidenceCategory.FINANCIAL

        # 2. Valid Batch: Add tags
        tag_res = client.post(
            f"/api/v1/cases/{case_a.id}/evidence/batch",
            json={
                "action": "ADD_TAGS",
                "evidence_ids": [ev1, ev2],
                "tags": ["tax-audit-2026", "q1-expenses"],
            },
            headers=_auth_headers(token),
        )
        assert tag_res.status_code == 200
        item1 = db.query(Evidence).filter(Evidence.id == uuid.UUID(ev1)).first()
        assert "tax-audit-2026" in item1.tags
        assert "q1-expenses" in item1.tags

        # 3. Security Boundary Test: Construct mixed batch containing 2 valid IDs + 1 foreign ID from Case B
        # Must fail closed with 404 existence-masking, preventing cross-tenant information leakage or partial mutations!
        mixed_batch = client.post(
            f"/api/v1/cases/{case_a.id}/evidence/batch",
            json={
                "action": "ARCHIVE",
                "evidence_ids": [ev1, ev2, foreign_ev],
            },
            headers=_auth_headers(token),
        )
        assert mixed_batch.status_code == 404

        # Verify that NO items were archived (atomic rollback)
        item1_check = db.query(Evidence).filter(Evidence.id == uuid.UUID(ev1)).first()
        assert item1_check.status == EvidenceStatus.ACTIVE

    def test_archive_restore_and_legal_hold_blocking(self, client: TestClient, db: Session):
        """Tests evidence archiving, restoration, and verifies that technical legal hold blocks archive."""
        owner, token = _create_user(db, "archive_owner", UserRole.CLIENT)
        case = _create_case(db, owner)
        ev_id, _ = _upload_and_activate_evidence(client, token, case.id, title="Settlement Agreement")

        # 1. Archive active evidence item
        arch_res = client.post(
            f"/api/v1/cases/{case.id}/evidence/{ev_id}/archive",
            headers=_auth_headers(token),
        )
        assert arch_res.status_code == 200
        assert arch_res.json()["status"] == "ARCHIVED"

        # Verify custody ledger recorded ARCHIVED action
        custody_event = (
            db.query(EvidenceCustodyEvent)
            .filter(
                EvidenceCustodyEvent.evidence_id == uuid.UUID(ev_id),
                EvidenceCustodyEvent.action == EvidenceCustodyAction.ARCHIVED,
            )
            .first()
        )
        assert custody_event is not None

        # 2. Restore archived item
        rest_res = client.post(
            f"/api/v1/cases/{case.id}/evidence/{ev_id}/restore",
            headers=_auth_headers(token),
        )
        assert rest_res.status_code == 200
        assert rest_res.json()["status"] == "ACTIVE"

        # 3. Apply technical Legal Hold
        hold_res = client.post(
            f"/api/v1/cases/{case.id}/evidence/{ev_id}/legal-hold",
            json={"legal_hold": True, "reason": "Section 65B Bharatiya Sakshya Adhiniyam hold"},
            headers=_auth_headers(token),
        )
        assert hold_res.status_code == 200
        assert hold_res.json()["legal_hold"] is True

        # 4. Attempt to archive an item under active legal hold -> must be blocked with HTTP 403
        blocked_arch = client.post(
            f"/api/v1/cases/{case.id}/evidence/{ev_id}/archive",
            headers=_auth_headers(token),
        )
        assert blocked_arch.status_code == 403
        assert "legal hold" in blocked_arch.json()["error"]["message"].lower()

    def test_server_side_metadata_search_and_tag_filtering(self, client: TestClient, db: Session):
        """Tests bounded server-side search across title, filename, tags, and exhibit presence."""
        owner, token = _create_user(db, "search_owner", UserRole.CLIENT)
        case = _create_case(db, owner)

        # Deposit item 1
        ev1, _ = _upload_and_activate_evidence(
            client,
            token,
            case.id,
            title="Shareholder Purchase Agreement",
            filename="shareholder_spa_final.pdf",
            category="CONTRACTUAL",
            tags=["merger", "corporate", "shareholder"],
        )

        # Deposit item 2
        ev2, _ = _upload_and_activate_evidence(
            client,
            token,
            case.id,
            title="Forensic Memory Dump",
            filename="ram_dump.raw.pdf",
            category="FORENSIC",
            tags=["forensic", "digital-evidence", "cyber"],
        )

        # Deposit item 3 and mark as exhibit
        ev3, _ = _upload_and_activate_evidence(
            client,
            token,
            case.id,
            title="Promissory Note",
            filename="promissory_note.pdf",
            category="FINANCIAL",
            tags=["promissory", "debt"],
        )
        client.post(
            f"/api/v1/cases/{case.id}/evidence/{ev3}/exhibits",
            json={"title": "Original Promissory Note"},
            headers=_auth_headers(token),
        )

        # 1. Search by title substring: "shareholder"
        search1 = client.get(
            f"/api/v1/cases/{case.id}/evidence?q=shareholder",
            headers=_auth_headers(token),
        )
        assert search1.status_code == 200
        res1 = search1.json()
        assert len(res1) == 1
        assert res1[0]["id"] == ev1

        # 2. Filter by tag: "cyber"
        search2 = client.get(
            f"/api/v1/cases/{case.id}/evidence?tag=cyber",
            headers=_auth_headers(token),
        )
        assert search2.status_code == 200
        res2 = search2.json()
        assert len(res2) == 1
        assert res2[0]["id"] == ev2

        # 3. Filter by exhibits: is_exhibit=true
        search3 = client.get(
            f"/api/v1/cases/{case.id}/evidence?is_exhibit=true",
            headers=_auth_headers(token),
        )
        assert search3.status_code == 200
        res3 = search3.json()
        assert len(res3) == 1
        assert res3[0]["id"] == ev3
        assert "Exhibit A" in res3[0]["exhibit_numbers"]

    def test_concurrent_exhibit_allocations(self, client: TestClient, db: Session):
        """Simulates rapid consecutive exhibit allocations to verify strictly unique sequential numbering and collision handling."""
        owner, token = _create_user(db, "seq_owner", UserRole.CLIENT)
        case = _create_case(db, owner)
        ev_id, _ = _upload_and_activate_evidence(client, token, case.id, title="Test Deed")

        exhibit_numbers = []
        for i in range(5):
            res = client.post(
                f"/api/v1/cases/{case.id}/evidence/{ev_id}/exhibits",
                json={"title": f"Exhibit Index {i}"},
                headers=_auth_headers(token),
            )
            assert res.status_code == 201
            exhibit_numbers.append(res.json()["exhibit_number"])

        assert exhibit_numbers == [
            "Exhibit A",
            "Exhibit B",
            "Exhibit C",
            "Exhibit D",
            "Exhibit E",
        ], "Allocations must be strictly sequential, deterministic, and unique"

        # Explicit collision test: attempting to create an exhibit with an already allocated number raises 422
        col_res = client.post(
            f"/api/v1/cases/{case.id}/evidence/{ev_id}/exhibits",
            json={"title": "Colliding Exhibit", "exhibit_number": "Exhibit B"},
            headers=_auth_headers(token),
        )
        assert col_res.status_code == 422
        assert "already in use" in col_res.json()["error"]["message"]

