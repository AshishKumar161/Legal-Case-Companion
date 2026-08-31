import json
import logging
import time
from typing import Protocol

import openai

from app.core.config import settings
from app.core.exceptions import AppException
from app.schemas.ai import AIResearchResponse, Citation
from app.schemas.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)


class AIProvider(Protocol):
    """Interface / Protocol for AI model providers.

    Concrete model implementations (e.g., OpenAI, Anthropic, local LLM) must adhere to this interface.
    """

    model: str

    def generate_research_response(
        self, system_prompt: str, user_query: str, chunks: list[RetrievedChunk]
    ) -> AIResearchResponse: ...


class StubAIProvider:
    """Development and testing stub provider.

    Provides deterministic behavior for integration testing and local dev.
    """

    model: str = "stub-llm"

    def generate_research_response(
        self, system_prompt: str, user_query: str, chunks: list[RetrievedChunk]
    ) -> AIResearchResponse:
        if not chunks:
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


class ProductionOpenAIProvider:
    """Production OpenAI provider with structured citation extraction,

    system-boundary isolation, and exponential backoff retry handling.
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

    def generate_research_response(
        self, system_prompt: str, user_query: str, chunks: list[RetrievedChunk]
    ) -> AIResearchResponse:
        if not chunks:
            return AIResearchResponse(
                answer="Evidence insufficient. The system cannot reliably answer this point from the available sources.",
                citations=[],
                warnings=["No relevant evidence retrieved."],
            )

        valid_chunk_map = {str(c.chunk_id): c for c in chunks}

        # Build evidence context with strict XML encapsulation
        evidence_blocks = []
        for idx, c in enumerate(chunks):
            snippet = c.content.strip()
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

        user_content = (
            f"AVAILABLE EVIDENCE:\n{formatted_evidence}\n\n"
            f"USER QUERY:\n{user_query}"
        )

        attempts = 0
        while attempts <= self.max_retries:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": strict_system_directive},
                        {"role": "user", "content": user_content},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )

                content = response.choices[0].message.content or "{}"
                data = json.loads(content)

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
                                    text_snippet=item.get("text_snippet")
                                    or matching_chunk.content[:150],
                                    relevance_score=float(
                                        item.get("relevance_score", 0.9)
                                    ),
                                )
                            )
                        except (KeyError, ValueError, TypeError) as val_err:
                            logger.debug(
                                "Skipping malformed citation payload: %s", val_err
                            )
                            continue

                if (
                    raw_citations
                    and len(verified_citations) < len(raw_citations)
                    and "UNVERIFIED_CITATION_REMOVED" not in warnings
                ):
                    warnings.append("UNVERIFIED_CITATION_REMOVED")

                return AIResearchResponse(
                    answer=data.get(
                        "answer",
                        "Evidence insufficient to provide a verified answer.",
                    ),
                    citations=verified_citations,
                    warnings=warnings,
                )

            except openai.RateLimitError as e:
                attempts += 1
                if attempts > self.max_retries:
                    raise AppException(
                        status_code=429,
                        code="AI_RATE_LIMIT",
                        message="AI provider rate limit reached.",
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

            except Exception as e:
                logger.exception("Unexpected error in ProductionOpenAIProvider")
                raise AppException(
                    status_code=500,
                    code="AI_GENERATION_ERROR",
                    message="Error generating AI response.",
                ) from e

        return AIResearchResponse(
            answer="Evidence insufficient. The system could not complete the request.",
            citations=[],
            warnings=["GENERATION_FAILED"],
        )


def get_ai_provider() -> AIProvider:
    """Factory returning the AI provider integration boundary."""
    if settings.ENVIRONMENT == "production":
        return ProductionOpenAIProvider()

    if (
        settings.OPENAI_API_KEY
        and settings.OPENAI_API_KEY
        not in ("<set-in-environment>", "", "dummy-key", "test-key")
        and not settings.OPENAI_API_KEY.startswith("dummy")
    ):
        try:
            return ProductionOpenAIProvider()
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"Failed to initialize ProductionOpenAIProvider, falling back to stub: {e}"
            )
            return StubAIProvider()

    return StubAIProvider()
