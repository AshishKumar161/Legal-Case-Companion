"""Lawyer Verification & Advocate Governance Domain package."""

import importlib
from typing import Any

__all__ = [
    "AdvocateOperationalState",
    "Cohort2Stage",
    "CohortGovernanceService",
    "LawyerDashboardService",
    "LawyerVerificationService",
    "MAX_VERIFICATION_FILE_BYTES",
    "RejectionCategory",
    "SourceOfTruthTag",
    "StageTarget",
]

_MODULE_MAP = {
    "LawyerVerificationService": "lawyer_verification_service",
    "RejectionCategory": "lawyer_verification_service",
    "MAX_VERIFICATION_FILE_BYTES": "lawyer_verification_service",
    "LawyerDashboardService": "lawyer_dashboard_service",
    "CohortGovernanceService": "cohort_governance_service",
    "Cohort2Stage": "cohort_governance_service",
    "AdvocateOperationalState": "cohort_governance_service",
    "SourceOfTruthTag": "cohort_governance_service",
    "StageTarget": "cohort_governance_service",
}


def __getattr__(name: str) -> Any:
    mod_name = _MODULE_MAP.get(name)
    if mod_name:
        mod = importlib.import_module(f"app.domain.verification.{mod_name}")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
