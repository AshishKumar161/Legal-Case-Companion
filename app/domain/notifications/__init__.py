"""Notifications, Reminders & Email Domain package."""

import importlib
from typing import Any

__all__ = ['AlertService', 'ConsoleEmailProvider', 'EmailProvider', 'NotificationService', 'ProductionAlert', 'ReminderService', 'SESEmailProvider', 'SMTPEmailProvider', 'SendGridEmailProvider', 'get_email_provider', 'sanitize_email_subject', 'validate_email_recipient']

_MODULE_MAP = {
    "NotificationService": "notification_service",
    "ReminderService": "reminder_service",
    "EmailProvider": "email_service",
    "ConsoleEmailProvider": "email_service",
    "SMTPEmailProvider": "email_service",
    "SendGridEmailProvider": "email_service",
    "SESEmailProvider": "email_service",
    "validate_email_recipient": "email_service",
    "sanitize_email_subject": "email_service",
    "get_email_provider": "email_service",
    "AlertService": "alert_service",
    "ProductionAlert": "alert_service",
}


def __getattr__(name: str) -> Any:
    mod_name = _MODULE_MAP.get(name)
    if mod_name:
        mod = importlib.import_module(f"app.domain.notifications.{mod_name}")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
