from unittest.mock import MagicMock, patch

import openai
import pytest

from app.core.config import settings
from app.core.exceptions import AppException
from app.domain.ai.embedding_service import EmbeddingService


@pytest.fixture
def mock_settings():
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "test-key"
    settings.OPENAI_MAX_RETRIES = 2
    yield settings
    settings.OPENAI_API_KEY = original_key


@patch("openai.OpenAI")
def test_embedding_service_success(mock_openai, mock_settings):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_data1 = MagicMock()
    mock_data1.embedding = [0.1, 0.2, 0.3]
    mock_data2 = MagicMock()
    mock_data2.embedding = [0.4, 0.5, 0.6]
    mock_response.data = [mock_data1, mock_data2]

    mock_client.embeddings.create.return_value = mock_response

    service = EmbeddingService()
    embeddings = service.generate_embeddings(["text 1", "text 2"])

    assert len(embeddings) == 2
    assert embeddings[0] == [0.1, 0.2, 0.3]
    assert mock_client.embeddings.create.call_count == 1


@patch("time.sleep")
@patch("openai.OpenAI")
def test_embedding_service_retries_on_timeout(mock_openai, mock_sleep, mock_settings):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_client.embeddings.create.side_effect = [
        openai.APITimeoutError(request=MagicMock()),
        openai.APITimeoutError(request=MagicMock()),
        openai.APITimeoutError(request=MagicMock()),
    ]

    service = EmbeddingService()
    with pytest.raises(AppException) as exc:
        service.generate_embeddings(["text"])

    assert exc.value.status_code == 504
    assert mock_client.embeddings.create.call_count == 3
    assert mock_sleep.call_count == 2


@patch("openai.OpenAI")
def test_embedding_service_auth_error_no_retry(mock_openai, mock_settings):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_client.embeddings.create.side_effect = openai.AuthenticationError(
        message="Invalid token", response=MagicMock(), body=None
    )

    service = EmbeddingService()
    with pytest.raises(AppException) as exc:
        service.generate_embeddings(["text"])

    assert exc.value.status_code == 500
    assert mock_client.embeddings.create.call_count == 1
