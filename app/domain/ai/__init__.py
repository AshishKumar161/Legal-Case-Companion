"""AI, LLM Orchestration & Legal Intelligence Domain package."""

import importlib
from typing import Any

__all__ = ['AIBudgetService', 'AIConversationService', 'AIEvaluationService', 'AIProvider', 'AIResearchService', 'AIReviewService', 'CaseAssistantService', 'ClaimVerificationService', 'DeterministicMockEmbeddingProvider', 'EmbeddingProvider', 'EmbeddingService', 'LLMProvider', 'LegalAuthorityIngestionService', 'LegalAuthorityRetrievalService', 'LegalCitationNormalizer', 'LegalDataPipeline', 'MockLLMProvider', 'NormalizedLegalCitation', 'OpenAIEmbeddingProvider', 'OpenAILLMProvider', 'ProductionOpenAIProvider', 'PromptSecurityPolicy', 'QueryUnderstandingService', 'RetrievalService', 'SafeContextBuilder', 'StructuredLegalQuery', 'StubAIProvider', 'check_prompt_injection', 'cosine_similarity', 'generate_conversation_title', 'get_ai_provider', 'get_embedding_provider', 'get_llm_provider', 'sanitize_untrusted_prompt_text']

_MODULE_MAP = {
    "AIConversationService": "ai_conversation_service",
    "check_prompt_injection": "ai_conversation_service",
    "generate_conversation_title": "ai_conversation_service",
    "AIResearchService": "ai_research_service",
    "CaseAssistantService": "assistant_service",
    "AIBudgetService": "ai_budget_service",
    "AIReviewService": "ai_review_service",
    "AIEvaluationService": "ai_evaluation_service",
    "PromptSecurityPolicy": "ai_prompt_policy",
    "SafeContextBuilder": "ai_prompt_policy",
    "AIProvider": "ai_provider",
    "StubAIProvider": "ai_provider",
    "ProductionOpenAIProvider": "ai_provider",
    "sanitize_untrusted_prompt_text": "ai_provider",
    "get_ai_provider": "ai_provider",
    "LLMProvider": "llm_provider",
    "MockLLMProvider": "llm_provider",
    "OpenAILLMProvider": "llm_provider",
    "get_llm_provider": "llm_provider",
    "EmbeddingProvider": "embedding_provider",
    "OpenAIEmbeddingProvider": "embedding_provider",
    "DeterministicMockEmbeddingProvider": "embedding_provider",
    "get_embedding_provider": "embedding_provider",
    "EmbeddingService": "embedding_service",
    "RetrievalService": "retrieval_service",
    "cosine_similarity": "retrieval_service",
    "LegalDataPipeline": "legal_data_pipeline",
    "LegalAuthorityRetrievalService": "legal_authority_retrieval",
    "LegalAuthorityIngestionService": "legal_authority_ingestion",
    "LegalCitationNormalizer": "citation_normalizer",
    "NormalizedLegalCitation": "citation_normalizer",
    "ClaimVerificationService": "claim_verifier",
    "QueryUnderstandingService": "query_understanding",
    "StructuredLegalQuery": "query_understanding",
}


def __getattr__(name: str) -> Any:
    mod_name = _MODULE_MAP.get(name)
    if mod_name:
        mod = importlib.import_module(f"app.domain.ai.{mod_name}")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
