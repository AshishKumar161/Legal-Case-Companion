"""Backward-compatible LLM provider facade.

Delegates canonical operations to `app.providers.ai` while maintaining full
backward compatibility for existing services, tests, and mock assertions.
"""

import logging
from typing import Any, Protocol

from app.core.config import settings
from app.providers.ai.base import AIProvider as CanonicalAIProvider
from app.providers.ai.factory import get_canonical_ai_provider
from app.providers.ai.mock import CanonicalMockAIProvider
from app.providers.ai.openai import CanonicalOpenAIProvider
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


class MockLLMProvider(CanonicalMockAIProvider):
    """Deterministic Mock LLM Provider for offline development and test suites."""

    def __init__(self, model: str = "mock-gpt-4o"):
        super().__init__(model=model)


class OpenAILLMProvider(CanonicalOpenAIProvider):
    """Production OpenAI LLM Provider."""

    def __init__(self, model: str = "gpt-4o"):
        super().__init__(model=model)


def get_llm_provider() -> CanonicalAIProvider:
    """Factory returning the appropriate LLM provider based on environment and configuration."""
    if (
        not getattr(settings, "AI_INTEGRATION_ENABLED", True)
        or not settings.OPENAI_API_KEY
        or settings.OPENAI_API_KEY in ("dummy-test-key", "test-key", "<set-in-environment>", "dummy-key")
        or settings.OPENAI_API_KEY.startswith("dummy")
        or settings.ENVIRONMENT in ("test", "testing")
    ):
        return MockLLMProvider()

    return OpenAILLMProvider()


__all__ = [
    "LLMProvider",
    "MockLLMProvider",
    "OpenAILLMProvider",
    "get_llm_provider",
]
