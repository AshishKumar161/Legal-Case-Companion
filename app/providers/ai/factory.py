"""Authoritative AI Provider Factory for Legal Case Companion (LCC).

Returns the active canonical AI provider based on environment, settings, and credential presence.
"""

import logging

from app.core.config import settings
from app.providers.ai.base import AIProvider
from app.providers.ai.mock import CanonicalMockAIProvider
from app.providers.ai.openai import CanonicalOpenAIProvider

logger = logging.getLogger(__name__)


def get_canonical_ai_provider() -> AIProvider:
    """Factory returning the canonical AI provider implementation.

    In production/staging with valid credentials, returns CanonicalOpenAIProvider.
    In testing/offline/local development, returns CanonicalMockAIProvider.
    """
    if (
        getattr(settings, "AI_INTEGRATION_ENABLED", True)
        and settings.OPENAI_API_KEY
        and settings.OPENAI_API_KEY
        not in ("<set-in-environment>", "", "dummy-key", "test-key", "dummy-test-key")
        and not settings.OPENAI_API_KEY.startswith("dummy")
        and settings.ENVIRONMENT not in ("test", "testing")
    ):
        try:
            return CanonicalOpenAIProvider()
        except Exception as e:
            logger.warning(
                "Failed to initialize CanonicalOpenAIProvider, falling back to mock provider: %s",
                e,
            )
            return CanonicalMockAIProvider()

    return CanonicalMockAIProvider()
