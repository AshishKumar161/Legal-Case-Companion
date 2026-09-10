import logging

from app.domain.ai.embedding_provider import (
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings using an abstract EmbeddingProvider.

    Handles timeouts, transient errors, and exponential backoff retries.
    """

    def __init__(self, provider: EmbeddingProvider | None = None):
        self.provider = provider or get_embedding_provider()
        # Expose OpenAI properties if provider is OpenAIEmbeddingProvider (backward compatibility for tests)
        if isinstance(self.provider, OpenAIEmbeddingProvider):
            self.client = self.provider.client
            self.model = self.provider.model
            self.max_retries = self.provider.max_retries

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generates embeddings for a batch of text chunks via the provider."""
        if not texts:
            return []
        return self.provider.generate_embeddings(texts)
