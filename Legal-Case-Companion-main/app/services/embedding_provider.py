import hashlib
import logging
import math
import time
from typing import Protocol

import openai

from app.core.config import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Protocol defining the embedding generation interface."""

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbeddingProvider:
    """Production embedding provider utilizing OpenAI API with retry logic and error encapsulation."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ):
        key = api_key or settings.OPENAI_API_KEY
        if not key:
            raise AppException(
                status_code=500,
                code="EMBEDDING_MISCONFIGURED",
                message="OpenAI API key is missing.",
            )

        self.model = model or settings.EMBEDDING_MODEL
        self.timeout = timeout if timeout is not None else settings.EMBEDDING_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.OPENAI_MAX_RETRIES
        self.client = openai.OpenAI(api_key=key, timeout=self.timeout)

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        attempts = 0
        while attempts <= self.max_retries:
            try:
                response = self.client.embeddings.create(input=texts, model=self.model)
                return [item.embedding for item in response.data]

            except openai.RateLimitError as e:
                attempts += 1
                if attempts > self.max_retries:
                    logger.error("OpenAI embedding generation failed: RateLimitError exceeded max retries.")
                    raise AppException(
                        status_code=429,
                        code="EMBEDDING_RATE_LIMIT",
                        message="Too many requests to the AI provider.",
                    ) from e
                time.sleep(2**attempts)

            except openai.APITimeoutError as e:
                attempts += 1
                if attempts > self.max_retries:
                    logger.error("OpenAI embedding generation failed: APITimeoutError exceeded max retries.")
                    raise AppException(
                        status_code=504,
                        code="EMBEDDING_TIMEOUT",
                        message="The AI provider took too long to respond.",
                    ) from e
                time.sleep(2**attempts)

            except openai.APIConnectionError as e:
                attempts += 1
                if attempts > self.max_retries:
                    logger.error("OpenAI embedding generation failed: APIConnectionError exceeded max retries.")
                    raise AppException(
                        status_code=502,
                        code="EMBEDDING_CONNECTION_ERROR",
                        message="Failed to connect to the AI provider.",
                    ) from e
                time.sleep(2**attempts)

            except openai.AuthenticationError as e:
                logger.error("OpenAI Authentication failed. Check configured API key.")
                raise AppException(
                    status_code=500,
                    code="EMBEDDING_AUTH_ERROR",
                    message="Internal AI configuration error.",
                ) from e

            except openai.BadRequestError as e:
                logger.error(f"OpenAI BadRequestError during embedding generation: {e}")
                raise AppException(
                    status_code=400,
                    code="EMBEDDING_BAD_REQUEST",
                    message=f"Invalid embedding request: {e}",
                ) from e

            except Exception as e:
                logger.exception("Unexpected error during OpenAI embedding generation")
                raise AppException(
                    status_code=500,
                    code="EMBEDDING_FAILED",
                    message="Failed to generate embeddings.",
                ) from e

        raise AppException(
            status_code=500,
            code="EMBEDDING_FAILED",
            message="Failed to generate embeddings after retries.",
        )


class DeterministicMockEmbeddingProvider:
    """Mock embedding provider generating deterministic normalized vectors from text hashes for tests."""

    def __init__(self, dimensions: int = 1536):
        self.dimensions = dimensions

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        results: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimensions
            clean_text = text.strip().lower()
            if not clean_text:
                results.append(vector)
                continue

            # Generate pseudo-random deterministic weights based on word hashes
            words = clean_text.split()
            for word in words:
                h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
                for i in range(min(16, self.dimensions)):
                    idx = (h + i * 97) % self.dimensions
                    weight = ((h >> (i * 4)) & 0xFF) / 255.0
                    vector[idx] += weight

            # Normalize to unit vector
            norm = math.sqrt(sum(v * v for v in vector))
            if norm > 0.0:
                vector = [v / norm for v in vector]
            results.append(vector)

        return results


def get_embedding_provider() -> EmbeddingProvider:
    """Factory creating the appropriate EmbeddingProvider based on application configuration."""
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "dummy-test-key":
        return DeterministicMockEmbeddingProvider()
    return OpenAIEmbeddingProvider()
