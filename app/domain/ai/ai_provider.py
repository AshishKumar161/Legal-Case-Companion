"""Backward-compatible AI provider facade.

Delegates canonical operations to `app.providers.ai` while maintaining full
backward compatibility for existing services, tests, and benchmark harnesses.
"""

import logging

from app.core.config import settings
from app.providers.ai.base import AIProvider as CanonicalAIProvider
from app.providers.ai.factory import get_canonical_ai_provider
from app.providers.ai.mock import CanonicalMockAIProvider
from app.providers.ai.openai import CanonicalOpenAIProvider
from app.schemas.ai import AIResearchResponse, Citation
from app.schemas.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)

# Re-export protocol
AIProvider = CanonicalAIProvider


class StubAIProvider(CanonicalMockAIProvider):
    """Backward-compatible stub provider for integration testing and local dev."""

    def __init__(self, model: str = "stub-llm"):
        super().__init__(model=model)


class ProductionOpenAIProvider(CanonicalOpenAIProvider):
    """Backward-compatible production OpenAI provider."""

    def __init__(self, model: str = "gpt-4o"):
        super().__init__(model=model)


def sanitize_untrusted_prompt_text(text: str) -> str:
    """Sanitizes untrusted text to prevent prompt injection and delimiter breakout.

    Preserves Hindi, transliterated, and English injection neutralization patterns.
    """
    from app.domain.ai.ai_prompt_policy import PromptSecurityPolicy
    return PromptSecurityPolicy.sanitize_untrusted_prompt_text(text)


def get_ai_provider() -> CanonicalAIProvider:
    """Factory returning the AI provider integration boundary."""
    if (
        getattr(settings, "AI_INTEGRATION_ENABLED", True)
        and settings.OPENAI_API_KEY
        and settings.OPENAI_API_KEY
        not in ("<set-in-environment>", "", "dummy-key", "test-key", "dummy-test-key")
        and not settings.OPENAI_API_KEY.startswith("dummy")
        and settings.ENVIRONMENT not in ("test", "testing")
    ):
        try:
            return ProductionOpenAIProvider()
        except Exception as e:
            logger.warning(
                "Failed to initialize ProductionOpenAIProvider, falling back to stub: %s",
                e,
            )
            return StubAIProvider()

    return StubAIProvider()


__all__ = [
    "AIProvider",
    "AIResearchResponse",
    "Citation",
    "ProductionOpenAIProvider",
    "RetrievedChunk",
    "StubAIProvider",
    "get_ai_provider",
    "sanitize_untrusted_prompt_text",
]
