"""Canonical Mock AI Provider Implementation.

Implements the exact same interface contract as production AI providers.
Allows deterministic testing without live LLM calls, supporting programmatic
scenario injection (e.g., CONFLICT, INSUFFICIENT_EVIDENCE, TIMEOUT, MALFORMED_OUTPUT).
"""

import re
from typing import Any

from app.core.ai_config import AI_CONFIG
from app.providers.ai.base import AIProvider
from app.schemas.ai import AIResearchResponse, Citation
from app.schemas.retrieval import RetrievedChunk


class CanonicalMockAIProvider(AIProvider):
    """Deterministic Mock AI Provider for testing and offline environments.

    Matches production contract and provides fixture controls for testing edge cases.
    """

    def __init__(self, model: str = AI_CONFIG.MOCK_CHAT_MODEL):
        self.provider_name = "mock"
        self.model = model
        self._scenario: str | None = None
        self._canned_response: dict[str, Any] | None = None
        self._error_to_raise: Exception | None = None

    def set_scenario(self, scenario: str | None) -> None:
        """Sets an explicit scenario: e.g. 'CONFLICT', 'INSUFFICIENT_EVIDENCE', 'MALFORMED'."""
        self._canned_response = None
        self._scenario = scenario.upper() if scenario else None

    def set_canned_response(self, response: dict[str, Any] | None) -> None:
        """Directly injects a structured response payload."""
        self._canned_response = response

    def set_error(self, error: Exception | None) -> None:
        """Configures an exception to be raised on the next call (e.g. timeout, rate limit)."""
        self._error_to_raise = error

    def reset(self) -> None:
        """Resets all mock state to defaults."""
        self._scenario = None
        self._canned_response = None
        self._error_to_raise = None

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        if self._error_to_raise:
            err = self._error_to_raise
            self._error_to_raise = None
            raise err
        return f"Mock generation response for prompt: {user_prompt[:50]}"

    def generate_structured_response(
        self,
        system_prompt: str,
        user_prompt: str,
        candidate_chunks: list[Any] | None = None,
        authority_provisions: list[Any] | None = None,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if self._error_to_raise:
            err = self._error_to_raise
            self._error_to_raise = None
            raise err

        if self._canned_response is not None:
            return dict(self._canned_response)

        chunks = candidate_chunks or []
        authorities = authority_provisions or []

        # Check for simulated conflict (via explicit scenario or backward-compatible query/chunk text)
        is_conflict = (
            self._scenario in ("CONFLICT", "CONFLICTING", "CONFLICTING_EVIDENCE")
            or "conflict" in user_prompt.lower()
            or any("conflict" in getattr(c, "content", "").lower() for c in chunks)
        )

        if is_conflict:
            chunk1 = chunks[0] if chunks else None
            chunk2 = chunks[1] if len(chunks) > 1 else chunk1
            citations = []
            if chunk1:
                citations.append({
                    "chunk_id": str(getattr(chunk1, "chunk_id", getattr(chunk1, "id", ""))),
                    "document_id": str(getattr(chunk1, "document_id", "")),
                    "text_snippet": getattr(chunk1, "content", "")[:120],
                })
            if chunk2:
                citations.append({
                    "chunk_id": str(getattr(chunk2, "chunk_id", getattr(chunk2, "id", ""))),
                    "document_id": str(getattr(chunk2, "document_id", "")),
                    "text_snippet": getattr(chunk2, "content", "")[:120],
                })

            return {
                "answer": f"Case documents present conflicting statements: Source '{getattr(chunk1, 'source_filename', 'Doc 1')}' states one position, whereas source '{getattr(chunk2, 'source_filename', 'Doc 2')}' indicates a competing position.",
                "grounding_status": "CONFLICTING_EVIDENCE",
                "citations": citations,
                "authority_citations": [],
                "claims": [
                    {
                        "claim_text": f"Source {getattr(chunk1, 'source_filename', 'Doc 1')} presents an affirmative claim.",
                        "status": "SUPPORTED",
                        "supporting_chunk_ids": [str(getattr(chunk1, "chunk_id", getattr(chunk1, "id", "")))] if chunk1 else [],
                    },
                ],
                "uncertainties": ["Evidentiary discrepancy between case documents."],
                "warnings": ["EVIDENTIARY_CONFLICT_DETECTED"],
            }

        # Explicit scenario checks or fallback when no evidence is retrieved
        if self._scenario == "INSUFFICIENT_EVIDENCE" or (not chunks and not authorities):
            return {
                "answer": "Available case materials and legal authorities do not establish the requested fact or legal conclusion.",
                "grounding_status": "INSUFFICIENT_EVIDENCE",
                "citations": [],
                "authority_citations": [],
                "claims": [
                    {
                        "claim_text": "No evidence was found in case documents or legal authorities to support the inquiry.",
                        "status": "UNSUPPORTED",
                        "supporting_chunk_ids": [],
                        "supporting_authority_ids": [],
                        "explanation": "No matching evidence or legal provisions found.",
                    }
                ],
                "uncertainties": ["Insufficient evidence in authorized case documents and legal authorities."],
                "warnings": ["NO_RELEVANT_EVIDENCE"],
            }

        # Check for relevance / keyword match in mock testing
        stop_words = {
            "what", "is", "the", "in", "of", "and", "to", "for", "a", "an",
            "under", "by", "on", "shall", "be", "this", "that", "it", "with",
            "as", "at", "from", "are", "was", "were", "does", "did", "how",
        }
        question_text = user_prompt.split("LEGAL QUESTION:\n")[-1] if "LEGAL QUESTION:\n" in user_prompt else user_prompt
        q_words = [w for w in re.findall(r"\w+", question_text.lower()) if len(w) > 3 and w not in stop_words]

        has_chunk_match = any(
            any(
                (qw in getattr(c, "content", "").lower() or any(tw.startswith(qw[:5]) or qw.startswith(tw[:5]) for tw in re.findall(r"\w+", getattr(c, "content", "").lower()) if len(tw) >= 5 and len(qw) >= 5))
                for qw in q_words
            )
            for c in chunks
        )
        has_auth_match = any(
            any(
                (qw in f"{getattr(p, 'name', '')} {getattr(p, 'title', '')} {getattr(p, 'content', '')}".lower() or any(tw.startswith(qw[:5]) or qw.startswith(tw[:5]) for tw in re.findall(r"\w+", f"{getattr(p, 'name', '')} {getattr(p, 'title', '')} {getattr(p, 'content', '')}".lower()) if len(tw) >= 5 and len(qw) >= 5))
                for qw in q_words
            )
            for p in authorities
        )

        if q_words and not has_chunk_match and not has_auth_match and self._scenario != "SUPPORTED":
            return {
                "answer": "Available case materials and legal authorities contain insufficient evidence to establish the requested fact or legal conclusion.",
                "grounding_status": "INSUFFICIENT_EVIDENCE",
                "citations": [],
                "authority_citations": [],
                "claims": [],
                "uncertainties": ["No matching evidence or statutory authority found."],
                "warnings": ["NO_RELEVANT_EVIDENCE"],
            }

        # Build case evidence citations
        case_citations = []
        for c in chunks[:2]:
            case_citations.append({
                "chunk_id": str(getattr(c, "chunk_id", getattr(c, "id", ""))),
                "document_id": str(getattr(c, "document_id", "")),
                "text_snippet": getattr(c, "content", "")[:150],
            })

        # Build legal authority citations
        auth_citations = []
        for p in authorities[:2]:
            sec_num = getattr(p, "section_number", "")
            auth_citations.append({
                "canonical_identifier": getattr(p, "canonical_identifier", ""),
                "canonical_provision_id": getattr(p, "canonical_provision_id", ""),
                "act_or_judgment_name": getattr(p, "name", ""),
                "section_or_para": f"Section {sec_num}" if not sec_num.startswith("Para") else sec_num,
                "source_type": getattr(p.source_type, "value", str(getattr(p, "source_type", ""))),
                "authority_level": getattr(p, "authority_level", 1),
                "jurisdiction": getattr(p, "jurisdiction", "Union of India"),
                "effective_from": p.effective_from.isoformat() if getattr(p, "effective_from", None) else None,
                "effective_to": p.effective_to.isoformat() if getattr(p, "effective_to", None) else None,
                "text_snippet": getattr(p, "content", "")[:150],
            })

        # Build claims
        claims = []
        answer_parts = []
        if chunks:
            top_chunk = chunks[0]
            top_content = getattr(top_chunk, "content", "").strip()
            top_filename = getattr(top_chunk, "source_filename", "Document")
            answer_parts.append(f"Based on case materials in {top_filename}: {top_content}.")
            claims.append({
                "claim_text": f"Case document {top_filename} establishes {top_content[:150]}.",
                "status": "SUPPORTED",
                "supporting_chunk_ids": [str(getattr(top_chunk, "chunk_id", getattr(top_chunk, "id", "")))],
                "supporting_authority_ids": [],
            })

        if authorities:
            top_auth = authorities[0]
            top_auth_name = getattr(top_auth, "name", "Statute")
            top_auth_sec = getattr(top_auth, "section_number", "")
            top_auth_content = getattr(top_auth, "content", "").strip()
            answer_parts.append(f"Under statutory authority of {top_auth_name} (Section {top_auth_sec}): {top_auth_content}.")
            claims.append({
                "claim_text": f"Under {top_auth_name} Section {top_auth_sec}, {top_auth_content[:150]}.",
                "status": "SUPPORTED",
                "supporting_chunk_ids": [],
                "supporting_authority_ids": [getattr(top_auth, "canonical_provision_id", "")],
            })

        answer = " ".join(answer_parts) if answer_parts else "Evidence establishes the requested inquiry."

        return {
            "answer": answer,
            "grounding_status": "SUPPORTED",
            "citations": case_citations,
            "authority_citations": auth_citations,
            "claims": claims,
            "uncertainties": [],
            "warnings": [],
        }

    def generate_research_response(
        self,
        system_prompt: str,
        user_query: str,
        chunks: list[RetrievedChunk],
    ) -> AIResearchResponse:
        """Emulates research response generation with predictable fallback behavior."""
        if self._error_to_raise:
            err = self._error_to_raise
            self._error_to_raise = None
            raise err

        if not chunks:
            try:
                from app.core.metrics import metrics_collector
                metrics_collector.record_ai_safety_event("EMPTY_RETRIEVAL_REFUSAL", "0_chunks")
            except Exception:
                pass
            return AIResearchResponse(
                answer="Evidence insufficient. The system cannot reliably answer this point from the available sources.",
                citations=[],
                warnings=["No relevant evidence retrieved."],
            )

        main_chunk = chunks[0]
        answer = f"Based on the available evidence, {main_chunk.content[:200]}"
        cit = Citation(
            chunk_id=main_chunk.chunk_id,
            document_id=main_chunk.document_id,
            text_snippet=main_chunk.content[:100],
            relevance_score=0.95,
        )

        return AIResearchResponse(answer=answer, citations=[cit], warnings=[])

    def health_check(self) -> bool:
        return True
