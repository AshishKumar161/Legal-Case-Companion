"""Operational Governance, Compliance & Trust Domain package."""

import importlib
from typing import Any

__all__ = ['AbuseDefenseService', 'ComplianceService', 'DISPOSABLE_DOMAINS', 'ExperimentService', 'IncidentService', 'LaunchGateCategory', 'LaunchGateService', 'PublicLaunchDecision', 'TranslationService']

_MODULE_MAP = {
    "LaunchGateService": "launch_gate_service",
    "LaunchGateCategory": "launch_gate_service",
    "PublicLaunchDecision": "launch_gate_service",
    "IncidentService": "incident_service",
    "ComplianceService": "compliance_service",
    "AbuseDefenseService": "abuse_defense_service",
    "DISPOSABLE_DOMAINS": "abuse_defense_service",
    "TranslationService": "translation_service",
    "ExperimentService": "experiment_service",
}


def __getattr__(name: str) -> Any:
    mod_name = _MODULE_MAP.get(name)
    if mod_name:
        mod = importlib.import_module(f"app.domain.governance.{mod_name}")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
