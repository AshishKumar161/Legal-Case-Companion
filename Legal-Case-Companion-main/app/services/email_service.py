import logging
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailProvider(Protocol):
    def send_email(self, to_email: str, subject: str, html_body: str) -> bool: ...


class ConsoleEmailProvider:
    """Development provider that prints emails to stdout."""

    def send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        logger.info("--- MOCK EMAIL ---")
        logger.info(f"To: {to_email}")
        logger.info(f"Subject: {subject}")
        # Note: Do not log the raw html_body if it contains raw tokens in production
        # In development, it's fine for debugging
        logger.info("Body: [REDACTED FOR LOGGING LENGTH]")
        logger.info("------------------")
        return True


class SendGridEmailProvider:
    """Production provider for SendGrid."""

    def __init__(self):
        if not settings.SENDGRID_API_KEY:
            raise ValueError("SENDGRID_API_KEY is required for SendGridEmailProvider")
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.EMAIL_FROM

    def send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        logger.info(f"Sending email via SendGrid to {to_email} (Subject: {subject})")
        try:
            import httpx

            payload = {
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": self.from_email},
                "subject": subject,
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
                logger.info(f"SendGrid email dispatched successfully to {to_email}")
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

        boto_config = Config(retries={"max_attempts": 3})
        self.client = boto3.client("ses", config=boto_config, **client_kwargs)
        self.from_email = settings.EMAIL_FROM

    def send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        logger.info(f"Sending email via AWS SES to {to_email} (Subject: {subject})")
        try:
            self.client.send_email(
                Source=self.from_email,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Html": {"Data": html_body}},
                },
            )
            logger.info(f"AWS SES email dispatched successfully to {to_email}")
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"AWS SES failed to send email: {e}")
            return False


def get_email_provider() -> EmailProvider:
    if settings.EMAIL_PROVIDER == "sendgrid":
        return SendGridEmailProvider()
    elif settings.EMAIL_PROVIDER == "ses":
        return SESEmailProvider()

    # Fallback to console (but config validates this is not allowed in production)
    return ConsoleEmailProvider()
