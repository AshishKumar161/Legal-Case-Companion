"""Evidence Locker & Security Scanning Domain package."""

from typing import Any

__all__ = ["EvidenceService", "ScannerService", "MalwareScanner", "HeuristicSignatureScanner", "ClamAVScanner", "DefaultMalwareScanner"]


def __getattr__(name: str) -> Any:
    if name == "EvidenceService":
        from app.domain.evidence.evidence_service import EvidenceService
        return EvidenceService
    if name in ("ScannerService", "MalwareScanner", "HeuristicSignatureScanner", "ClamAVScanner", "DefaultMalwareScanner"):
        import app.domain.evidence.scanner_service as s
        return getattr(s, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
