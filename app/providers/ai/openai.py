"""Canonical OpenAI Provider Implementation.

Encapsulates OpenAI SDK operations, exponential backoff retries,
JSON mode structured generation, error normalization, and token telemetry.
"""

import json
import logging
import time
from typing import Any

import openai

from app.core.ai_config import AI_CONFIG
from app.core.ai_exceptions import (
    AIInvalidResponseError,
    AIProviderError,
    AIProviderMisconfiguredError,
    AIProviderUnavailableError,
    AIQuotaExceededError,
    AIRequestTimeoutError,
)
from app.core.config import settings
from app.providers.ai.base import AIProvider
from app.schemas.ai import AIResearchResponse, Citation
from app.schemas.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)


class CanonicalOpenAIProvider(AIProvider):
    """Production-grade OpenAI provider with strict error normalization and exponential backoff."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ):
        self.provider_name = "openai"
        resolved_model = model or getattr(settings, "AI_MODEL", None) or AI_CONFIG.DEFAULT_CHAT_MODEL
        self.model: str = str(resolved_model)
        self.timeout = timeout or AI_CONFIG.DEFAULT_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.OPENAI_MAX_RETRIES

        key = api_key or settings.OPENAI_API_KEY
        if not key or key in ("<set-in-environment>", "", "dummy-key", "test-key", "dummy-test-key") or key.startswith("dummy"):
            raise AIProviderMisconfiguredError("OPENAI_API_KEY is missing or invalid.")

        self.client = openai.OpenAI(api_key=key, timeout=self.timeout)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Executes raw completion with transient error retries."""
        attempts = 0
        while attempts <= self.max_retries:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""

            except openai.RateLimitError as e:
                attempts += 1
                if attempts > self.max_retries:
                    raise AIQuotaExceededError("AI provider rate limit reached.") from e
                time.sleep(AI_CONFIG.DEFAULT_BACKOFF_FACTOR**attempts)

            except openai.APITimeoutError as e:
                attempts += 1
                if attempts > self.max_retries:
                    raise AIRequestTimeoutError("AI provider request timed out.") from e
                time.sleep(AI_CONFIG.DEFAULT_BACKOFF_FACTOR**attempts)

            except openai.APIConnectionError as e:
                attempts += 1
                if attempts > self.max_retries:
                    raise AIProviderUnavailableError("Failed to connect to AI provider.") from e
                time.sleep(AI_CONFIG.DEFAULT_BACKOFF_FACTOR**attempts)

            except openai.AuthenticationError as e:
                logger.error("OpenAI authentication rejected: %s", e)
                raise AIProviderMisconfiguredError("Invalid OpenAI API credentials.") from e

            except openai.BadRequestError as e:
                logger.error("OpenAI bad request: %s", e)
                raise AIProviderError(status_code=400, code="AI_BAD_REQUEST", message=str(e)) from e

            except Exception as e:
                logger.exception("Unexpected failure during OpenAI text generation: %s", e)
                raise AIProviderError(status_code=500, code="AI_GENERATION_ERROR", message="Error generating AI response.") from e

        raise AIRequestTimeoutError("Maximum retries exceeded communicating with AI provider.")

    def generate_structured_response(
        self,
        system_prompt: str,
        user_prompt: str,
        candidate_chunks: list[Any] | None = None,
        authority_provisions: list[Any] | None = None,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generates structured JSON response, enforcing json_object response format."""
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
                try:
                    return json.loads(raw_content)
                except json.JSONDecodeError as jde:
                    logger.error("Model returned non-JSON payload: %s", raw_content[:200])
                    raise AIInvalidResponseError("AI provider returned an invalid structured output.") from jde

            except openai.RateLimitError as e:
                attempts += 1
                if attempts > self.max_retries:
                    raise AIQuotaExceededError("AI provider rate limit reached. Please try again shortly.") from e
                time.sleep(AI_CONFIG.DEFAULT_BACKOFF_FACTOR**attempts)

            except openai.APITimeoutError as e:
                attempts += 1
                if attempts > self.max_retries:
                    raise AIRequestTimeoutError("AI provider request timed out.") from e
                time.sleep(AI_CONFIG.DEFAULT_BACKOFF_FACTOR**attempts)

            except openai.APIConnectionError as e:
                attempts += 1
                if attempts > self.max_retries:
                    raise AIProviderUnavailableError("Failed to connect to AI provider.") from e
                time.sleep(AI_CONFIG.DEFAULT_BACKOFF_FACTOR**attempts)

            except openai.AuthenticationError as e:
                logger.error("OpenAI authentication rejected: %s", e)
                raise AIProviderMisconfiguredError("Invalid OpenAI API credentials.") from e

            except openai.BadRequestError as e:
                logger.error("OpenAI bad request: %s", e)
                raise AIProviderError(status_code=400, code="AI_BAD_REQUEST", message=str(e)) from e

            except (AIProviderError, AIInvalidResponseError):
                raise

            except Exception as e:
                logger.exception("Unexpected error in CanonicalOpenAIProvider: %s", e)
                raise AIProviderError(
                    status_code=500,
                    code="AI_GENERATION_ERROR",
                    message="An unexpected error occurred while communicating with the AI service.",
                ) from e

        raise AIRequestTimeoutError("AI provider request exceeded maximum retry attempts.")

    def generate_research_response(
        self,
        system_prompt: str,
        user_query: str,
        chunks: list[RetrievedChunk],
    ) -> AIResearchResponse:
        """Generates evidence-grounded research response with verified citation payloads."""
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

        valid_chunk_map = {str(c.chunk_id): c for c in chunks}

        # Build evidence context
        evidence_blocks = []
        for idx, c in enumerate(chunks):
            snippet = c.content.strip().replace("</evidence>", "&lt;/evidence&gt;").replace("<evidence", "&lt;evidence")
            evidence_blocks.append(
                f'<evidence index="{idx}" chunk_id="{c.chunk_id}" document_id="{c.document_id}">\n{snippet}\n</evidence>'
            )

        formatted_evidence = "\n\n".join(evidence_blocks)

        strict_system_directive = (
            f"{system_prompt}\n\n"
            "MANDATORY OUTPUT FORMAT:\n"
            "You MUST respond ONLY with a valid JSON object with the following schema:\n"
            "{\n"
            '  "answer": "string (evidence-grounded legal answer. Clearly state if evidence is insufficient)",\n'
            '  "citations": [\n'
            "    {\n"
            '      "chunk_id": "UUID string matching the chunk_id attribute from <evidence>",\n'
            '      "document_id": "UUID string matching the document_id attribute from <evidence>",\n'
            '      "text_snippet": "exact quote or relevant snippet from the evidence",\n'
            '      "relevance_score": 0.95\n'
            "    }\n"
            "  ],\n"
            '  "warnings": ["string (e.g. UNCERTAINTY_HIGH, INSUFFICIENT_EVIDENCE)"]\n'
            "}\n"
            "CRITICAL: Do NOT invent chunk_ids or document_ids. Every citation MUST reference an actual chunk provided."
        )

        user_content = f"AVAILABLE EVIDENCE:\n{formatted_evidence}\n\nUSER QUERY:\n{user_query}"

        data = self.generate_structured_response(
            system_prompt=strict_system_directive,
            user_prompt=user_content,
            temperature=0.1,
        )

        raw_citations = data.get("citations", [])
        verified_citations: list[Citation] = []
        warnings: list[str] = list(data.get("warnings", []))

        for item in raw_citations:
            c_id_str = str(item.get("chunk_id", ""))
            if c_id_str in valid_chunk_map:
                matching_chunk = valid_chunk_map[c_id_str]
                try:
                    verified_citations.append(
                        Citation(
                            chunk_id=matching_chunk.chunk_id,
                            document_id=matching_chunk.document_id,
                            text_snippet=item.get("text_snippet") or matching_chunk.content[:150],
                            relevance_score=float(item.get("relevance_score", 0.9)),
                        )
                    )
                except (KeyError, ValueError, TypeError) as val_err:
                    logger.debug("Skipping malformed citation payload: %s", val_err)
                    continue

        if raw_citations and len(verified_citations) < len(raw_citations) and "UNVERIFIED_CITATION_REMOVED" not in warnings:
            warnings.append("UNVERIFIED_CITATION_REMOVED")

        return AIResearchResponse(
            answer=data.get("answer", "Evidence insufficient to provide a verified answer."),
            citations=verified_citations,
            warnings=warnings,
        )

    def health_check(self) -> bool:
        """Verifies OpenAI API connectivity and credential validity."""
        try:
            self.client.models.list()
            return True
        except Exception:
            return False
