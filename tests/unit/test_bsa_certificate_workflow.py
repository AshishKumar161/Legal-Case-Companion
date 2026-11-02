import uuid
from datetime import UTC, datetime
import pypdf
import pytest
from pypdf import PdfReader
import io

from app.domain.cases.bundle_pdf_engine import BundlePdfEngine
from app.schemas.bundle import BSACertificateCreateRequest, BSACertificateResponse


def test_bsa_certificate_data_distinction_and_signatures():
    """
    Verifies that Section 63 BSA Certificate technical compilation distinctly separates:
    1. System-generated technical facts and cryptographic SHA-256 hashes.
    2. Device and record particulars.
    3. Person in charge / management declaration and signatory (Schedule Part A).
    4. Expert examination and signatory (Schedule Part B pursuant to Section 63(4)).
    5. Legal counsel advisory notice.
    """
    now = datetime.now(UTC)
    cert_data = {
        "record_identification": "REC-CASE-9921-ELECTRONIC-EVIDENCE-01",
        "source_device_type": "AWS S3 Private Evidence Storage Vault",
        "source_device_details": "Cloud Storage Node ap-south-1 with immutable SHA-256 integrity verification",
        "lawful_control_statement": "The computer system was in lawful control and ordinary custody of the declarant throughout.",
        "operational_condition_statement": "The computer system operated properly without technical malfunction affecting record integrity.",
        "declarant_name": "Rajesh Kumar",
        "declarant_designation": "Chief Information Security Officer",
        "declarant_organization": "Apex Legal Tech Pvt Ltd",
        "place": "New Delhi",
        "declaration_date": now,
        "hash_value": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "hash_algorithm": "SHA-256",
        "expert_examiner_name": "Dr. A. Verma",
        "expert_examiner_designation": "Forensic Examiner of Electronic Records (Schedule Part B)",
        "expert_examination_details": "Digital forensic examination verified non-tampering of SHA-256 bitstream.",
    }

    pdf_bytes = BundlePdfEngine.create_bsa_certificate_pdf(cert_data)
    assert len(pdf_bytes) > 0

    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == 1
    page_text = reader.pages[0].extract_text()

    # 1. Statutory heading
    assert "STATUTORY CERTIFICATE UNDER SECTION 63(4) & SCHEDULE" in page_text
    assert "BHARATIYA SAKSHYA ADHINIYAM, 2023" in page_text

    # 2. Advisory to seek qualified Indian counsel
    assert "LEGAL COUNSEL ADVISORY" in page_text
    assert "All statutory interpretations and admissibility under BSA Section 63(4) must be reviewed by qualified Indian counsel." in page_text

    # 3. System-generated technical facts
    assert "PART 1: SYSTEM-GENERATED TECHNICAL FACTS" in page_text
    assert "SHA-256" in page_text
    assert cert_data["hash_value"] in page_text

    # 4. Device and storage information
    assert "PART 2: DEVICE & STORAGE RECORD INFORMATION" in page_text
    assert "AWS S3 Private Evidence Storage Vault" in page_text

    # 5. Schedule Part A - Party declaration & signatory
    assert "SCHEDULE -- PART A: PARTY DECLARATION" in page_text
    assert "SIGNATURE: PARTY / PERSON IN CHARGE" in page_text
    assert "Rajesh Kumar" in page_text

    # 6. Schedule Part B - Expert declaration & signatory
    assert "SCHEDULE -- PART B: EXPERT DECLARATION" in page_text
    assert "SIGNATURE: EXPERT" in page_text
    assert "Dr. A. Verma" in page_text


def test_bsa_certificate_requires_human_confirmation():
    """Unverified facts must not be automatically certified without explicit human confirmation."""
    now = datetime.now(UTC)
    
    # Must fail validation if is_confirmed is not explicitly provided as boolean True
    with pytest.raises(Exception):
        BSACertificateCreateRequest(
            record_identification="REC-01",
            source_device_type="Server",
            source_device_details="Details",
            lawful_control_statement="Lawful control",
            operational_condition_statement="Operational",
            declarant_name="Declarant",
            declarant_designation="Manager",
            place="Mumbai",
            declaration_date=now,
            # Missing is_confirmed
        )

    # Valid confirmed request
    req = BSACertificateCreateRequest(
        record_identification="REC-01",
        source_device_type="Server",
        source_device_details="Details",
        lawful_control_statement="Lawful control",
        operational_condition_statement="Operational",
        declarant_name="Declarant",
        declarant_designation="Manager",
        place="Mumbai",
        declaration_date=now,
        is_confirmed=True,
    )
    assert req.is_confirmed is True


def test_bsa_certificate_response_includes_legal_counsel_advisory():
    """Response schema must proactively provide qualified legal counsel advisory."""
    cert_resp = BSACertificateResponse(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        bundle_id=uuid.uuid4(),
        record_identification="REC-01",
        source_device_type="Cloud Storage",
        lawful_control_statement="Lawful control statement",
        operational_condition_statement="Operational statement",
        hash_value="abc123hash",
        hash_algorithm="SHA-256",
        declarant_name="Declarant",
        declarant_designation="CISO",
        place="Delhi",
        declaration_date=datetime.now(UTC),
        is_confirmed=True,
        status="PREPARED_DRAFT",
        created_by_user_id=uuid.uuid4(),
        created_at=datetime.now(UTC),
    )
    assert "qualified Indian legal counsel" in cert_resp.legal_counsel_advisory
