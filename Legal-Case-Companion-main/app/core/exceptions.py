from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel


class ErrorDetails(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetails


class AppException(HTTPException):
    """
    Base exception for all application errors.
    Automatically formats into the standardized JSON error response.
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(status_code=status_code, detail=message)


class AuthenticationError(AppException):
    def __init__(
        self,
        message: str = "Invalid authentication credentials",
        code: str = "UNAUTHENTICATED",
    ):
        super().__init__(status_code=401, code=code, message=message)


class ValidationError(AppException):
    def __init__(self, message: str = "Validation failed", details: dict[str, Any] | None = None):
        super().__init__(status_code=422, code="VALIDATION_ERROR", message=message, details=details)


class ResourceNotFoundError(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(status_code=404, code="NOT_FOUND", message=message)


NotFoundError = ResourceNotFoundError


class AuthorizationError(AppException):
    def __init__(
        self,
        message: str = "Not authorized to access this resource",
        code: str = "FORBIDDEN",
    ):
        super().__init__(status_code=403, code=code, message=message)


class ConflictError(AppException):
    def __init__(
        self,
        message: str = "Resource conflict",
        code: str = "CONFLICT",
    ):
        super().__init__(status_code=409, code=code, message=message)


class ScannerUnavailableError(AppException):
    def __init__(
        self,
        message: str = "Malware scanner service is temporarily unavailable",
        code: str = "SCANNER_UNAVAILABLE",
    ):
        super().__init__(status_code=503, code=code, message=message)


class DependencyUnavailableError(AppException):
    def __init__(
        self,
        message: str = "Underlying dependency is temporarily unavailable",
        code: str = "DEPENDENCY_UNAVAILABLE",
    ):
        super().__init__(status_code=503, code=code, message=message)


class StorageError(AppException):
    def __init__(
        self,
        message: str = "Storage service operation failed",
        code: str = "STORAGE_ERROR",
    ):
        super().__init__(status_code=502, code=code, message=message)


class IntegrityError(AppException):
    def __init__(
        self,
        message: str = "Cryptographic integrity verification failed",
        code: str = "INTEGRITY_ERROR",
    ):
        super().__init__(status_code=422, code=code, message=message)


class RateLimitExceededError(AppException):
    def __init__(
        self,
        message: str = "Rate limit exceeded. Please retry later.",
        code: str = "RATE_LIMITED",
    ):
        super().__init__(status_code=429, code=code, message=message)


class ConfigurationError(AppException):
    def __init__(
        self,
        message: str = "Invalid service configuration",
        code: str = "CONFIGURATION_ERROR",
    ):
        super().__init__(status_code=500, code=code, message=message)
