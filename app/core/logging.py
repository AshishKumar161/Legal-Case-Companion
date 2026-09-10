import json
import logging
import re
import sys

from app.middleware.correlation_id import correlation_id_ctx


class CorrelationIdFilter(logging.Filter):
    """Injects correlation_id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_ctx.get()
        return True


class SensitiveDataScrubberFilter(logging.Filter):
    """Scrubs sensitive credentials, tokens, passwords, and signed URLs from log messages."""

    PATTERNS = [
        # Passwords (double, single, or unquoted)
        (re.compile(r'(?i)("?password"?\s*[:=]\s*)["\']?[^"\'\s,;]+["\']?'), r'\1"***REDACTED***"'),
        # Bearer tokens
        (re.compile(r'(?i)Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*'), r"Bearer ***REDACTED***"),
        # Refresh tokens
        (re.compile(r'(?i)("?refresh_token"?\s*[:=]\s*)["\']?[^"\'\s,;]+["\']?'), r'\1"***REDACTED***"'),
        # Access tokens
        (re.compile(r'(?i)("?access_token"?\s*[:=]\s*)["\']?[^"\'\s,;]+["\']?'), r'\1"***REDACTED***"'),
        # Generic tokens
        (re.compile(r'(?i)("?token"?\s*[:=]\s*)["\']?[^"\'\s,;]+["\']?'), r'\1"***REDACTED***"'),
        # Signed URL credentials
        (re.compile(r'(?i)(X-Amz-Signature=[a-f0-9]+)'), r"X-Amz-Signature=***REDACTED***"),
        (re.compile(r'(?i)(AWSAccessKeyId=[A-Z0-9]+)'), r"AWSAccessKeyId=***REDACTED***"),
        # General secret / private key
        (re.compile(r'(?i)("?(?:secret|api_key|client_secret)"?\s*[:=]\s*)["\']?[^"\'\s,;]+["\']?'), r'\1"***REDACTED***"'),
        # Payment Card Numbers (16 digits)
        (re.compile(r'\b(?:\d{4}[ -]?){3}\d{4}\b'), r"***REDACTED-CARD***"),
        # Indian Aadhaar (12 digits with or without spaces)
        (re.compile(r'\b\d{4}\s\d{4}\s\d{4}\b'), r"***REDACTED-AADHAAR***"),
        # Indian PAN (Permanent Account Number)
        (re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'), r"***REDACTED-PAN***"),
        # Raw eCourts CNR in logs
        (re.compile(r'\b[A-Z]{4}\d{12}\b'), r"***REDACTED-CNR***"),
    ]

    @classmethod
    def scrub_text(cls, text: str) -> str:
        if not isinstance(text, str):
            return text
        for pattern, replacement in cls.PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args and not record.name.startswith("uvicorn"):
            try:
                record.msg = record.getMessage()
                record.args = None
            except Exception:
                pass
        if isinstance(record.msg, str):
            record.msg = self.scrub_text(record.msg)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from app.core.config import settings

        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "service": "lcc-backend",
            "environment": getattr(settings, "ENVIRONMENT", "development"),
            "correlation_id": getattr(record, "correlation_id", "-"),
            "message": record.getMessage(),
        }
        if hasattr(record, "user_id"):
            log_obj["user_id"] = record.user_id
        if hasattr(record, "duration_ms"):
            log_obj["duration_ms"] = record.duration_ms
        if hasattr(record, "error_code"):
            log_obj["error_code"] = record.error_code
        if record.exc_info:
            log_obj["exception"] = SensitiveDataScrubberFilter.scrub_text(
                self.formatException(record.exc_info)
            )
        return json.dumps(log_obj)


class ScrubbingStandardFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        return SensitiveDataScrubberFilter.scrub_text(rendered)


def setup_logging(log_level: str = "INFO") -> None:
    """Configures structured logging for the application with correlation and sanitization."""
    logger = logging.getLogger("app")
    logger.setLevel(log_level)

    # Prevent duplicate logs if already configured
    if logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    from app.core.config import settings

    if settings.ENVIRONMENT == "production":
        formatter: logging.Formatter = JsonFormatter(datefmt="%Y-%m-%dT%H:%M:%SZ")
    else:
        formatter = ScrubbingStandardFormatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | [req_id: %(correlation_id)s] | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())
    handler.addFilter(SensitiveDataScrubberFilter())
    logger.addHandler(handler)

    # Configure uvicorn loggers with correlation and scrubbing filters
    for uvicorn_logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        uvicorn_logger.addFilter(CorrelationIdFilter())
        uvicorn_logger.addFilter(SensitiveDataScrubberFilter())
