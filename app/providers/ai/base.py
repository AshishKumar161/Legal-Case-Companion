"""Canonical AI Provider Protocol and Shared Dataclasses.

Defines the single authoritative provider interface for Legal Case Companion (LCC).
Business/domain logic depends strictly on this abstraction rather than any specific vendor SDK.
"""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from app.schemas.ai import AIResearchResponse
from app.schemas.retrieval import RetrievedChunk


@dataclass(frozen=True)
class TokenUsage:
    """Estimated or provider-reported token accounting."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class AIExecutionMetadata:
    """Audit and telemetry metadata captured for every LLM operation."""

    provider: str
    model: str
    latency_ms: float
    usage: TokenUsage
    prompt_version: str = "v1"


@runtime_checkable
class AIProvider(Protocol):
    """Canonical interface for AI / LLM model providers.

    All concrete implementations (OpenAI, Anthropic, Mock, Stubs) must adhere to this protocol.
    """

    model: str
    provider_name: str

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Executes raw text generation."""
        ...

    def generate_structured_response(
        self,
        system_prompt: str,
        user_prompt: str,
        candidate_chunks: list[Any] | None = None,
        authority_provisions: list[Any] | None = None,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generates a structured JSON response verified against evidentiary sources."""
        ...

    def generate_research_response(
        self,
        system_prompt: str,
        user_query: str,
        chunks: list[RetrievedChunk],
    ) -> AIResearchResponse:
        """Generates evidence-grounded research response with verified citation payloads."""
        ...

    def health_check(self) -> bool:
        """Verifies provider connectivity and operational status."""
        ...
