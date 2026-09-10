"""Authoritative AI / LLM Configuration for Legal Case Companion (LCC).

Centralizes all model identifiers, temperature defaults, token limits,
context constraints, retry policies, and prompt versioning.
"""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class AIModelConfig:
    # Authoritative Model Identifiers
    DEFAULT_CHAT_MODEL: str = "gpt-4o"
    DEFAULT_EMBEDDING_MODEL: str = "text-embedding-3-small"
    MOCK_CHAT_MODEL: str = "mock-gpt-4o"
    STUB_CHAT_MODEL: str = "stub-llm"

    # Generation Parameters
    DEFAULT_TEMPERATURE: float = 0.1
    DEFAULT_MAX_OUTPUT_TOKENS: int = 2048

    # Timeout and Resilience
    DEFAULT_TIMEOUT_SECONDS: float = 30.0
    DEFAULT_MAX_RETRIES: int = 3
    DEFAULT_BACKOFF_FACTOR: float = 2.0

    # Context & Token Bounds
    MAX_EVIDENCE_CHUNKS: int = 10
    MAX_CHUNK_CHARACTERS: int = 1500
    MAX_LEGAL_AUTHORITIES: int = 5
    MAX_HISTORY_MESSAGES: int = 6
    MAX_USER_QUERY_CHARACTERS: int = 1000
    MAX_TOTAL_PROMPT_TOKENS: int = 8000

    # Canonical Prompt Versions
    PROMPT_VERSION_RESEARCH: str = "legal_research_v1"
    PROMPT_VERSION_ASSISTANT: str = "case_assistant_v1"
    PROMPT_VERSION_COPILOT: str = "case_copilot_v1"


AI_CONFIG: Final[AIModelConfig] = AIModelConfig()
