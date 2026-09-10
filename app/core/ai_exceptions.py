"""Normalized application-level AI exceptions.

Prevents raw provider exceptions, credentials, or internal provider specifics
from leaking into upper business layers or API consumers.
"""

from app.core.exceptions import AppException


class AIProviderError(AppException):
    """Base exception for all AI provider-related failures."""

    def __init__(
        self,
        status_code: int = 500,
        code: str = "AI_PROVIDER_ERROR",
        message: str = "An error occurred while interacting with the AI provider.",
    ):
        super().__init__(status_code=status_code, code=code, message=message)


class AIProviderMisconfiguredError(AIProviderError):
    """Raised when an AI provider lacks required configuration or API credentials."""

    def __init__(
        self,
        message: str = "AI provider is not properly configured.",
    ):
        super().__init__(
            status_code=500,
            code="AI_PROVIDER_MISCONFIGURED",
            message=message,
        )


class AIProviderUnavailableError(AIProviderError):
    """Raised when the AI provider cannot be reached or is temporarily unavailable."""

    def __init__(
        self,
        message: str = "AI provider service is currently unavailable. Please retry shortly.",
    ):
        super().__init__(
            status_code=502,
            code="AI_CONNECTION_ERROR",
            message=message,
        )


class AIRequestTimeoutError(AIProviderError):
    """Raised when an AI request exceeds timeout limits or max retries."""

    def __init__(
        self,
        message: str = "AI provider request timed out. Please try again.",
    ):
        super().__init__(
            status_code=504,
            code="AI_TIMEOUT",
            message=message,
        )


class AIQuotaExceededError(AIProviderError):
    """Raised when rate limits or user query quotas are exceeded."""

    def __init__(
        self,
        message: str = "AI provider rate limit reached. Please try again shortly.",
    ):
        super().__init__(
            status_code=429,
            code="AI_RATE_LIMIT",
            message=message,
        )


class AIInvalidResponseError(AIProviderError):
    """Raised when the AI provider returns malformed, unparseable, or invalid structured data."""

    def __init__(
        self,
        message: str = "AI provider returned an invalid structured output.",
    ):
        super().__init__(
            status_code=502,
            code="AI_MALFORMED_RESPONSE",
            message=message,
        )


class AIGroundingFailureError(AIProviderError):
    """Raised when a strict grounding requirement cannot be established from evidence."""

    def __init__(
        self,
        message: str = "Evidence insufficient to support a verified legal response.",
    ):
        super().__init__(
            status_code=422,
            code="AI_GROUNDING_FAILURE",
            message=message,
        )


class AIPromptSecurityError(AIProviderError):
    """Raised when prompt injection, system manipulation, or delimiter tampering is intercepted."""

    def __init__(
        self,
        message: str = "Query was rejected by prompt-injection safety controls.",
    ):
        super().__init__(
            status_code=400,
            code="PROMPT_INJECTION_DETECTED",
            message=message,
        )
