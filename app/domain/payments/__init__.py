"""Payments, Commercial Billing & Reconciliation Domain package."""

import importlib
from typing import Any

__all__ = [
    "CancellationEconomicsResult",
    "CancellationPolicyService",
    "CommercialService",
    "MockPaymentProvider",
    "PaymentProvider",
    "PaymentService",
    "ReconciliationService",
    "StripePaymentProvider",
    "UnitEconomicsService",
    "get_payment_provider",
    "verify_stripe_webhook_signature",
]

_MODULE_MAP = {
    "PaymentService": "payment_service",
    "PaymentProvider": "payment_service",
    "StripePaymentProvider": "payment_service",
    "MockPaymentProvider": "payment_service",
    "verify_stripe_webhook_signature": "payment_service",
    "get_payment_provider": "payment_service",
    "CommercialService": "commercial_service",
    "ReconciliationService": "reconciliation_service",
    "CancellationPolicyService": "cancellation_policy_service",
    "CancellationEconomicsResult": "cancellation_policy_service",
    "UnitEconomicsService": "unit_economics_service",
}


def __getattr__(name: str) -> Any:
    mod_name = _MODULE_MAP.get(name)
    if mod_name:
        mod = importlib.import_module(f"app.domain.payments.{mod_name}")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
