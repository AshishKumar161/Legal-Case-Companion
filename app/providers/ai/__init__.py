"""Canonical AI Provider Package for Legal Case Companion (LCC)."""

from app.providers.ai.base import AIExecutionMetadata, AIProvider, TokenUsage
from app.providers.ai.factory import get_canonical_ai_provider
from app.providers.ai.mock import CanonicalMockAIProvider
from app.providers.ai.openai import CanonicalOpenAIProvider

__all__ = [
    "AIExecutionMetadata",
    "AIProvider",
    "CanonicalMockAIProvider",
    "CanonicalOpenAIProvider",
    "TokenUsage",
    "get_canonical_ai_provider",
]
