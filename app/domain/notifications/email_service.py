import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Protocol

from app.core.config import settings
from app.core.exceptions import ConfigurationError, ValidationError

logger = logging.getLogger(__name__)

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_email_recipient(to_email: str) -> str:
    """Validates email recipient format and protects against CRLF header injection."""
    if not to_email or not isinstance(to_email, str):
        raise ValidationError("Email recipient must be a non-empty string")

    if "\r" in to_email or "\n" in to_email:
        raise ValidationError("Email recipient contains illegal CRLF control characters")

    clean = to_email.strip()
    if not _EMAIL_REGEX.match(clean):
        raise ValidationError(f"Invalid email recipient address: {clean}")

    return clean


def sanitize_email_subject(subject: str) -> str:
    """Sanitizes email subject and protects against CRLF header injection."""
    if not subject or not isinstance(subject, str):
        raise ValidationError("Email subject must be a non-empty string")

    if "\r" in subject or "\n" in subject:
        raise ValidationError("Email subject contains illegal CRLF control characters")

    clean = subject.strip()
    if not clean:
        raise ValidationError("Email subject cannot be empty")

    return clean


class EmailProvider(Protocol):
    def send_email(self, to_email: str, subject: str, html_body: str) -> bool: ...


class ConsoleEmailProvider:
    """Development provider that prints emails to stdout with clearly extracted action links."""

    def send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        safe_to = validate_email_recipient(to_email)
        safe_subject = sanitize_email_subject(subject)

        logger.info("==================== [DEV EMAIL DISPATCH] ====================")
        logger.info(f"To:      {safe_to}")
        logger.info(f"From:    {settings.EMAIL_FROM}")
        logger.info(f"Subject: {safe_subject}")

        # Extract links from HTML body for developer convenience
        urls = re.findall(r'href=[\'"]?([^\'" >]+)', html_body)
        if urls:
            logger.info("Action Links:")
            for url in urls:
                logger.info(f"  -> {url}")

        logger.info("--- Message Body ---")
        logger.info(html_body)
        logger.info("==============================================================")
        return True


class SMTPEmailProvider:
    """Production and staging SMTP provider (supports TLS/SSL, Mailtrap, AWS SES SMTP, SendGrid SMTP, etc.)."""

    def __init__(self):
        env = getattr(settings, "ENVIRONMENT", "development").lower()
        if not settings.SMTP_HOST:
            if env in ("production", "staging"):
                raise ConfigurationError("SMTP_HOST is required for SMTPEmailProvider in production/staging")
            raise ValueError("SMTP_HOST is required for SMTPEmailProvider")
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.EMAIL_FROM
        self.use_tls = settings.SMTP_TLS
        self.use_ssl = settings.SMTP_SSL

    def send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        safe_to = validate_email_recipient(to_email)
        safe_subject = sanitize_email_subject(subject)

        logger.info(f"Sending email via SMTP ({self.host}:{self.port}) to {safe_to} (Subject: {safe_subject})")
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = safe_subject
            msg["From"] = self.from_email
            msg["To"] = safe_to

            part = MIMEText(html_body, "html", "utf-8")
            msg.attach(part)

            if self.use_ssl:
                server: smtplib.SMTP = smtplib.SMTP_SSL(self.host, self.port, timeout=10.0)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=10.0)

            with server:
                if self.use_tls and not self.use_ssl:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.sendmail(self.from_email, [safe_to], msg.as_string())

            logger.info(f"SMTP email dispatched successfully to {safe_to}")
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"SMTP failed to send email to {safe_to}: {e}")
            return False


class SendGridEmailProvider:
    """Production provider for SendGrid."""

    def __init__(self):
        env = getattr(settings, "ENVIRONMENT", "development").lower()
        if not settings.SENDGRID_API_KEY:
            if env in ("production", "staging"):
                raise ConfigurationError("SENDGRID_API_KEY is required for SendGridEmailProvider in production/staging")
            raise ValueError("SENDGRID_API_KEY is required for SendGridEmailProvider")
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.EMAIL_FROM

    def send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        safe_to = validate_email_recipient(to_email)
        safe_subject = sanitize_email_subject(subject)

        logger.info(f"Sending email via SendGrid to {safe_to} (Subject: {safe_subject})")
        try:
            import httpx

            payload = {
                "personalizations": [{"to": [{"email": safe_to}]}],
                "from": {"email": self.from_email},
                "subject": safe_subject,
                "content": [{"type": "text/html", "value": html_body}],
            }
            response = httpx.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=10.0,
            )
            if response.status_code in (200, 201, 202):
                logger.info(f"SendGrid email dispatched successfully to {safe_to}")
                return True
            logger.error(
                f"SendGrid returned status {response.status_code}: {response.text}"
            )
            return False
        except Exception as e:  # noqa: BLE001
            logger.error(f"SendGrid failed to send email: {e}")
            return False


class SESEmailProvider:
    """Production provider for AWS SES."""

    def __init__(self):
        import boto3
        from botocore.config import Config

        client_kwargs = {"region_name": settings.AWS_REGION}
        if settings.SES_ACCESS_KEY_ID and settings.SES_SECRET_ACCESS_KEY:
            client_kwargs["aws_access_key_id"] = settings.SES_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = settings.SES_SECRET_ACCESS_KEY

        boto_config = Config(
            connect_timeout=5, read_timeout=15, retries={"max_attempts": 3}
        )
        self.client = boto3.client("ses", config=boto_config, **client_kwargs)
        self.from_email = settings.EMAIL_FROM

    def send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        safe_to = validate_email_recipient(to_email)
        safe_subject = sanitize_email_subject(subject)

        logger.info(f"Sending email via AWS SES to {safe_to} (Subject: {safe_subject})")
        try:
            self.client.send_email(
                Source=self.from_email,
                Destination={"ToAddresses": [safe_to]},
                Message={
                    "Subject": {"Data": safe_subject},
                    "Body": {"Html": {"Data": html_body}},
                },
            )
            logger.info(f"AWS SES email dispatched successfully to {safe_to}")
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"AWS SES failed to send email: {e}")
            return False


def get_email_provider() -> EmailProvider:
    env = getattr(settings, "ENVIRONMENT", "development").lower()
    provider = settings.EMAIL_PROVIDER.lower() if settings.EMAIL_PROVIDER else "console"

    if env in ("production", "staging"):
        if provider in ("console", "mock") or not settings.EMAIL_PROVIDER:
            raise ConfigurationError(
                f"{env.capitalize()} environment requires a production email provider (SMTP, SendGrid, SES). "
                f"ConsoleEmailProvider is strictly forbidden in {env}."
            )

    if provider == "sendgrid":
        return SendGridEmailProvider()
    elif provider == "ses":
        return SESEmailProvider()
    elif provider in ("smtp", "mailtrap", "mailpit"):
        return SMTPEmailProvider()

    # Default to console provider for development
    return ConsoleEmailProvider()

