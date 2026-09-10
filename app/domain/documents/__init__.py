"""Documents Domain package."""

from typing import Any

__all__ = ["DocumentService", "DocumentProcessor", "ExtractedPageData", "LegalDocumentService"]


def __getattr__(name: str) -> Any:
    if name == "DocumentService":
        from app.domain.documents.document_service import DocumentService
        return DocumentService
    if name in ("DocumentProcessor", "ExtractedPageData"):
        from app.domain.documents.document_processor import DocumentProcessor, ExtractedPageData
        return DocumentProcessor if name == 'DocumentProcessor' else ExtractedPageData
    if name == "LegalDocumentService":
        from app.domain.documents.legal_document_service import LegalDocumentService
        return LegalDocumentService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
