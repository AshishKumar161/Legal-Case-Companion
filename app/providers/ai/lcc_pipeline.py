"""LCC AI Provider Pipeline Integration.

Wraps the actual LegalAssistant agentic pipeline in the canonical AIProvider protocol.
"""

import logging
from typing import Any

from app.providers.ai.base import AIProvider, AIResearchResponse
from app.schemas.retrieval import RetrievedChunk
from chatbot.model_backend.pipeline import LegalAssistant, PipelineConfig
from chatbot.model_backend.llama_model import LLaMAConfig

logger = logging.getLogger(__name__)


class CanonicalLCCPipelineProvider(AIProvider):
    """Canonical integration of the LCC multi-agent backend pipeline."""

    def __init__(self):
        # By passing no kwargs, LLaMAConfig auto-discovers if it can use Groq or OpenAI or Mock
        # We can also explicitly force something if we want, but auto is fine.
        config = PipelineConfig(
            llama_config=LLaMAConfig(),
            auto_index=True
        )
        try:
            self.assistant = LegalAssistant(config=config)
            self.model = getattr(self.assistant.llm.config, "model_name", "lcc-pipeline")
        except Exception as e:
            logger.error("Failed to initialize LegalAssistant: %s", e)
            raise e
        self.provider_name = "LCC_Pipeline"
        logger.info(f"Initialized CanonicalLCCPipelineProvider with model {self.model}")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Executes raw text generation using the underlying LLaMA model."""
        return self.assistant.llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=False
        )

    def generate_structured_response(
        self,
        system_prompt: str,
        user_prompt: str,
        candidate_chunks: list[Any] | None = None,
        authority_provisions: list[Any] | None = None,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generates a structured JSON response verified against evidentiary sources."""
        # We can extract conversation_history from kwargs if passed
        conversation_history = kwargs.get("conversation_history", None)
        
        # If user_prompt contains "Previous conversation", it was already injected by advisor.py
        # But we prefer to pass the raw payload.message if possible.
        # If we just have user_prompt, we will pass it as query.
        
        query = kwargs.get("original_message", user_prompt)

        try:
            response = self.assistant.ask(
                query=query,
                conversation_history=conversation_history
            )
            return response.model_dump()
        except Exception as e:
            logger.error("LCC Pipeline failed during structured response generation: %s", e)
            return {
                "answer": "An error occurred while processing your request through the Legal Case Companion AI pipeline.",
                "verified": False
            }

    def generate_research_response(
        self,
        system_prompt: str,
        user_query: str,
        chunks: list[RetrievedChunk],
    ) -> AIResearchResponse:
        """Fallback implementation for AIResearchResponse."""
        raise NotImplementedError("LCCPipelineProvider does not support raw research response generation.")

    def health_check(self) -> bool:
        """Verifies provider connectivity."""
        try:
            return self.assistant is not None
        except Exception:
            return False
