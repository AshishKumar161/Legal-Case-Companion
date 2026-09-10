from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.i18n import resolve_locale, translate

router = APIRouter(prefix="/trust", tags=["trust-and-transparency"])


@router.get("/disclosures")
@router.get("/transparency")
def get_trust_and_transparency_disclosures(
    request: Request,
) -> dict[str, Any]:
    """Exposes public legal transparency disclosures cleanly categorizing platform services (Part E, W)."""
    loc = resolve_locale(request)

    return {
        "platform_role": "TECHNOLOGY_INTERMEDIARY",
        "jurisdiction": "INDIA",
        "regulatory_frameworks": [
            "Information Technology Act, 2000 (Intermediary Guidelines)",
            "Digital Personal Data Protection Act, 2023",
            "Advocates Act, 1961 & Bar Council of India Rules",
            "Bharatiya Sakshya Adhiniyam, 2023 (Electronic Evidence Standards)",
        ],
        "service_categorization": {
            "legal_information": {
                "definition": "Public statutes, judicial precedents, court rules, and procedural guides published for general awareness.",
                "binding_status": "INFORMATIONAL_ONLY",
            },
            "legal_assistance": {
                "definition": "Software tools for organizing case chronologies, indexing exhibits, and drafting timelines.",
                "binding_status": "LITIGANT_ASSISTANCE",
            },
            "ai_generated_assistance": {
                "definition": "Grounded statutory summaries and document chunk retrieval. Not legal advice; zero guarantee against misinterpretation.",
                "binding_status": "MACHINE_ASSISTED_RESEARCH",
                "disclaimer": translate("ai.disclaimer", loc),
            },
            "legal_professional_services": {
                "definition": "Direct legal advice, representation, and petition drafting provided exclusively by Bar Council of India verified advocates.",
                "binding_status": "ATTORNEY_CLIENT_PRIVILEGED",
                "advocate_responsibility": "Solely provided by independent enrolled advocates; platform does not solicit or direct client representation.",
            },
        },
        "evidence_integrity_standards": {
            "hashing_algorithm": "SHA-256",
            "storage_security": "Private AWS S3 SSE-S3 with non-guessable storage paths",
            "tamper_detection": "Immediate quarantine and alert on cryptographic hash mismatch",
            "custody_ledger": "Append-only chronological audit log of all access and views",
        },
        "contact_channels": {
            "compliance_officer": "compliance@legalcasecompanion.in",
            "grievance_officer": "grievance.officer@legalcasecompanion.in",
            "security_incident_reporting": "security@legalcasecompanion.in",
        },
    }
