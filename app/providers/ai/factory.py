"""Authoritative AI Provider Factory for Legal Case Companion (LCC).

Returns the active canonical AI provider based on environment, settings, and credential presence.
"""

import logging

from app.core.config import settings
from app.providers.ai.base import AIProvider
from app.providers.ai.mock import CanonicalMockAIProvider
from app.providers.ai.openai import CanonicalOpenAIProvider
from app.providers.ai.lcc_pipeline import CanonicalLCCPipelineProvider

logger = logging.getLogger(__name__)


_canonical_provider_instance: AIProvider | None = None


def get_canonical_ai_provider() -> AIProvider:
    """Factory returning the canonical AI provider implementation (cached singleton).

    In production/staging with valid credentials, returns CanonicalOpenAIProvider.
    In testing/offline/local development, returns CanonicalMockAIProvider.
    """
    global _canonical_provider_instance
    if _canonical_provider_instance is not None:
        return _canonical_provider_instance

    if (
        getattr(settings, "AI_INTEGRATION_ENABLED", True)
        and settings.ENVIRONMENT not in ("test", "testing")
    ):
        # Return the LCC Pipeline Provider by default
        try:
            _canonical_provider_instance = CanonicalLCCPipelineProvider()
            return _canonical_provider_instance
        except Exception as e:
            logger.warning(
                "Failed to initialize CanonicalLCCPipelineProvider, falling back to mock provider: %s",
                e,
            )
            _canonical_provider_instance = CanonicalMockAIProvider()
            return _canonical_provider_instance

    _canonical_provider_instance = CanonicalMockAIProvider()
    return _canonical_provider_instance
