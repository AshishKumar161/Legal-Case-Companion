"""
LCC AI/Model Backend Package.
Provides autonomous, grounded legal AI pipeline for Indian criminal law.
"""

from .pipeline import LegalAssistant, PipelineConfig
from .llama_model import LLaMAModel, LLaMAConfig
from .schemas import (
    LegalAssistantResponse,
    IntakeResult,
    LegalIssue,
    RetrievedSource,
    RerankedCandidate,
    GeneratedAnswer,
    VerificationResult,
    LegalCategory,
    LegalCaseRecord,
)

__all__ = [
    "LegalAssistant",
    "PipelineConfig",
    "LLaMAConfig",
    "LLaMAModel",
    "LegalAssistantResponse",
    "IntakeResult",
    "LegalIssue",
    "RetrievedSource",
    "RerankedCandidate",
    "GeneratedAnswer",
    "VerificationResult",
    "LegalCategory",
    "LegalCaseRecord",
]
