import re
from uuid import UUID

from app.schemas.assistant import (
    ClaimSourceType,
    ClaimSupportStatus,
    GroundingStatus,
    VerifiedAuthorityCitation,
    VerifiedCitation,
    VerifiedClaim,
)
from app.schemas.legal_authority import RetrievedLegalAuthority
from app.schemas.search import RetrievedEvidence


class ClaimVerificationService:
    """Service to verify factual and legal assertions in LLM-generated legal answers against

    both case-specific evidence and external legal authorities.
    """

    @staticmethod
    def extract_claims_from_answer(answer: str) -> list[str]:
        """Splits answer into discrete factual assertions / sentences for verification."""
        sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
        claims = []
        for s in sentences:
            cleaned = s.strip()
            if (len(cleaned) > 20 and not cleaned.lower().startswith(("based on", "according to", "in summary", "in conclusion"))) or len(cleaned) > 10:
                claims.append(cleaned)
        return claims

    @classmethod
    def verify_claims(
        cls,
        answer: str,
        reported_claims: list[dict],
        verified_citations: list[VerifiedCitation],
        evidence_chunks: list[RetrievedEvidence],
        authority_provisions: list[RetrievedLegalAuthority] | None = None,
        verified_authority_citations: list[VerifiedAuthorityCitation] | None = None,
    ) -> tuple[list[VerifiedClaim], GroundingStatus, list[str]]:
        """Verifies claims against verified case citations, evidence chunks, and authoritative legal provisions.

        Returns (verified_claims, adjusted_grounding_status, uncertainties).
        """
        uncertainties: list[str] = []
        chunk_map = {c.chunk_id: c for c in evidence_chunks}
        auth_map = {p.canonical_provision_id: p for p in (authority_provisions or [])}

        citation_chunk_ids = {cit.chunk_id for cit in verified_citations}
        citation_auth_ids = {ac.canonical_provision_id for ac in (verified_authority_citations or [])}

        verified_claims: list[VerifiedClaim] = []

        # If LLM provided structured claims in its output, process them
        if reported_claims:
            for item in reported_claims:
                claim_text = item.get("claim_text", "").strip()
                if not claim_text:
                    continue

                raw_supp_chunk_ids = item.get("supporting_chunk_ids", [])
                valid_supp_chunk_ids = []
                for cid in raw_supp_chunk_ids:
                    try:
                        u_cid = UUID(str(cid))
                        if u_cid in chunk_map:
                            valid_supp_chunk_ids.append(u_cid)
                    except (ValueError, TypeError):
                        continue

                raw_supp_auth_ids = item.get("supporting_authority_ids", [])
                valid_supp_auth_ids = [str(aid) for aid in raw_supp_auth_ids if str(aid) in auth_map]

                # Determine source type and status
                if valid_supp_chunk_ids and valid_supp_auth_ids:
                    source_type = ClaimSourceType.SYNTHESIS
                    status = ClaimSupportStatus.SUPPORTED
                elif valid_supp_chunk_ids:
                    source_type = ClaimSourceType.CASE_EVIDENCE
                    status = ClaimSupportStatus.SUPPORTED
                elif valid_supp_auth_ids:
                    source_type = ClaimSourceType.LEGAL_AUTHORITY
                    status = ClaimSupportStatus.SUPPORTED
                else:
                    source_type = ClaimSourceType.UNSUPPORTED
                    status = ClaimSupportStatus.UNSUPPORTED
                    uncertainties.append(f"Assertion lacks verifiable evidence or authority: '{claim_text[:60]}...'")

                verified_claims.append(
                    VerifiedClaim(
                        claim_text=claim_text,
                        status=status,
                        source_type=source_type,
                        supporting_chunk_ids=valid_supp_chunk_ids,
                        supporting_authority_ids=valid_supp_auth_ids,
                        explanation=item.get("explanation"),
                    )
                )

        # If LLM did not provide structured claims, extract and verify automatically
        if not verified_claims and answer:
            extracted = cls.extract_claims_from_answer(answer)
            for text in extracted:
                matching_chunks: list[UUID] = []
                matching_authorities: list[str] = []
                words = set(re.findall(r"\b\w{4,}\b", text.lower()))

                # Match against case chunks
                for c in evidence_chunks:
                    c_words = set(re.findall(r"\b\w{4,}\b", c.content.lower()))
                    overlap = len(words.intersection(c_words))
                    if len(words) > 0 and (overlap / len(words) >= 0.35 or overlap >= 3):
                        matching_chunks.append(c.chunk_id)

                # Match against authority provisions
                if authority_provisions:
                    for p in authority_provisions:
                        p_words = set(re.findall(r"\w{4,}", f"{p.name} {p.title} {p.content}".lower()))
                        overlap = len(words.intersection(p_words))
                        if len(words) > 0 and (overlap / len(words) >= 0.35 or overlap >= 3):
                            matching_authorities.append(p.canonical_provision_id)

                if matching_chunks and matching_authorities:
                    source_type = ClaimSourceType.SYNTHESIS
                    status = ClaimSupportStatus.SUPPORTED
                elif matching_chunks:
                    source_type = ClaimSourceType.CASE_EVIDENCE
                    status = ClaimSupportStatus.SUPPORTED
                elif matching_authorities:
                    source_type = ClaimSourceType.LEGAL_AUTHORITY
                    status = ClaimSupportStatus.SUPPORTED
                elif citation_chunk_ids or citation_auth_ids:
                    source_type = ClaimSourceType.UNSUPPORTED
                    status = ClaimSupportStatus.UNCERTAIN
                    uncertainties.append(f"Assertion has unconfirmed direct reference: '{text[:60]}...'")
                else:
                    source_type = ClaimSourceType.UNSUPPORTED
                    status = ClaimSupportStatus.UNSUPPORTED
                    uncertainties.append(f"Assertion is unsupported by case materials or legal authorities: '{text[:60]}...'")

                verified_claims.append(
                    VerifiedClaim(
                        claim_text=text,
                        status=status,
                        source_type=source_type,
                        supporting_chunk_ids=matching_chunks,
                        supporting_authority_ids=matching_authorities,
                        explanation="Verified against case evidence and statutory legal authorities.",
                    )
                )

        # Determine overall grounding status
        has_sources = bool(evidence_chunks or authority_provisions)
        has_citations = bool(verified_citations or (verified_authority_citations or []))

        if not has_sources or not has_citations:
            grounding_status = GroundingStatus.INSUFFICIENT_EVIDENCE
        else:
            unsupported_count = sum(1 for c in verified_claims if c.status == ClaimSupportStatus.UNSUPPORTED)
            if unsupported_count > 0 and len(verified_claims) > 0 and (unsupported_count / len(verified_claims) > 0.5):
                grounding_status = GroundingStatus.UNSUPPORTED
            else:
                grounding_status = GroundingStatus.SUPPORTED

        return verified_claims, grounding_status, uncertainties
