"""Cases & Workflow Domain package."""

from typing import Any

__all__ = ['CaseService', 'CaseWorkflowService', 'CaseAttentionService', 'CaseIntelligenceService', 'CaseReportService', 'CollaborationService', 'BundleService', 'BundlePdfEngine']


def __getattr__(name: str) -> Any:
    if name == "CaseService":
        from app.domain.cases.case_service import CaseService
        return CaseService
    if name == "CaseWorkflowService":
        from app.domain.cases.case_workflow_service import CaseWorkflowService
        return CaseWorkflowService
    if name == "CaseAttentionService":
        from app.domain.cases.case_attention_service import CaseAttentionService
        return CaseAttentionService
    if name == "CaseIntelligenceService":
        from app.domain.cases.case_intelligence_service import CaseIntelligenceService
        return CaseIntelligenceService
    if name == "CaseReportService":
        from app.domain.cases.case_report_service import CaseReportService
        return CaseReportService
    if name == "CollaborationService":
        from app.domain.cases.collaboration_service import CollaborationService
        return CollaborationService
    if name == "BundleService":
        from app.domain.cases.bundle_service import BundleService
        return BundleService
    if name == "BundlePdfEngine":
        from app.domain.cases.bundle_pdf_engine import BundlePdfEngine
        return BundlePdfEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
