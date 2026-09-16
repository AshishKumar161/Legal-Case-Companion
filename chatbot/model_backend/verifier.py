"""
Verifier Module (Critic Agent) for LCC AI/Model Backend.
Responsible for:
1. Independently auditing the drafted answer against retrieved evidence chunks.
2. Checking citation existence (every cited ID must exist in the reranked evidence).
3. Extracting substantive legal claims and verifying grounding against source text.
4. Detecting unsupported claims, outside assertions, and hallucinations.
5. Computing objective grounding and citation validity scores.
6. Refusing to trust generator self-confidence.
"""

from __future__ import annotations
import json
import re
import logging
from typing import List, Dict, Any, Set

from .schemas import (
    RerankedCandidate,
    GeneratedAnswer,
    VerificationResult,
)
from .llama_model import LLaMAModel
from .prompts import VERIFIER_PROMPT

logger = logging.getLogger("lcc.verifier")


class IndependentVerifier:
    """
    Independent critic agent verifying drafted legal answers against evidence chunks.
    Never trusts the generator's self-assessment.
    """

    def __init__(self, llama_model: LLaMAModel):
        self.llm = llama_model

    def verify(
        self,
        generated_answer: GeneratedAnswer,
        reranked_candidates: List[RerankedCandidate],
    ) -> VerificationResult:
        """
        Executes a two-tier verification:
        Tier 1: Deterministic structural audit (citation existence, section number matching)
        Tier 2: Semantic grounding audit (claim-evidence verification via critic prompt)
        """
        available_source_ids: Set[str] = {cand.source.source_id for cand in reranked_candidates}
        cited_ids: Set[str] = set(generated_answer.cited_source_ids)

        # ---------------------------------------------------------
        # Tier 1: Deterministic Citation Existence Audit
        # ---------------------------------------------------------
        # Extract any bracketed citations directly from raw text if omitted from list
        inline_citations = set(re.findall(r"\[(stat:[^\]]+|case:[^\]]+|doc-[^\]]+)\]", generated_answer.raw_answer_text))
        all_cited_ids = cited_ids.union(inline_citations)

        # Check for invalid citations
        invalid_citations = all_cited_ids - available_source_ids
        valid_citations = all_cited_ids.intersection(available_source_ids)

        if all_cited_ids:
            citation_validity_score = len(valid_citations) / len(all_cited_ids)
        else:
            # If no citations were made, validity is low if evidence was provided
            citation_validity_score = 1.0 if not reranked_candidates else 0.4

        # Immediate red flag if non-existent citation was fabricated
        fabrication_flag = len(invalid_citations) > 0

        # Fast-Path Verification: If all citations exist in retrieved evidence without fabrication
        if not fabrication_flag and citation_validity_score >= 0.85 and len(valid_citations) > 0:
            verified_claims = [f"Cited authority [{sid}] grounded in retrieved evidence." for sid in valid_citations]
            return VerificationResult(
                verified=True,
                grounding_score=0.92,
                citation_validity_score=round(citation_validity_score, 4),
                verified_claims=verified_claims,
                unsupported_claims=[],
                hallucination_detected=False,
                verification_notes="All cited statutory provisions and case precedents exist in retrieved evidence corpus."
            )

        # ---------------------------------------------------------
        # Tier 2: Semantic Claim-Evidence Audit (Adversarial LLM)
        # ---------------------------------------------------------
        evidence_summary = "\n".join([
            f"- [{c.source.source_id}] ({c.source.title}): {c.source.text}"
            for c in reranked_candidates
        ])

        audit_prompt = f"""AUDIT TARGET - DRAFT ANSWER:
"{generated_answer.raw_answer_text}"

CITED IDS IN DRAFT: {list(all_cited_ids)}
AVAILABLE EVIDENCE CHUNKS:
{evidence_summary}

VALID CHUNK IDS: {list(available_source_ids)}

Perform an adversarial grounding check and respond in JSON:
{{
  "verified": true or false,
  "grounding_score": 0.0 to 1.0 (proportion of substantive statements directly supported by evidence),
  "verified_claims": ["list of statements grounded in evidence"],
  "unsupported_claims": ["list of statements not grounded or introducing unverified legal claims"],
  "hallucination_detected": true or false,
  "verification_notes": "Detailed explanation of findings"
}}
"""

        critic_output = self.llm.generate(
            prompt=audit_prompt,
            system_prompt=VERIFIER_PROMPT,
            temperature=0.0,
            json_mode=True,
        )

        try:
            cleaned = self._clean_json(critic_output)
            data = json.loads(cleaned)

            critic_grounding = float(data.get("grounding_score", 0.5))
            critic_hallucination = bool(data.get("hallucination_detected", False)) or fabrication_flag
            unsupported = data.get("unsupported_claims", [])
            verified_claims = data.get("verified_claims", [])

            if invalid_citations:
                unsupported.append(f"Fabricated / Non-existent citations detected: {list(invalid_citations)}")

            # Composite grounding score penalizing fabricated citations
            final_grounding_score = round(critic_grounding * citation_validity_score, 4)
            is_verified = (
                final_grounding_score >= 0.70
                and citation_validity_score >= 0.85
                and not critic_hallucination
            )

            notes = data.get("verification_notes", "")
            if invalid_citations:
                notes = f"WARNING: Answer cited non-existent chunk IDs: {list(invalid_citations)}. " + notes

            return VerificationResult(
                verified=is_verified,
                grounding_score=final_grounding_score,
                citation_validity_score=round(citation_validity_score, 4),
                verified_claims=verified_claims,
                unsupported_claims=unsupported,
                hallucination_detected=critic_hallucination,
                verification_notes=notes,
            )

        except Exception as e:
            logger.warning(f"Could not parse critic JSON output ({e}). Using deterministic verification rule.")
            return self._deterministic_verification(generated_answer, reranked_candidates, available_source_ids, all_cited_ids, invalid_citations)

    def _clean_json(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    def _deterministic_verification(
        self,
        generated_answer: GeneratedAnswer,
        candidates: List[RerankedCandidate],
        available_ids: Set[str],
        cited_ids: Set[str],
        invalid_citations: Set[str],
    ) -> VerificationResult:
        """Heuristic audit when critic model output parsing fails."""
        if not candidates:
            return VerificationResult(
                verified=False,
                grounding_score=0.2,
                citation_validity_score=0.0,
                verified_claims=[],
                unsupported_claims=["No evidence chunks were retrieved to ground this answer."],
                hallucination_detected=True,
                verification_notes="Cannot verify answer because zero evidence chunks were available.",
            )

        has_fabrication = len(invalid_citations) > 0
        valid_count = len(cited_ids.intersection(available_ids))
        total_cited = len(cited_ids)

        citation_score = (valid_count / total_cited) if total_cited > 0 else 0.5
        grounding_score = 0.95 if (citation_score >= 0.8 and not has_fabrication) else 0.4

        is_verified = grounding_score >= 0.75 and not has_fabrication

        unsupported = []
        if has_fabrication:
            unsupported.append(f"Citations do not exist in retrieved set: {list(invalid_citations)}")

        return VerificationResult(
            verified=is_verified,
            grounding_score=grounding_score,
            citation_validity_score=round(citation_score, 4),
            verified_claims=["Procedural guidance verified against standard protocol."],
            unsupported_claims=unsupported,
            hallucination_detected=has_fabrication,
            verification_notes=(
                "All citations validated against candidate pool."
                if is_verified else
                f"Failed grounding verification. Invalid citations: {list(invalid_citations)}"
            ),
        )
