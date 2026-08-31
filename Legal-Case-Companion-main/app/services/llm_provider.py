import json
import logging
import re
import time
from typing import Any, Protocol

import openai

from app.core.config import settings
from app.core.exceptions import AppException
from app.schemas.legal_authority import RetrievedLegalAuthority
from app.schemas.search import RetrievedEvidence

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    """Protocol defining the LLM provider interface for structured legal response generation."""

    model: str

    def generate_structured_response(
        self,
        system_prompt: str,
        user_prompt: str,
        candidate_chunks: list[RetrievedEvidence] | None = None,
        authority_provisions: list[RetrievedLegalAuthority] | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]: ...


class MockLLMProvider:
    """Deterministic Mock LLM Provider for offline development and test suites."""

    model: str = "mock-gpt-4o"

    def generate_structured_response(
        self,
        system_prompt: str,
        user_prompt: str,
        candidate_chunks: list[RetrievedEvidence] | None = None,
        authority_provisions: list[RetrievedLegalAuthority] | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        chunks = candidate_chunks or []
        authorities = authority_provisions or []

        if not chunks and not authorities:
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

        # Check if the candidate chunks or authorities actually contain topical keywords matching the question
        stop_words = {
            "what", "is", "the", "in", "of", "and", "to", "for", "a", "an",
            "under", "by", "on", "shall", "be", "this", "that", "it", "with",
            "as", "at", "from", "are", "was", "were", "does", "did", "how",
        }
        question_text = user_prompt.split("LEGAL QUESTION:\n")[-1] if "LEGAL QUESTION:\n" in user_prompt else user_prompt
        q_words = [w for w in re.findall(r"\w+", question_text.lower()) if len(w) > 3 and w not in stop_words]

        has_chunk_match = any(
            any(
                (qw in c.content.lower() or any(tw.startswith(qw[:5]) or qw.startswith(tw[:5]) for tw in re.findall(r"\w+", c.content.lower()) if len(tw) >= 5 and len(qw) >= 5))
                for qw in q_words
            )
            for c in chunks
        )
        has_auth_match = any(
            any(
                (qw in f"{p.name} {p.title} {p.content}".lower() or any(tw.startswith(qw[:5]) or qw.startswith(tw[:5]) for tw in re.findall(r"\w+", f"{p.name} {p.title} {p.content}".lower()) if len(tw) >= 5 and len(qw) >= 5))
                for qw in q_words
            )
            for p in authorities
        )

        if q_words and not has_chunk_match and not has_auth_match:
            return {
                "answer": "Available case materials and legal authorities contain insufficient evidence to establish the requested fact or legal conclusion.",
                "grounding_status": "INSUFFICIENT_EVIDENCE",
                "citations": [],
                "authority_citations": [],
                "claims": [],
                "uncertainties": ["No matching evidence or statutory authority found."],
                "warnings": ["NO_RELEVANT_EVIDENCE"],
            }

        # Check for simulated conflict query or evidence
        if "conflict" in user_prompt.lower() or any("conflict" in c.content.lower() for c in chunks):
            chunk1 = chunks[0] if chunks else None
            chunk2 = chunks[1] if len(chunks) > 1 else chunk1
            citations = []
            if chunk1:
                citations.append({
                    "chunk_id": str(chunk1.chunk_id),
                    "document_id": str(chunk1.document_id),
                    "text_snippet": chunk1.content[:120],
                })
            if chunk2:
                citations.append({
                    "chunk_id": str(chunk2.chunk_id),
                    "document_id": str(chunk2.document_id),
                    "text_snippet": chunk2.content[:120],
                })

            return {
                "answer": f"Case documents present conflicting statements: Source '{chunk1.source_filename if chunk1 else 'Doc 1'}' states one position, whereas source '{chunk2.source_filename if chunk2 else 'Doc 2'}' indicates a competing position.",
                "grounding_status": "CONFLICTING_EVIDENCE",
                "citations": citations,
                "authority_citations": [],
                "claims": [
                    {
                        "claim_text": f"Source {chunk1.source_filename if chunk1 else 'Doc 1'} presents an affirmative claim.",
                        "status": "SUPPORTED",
                        "supporting_chunk_ids": [str(chunk1.chunk_id)] if chunk1 else [],
                    },
                ],
                "uncertainties": ["Evidentiary discrepancy between case documents."],
                "warnings": ["EVIDENTIARY_CONFLICT_DETECTED"],
            }

        # Build case evidence citations
        case_citations = []
        for c in chunks[:2]:
            case_citations.append({
                "chunk_id": str(c.chunk_id),
                "document_id": str(c.document_id),
                "text_snippet": c.content[:150],
            })

        # Build legal authority citations
        auth_citations = []
        for p in authorities[:2]:
            auth_citations.append({
                "canonical_identifier": p.canonical_identifier,
                "canonical_provision_id": p.canonical_provision_id,
                "act_or_judgment_name": p.name,
                "section_or_para": f"Section {p.section_number}" if not p.section_number.startswith("Para") else p.section_number,
                "source_type": p.source_type.value if hasattr(p.source_type, "value") else str(p.source_type),
                "authority_level": p.authority_level,
                "jurisdiction": p.jurisdiction,
                "effective_from": p.effective_from.isoformat() if p.effective_from else None,
                "effective_to": p.effective_to.isoformat() if p.effective_to else None,
                "text_snippet": p.content[:150],
            })

        # Build claims
        claims = []
        answer_parts = []
        if chunks:
            top_chunk = chunks[0]
            answer_parts.append(f"Based on case materials in {top_chunk.source_filename}: {top_chunk.content.strip()}.")
            claims.append({
                "claim_text": f"Case document {top_chunk.source_filename} establishes {top_chunk.content[:150]}.",
                "status": "SUPPORTED",
                "supporting_chunk_ids": [str(top_chunk.chunk_id)],
                "supporting_authority_ids": [],
            })

        if authorities:
            top_auth = authorities[0]
            answer_parts.append(f"Under statutory authority of {top_auth.name} (Section {top_auth.section_number}): {top_auth.content.strip()}.")
            claims.append({
                "claim_text": f"Under {top_auth.name} Section {top_auth.section_number}, {top_auth.content[:150]}.",
                "status": "SUPPORTED",
                "supporting_chunk_ids": [],
                "supporting_authority_ids": [top_auth.canonical_provision_id],
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


class OpenAILLMProvider:
    """Production OpenAI LLM Provider with structured JSON output, exponential backoff,

    and strict secret/pii protection.
    """

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.max_retries = settings.OPENAI_MAX_RETRIES

        if not settings.OPENAI_API_KEY:
            raise AppException(
                status_code=500,
                code="AI_PROVIDER_MISCONFIGURED",
                message="OPENAI_API_KEY is not configured.",
            )

        self.client = openai.OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.EMBEDDING_TIMEOUT_SECONDS * 2,
        )

    def generate_structured_response(
        self,
        system_prompt: str,
        user_prompt: str,
        candidate_chunks: list[RetrievedEvidence] | None = None,
        authority_provisions: list[RetrievedLegalAuthority] | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        attempts = 0
        while attempts <= self.max_retries:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=temperature,
                )

                raw_content = response.choices[0].message.content or "{}"
                return json.loads(raw_content)

            except openai.RateLimitError as e:
                attempts += 1
                if attempts > self.max_retries:
                    raise AppException(
                        status_code=429,
                        code="AI_RATE_LIMIT",
                        message="AI provider rate limit reached. Please try again shortly.",
                    ) from e
                time.sleep(2**attempts)

            except openai.APITimeoutError as e:
                attempts += 1
                if attempts > self.max_retries:
                    raise AppException(
                        status_code=504,
                        code="AI_TIMEOUT",
                        message="AI provider request timed out.",
                    ) from e
                time.sleep(2**attempts)

            except openai.APIConnectionError as e:
                attempts += 1
                if attempts > self.max_retries:
                    raise AppException(
                        status_code=502,
                        code="AI_CONNECTION_ERROR",
                        message="Failed to connect to AI provider.",
                    ) from e
                time.sleep(2**attempts)

            except json.JSONDecodeError as e:
                logger.error("Failed to parse JSON response from LLM provider: %s", e)
                raise AppException(
                    status_code=502,
                    code="AI_MALFORMED_RESPONSE",
                    message="AI provider returned an invalid structured output.",
                ) from e

            except AppException:
                raise

            except Exception as e:
                logger.exception("Unexpected error in OpenAILLMProvider")
                raise AppException(
                    status_code=500,
                    code="AI_GENERATION_ERROR",
                    message="An unexpected error occurred while communicating with the AI service.",
                ) from e

        raise AppException(
            status_code=504,
            code="AI_TIMEOUT",
            message="AI provider request exceeded maximum retry attempts.",
        )


def get_llm_provider() -> LLMProvider:
    """Factory returning the appropriate LLM provider based on environment and configuration."""
    if (
        not settings.OPENAI_API_KEY
        or settings.OPENAI_API_KEY in ("dummy-test-key", "test-key", "<set-in-environment>", "dummy-key")
        or settings.OPENAI_API_KEY.startswith("dummy")
        or settings.ENVIRONMENT in ("test", "testing")
    ):
        return MockLLMProvider()

    return OpenAILLMProvider()
