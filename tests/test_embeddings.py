"""Tests for the embedding provider interface and Ollama/OpenAI/Gemini backends."""

from unittest.mock import MagicMock, patch

import pytest

from link_checker.embeddings import (
    EmbeddingError,
    EmbeddingProvider,
    GeminiProvider,
    OllamaProvider,
    OpenAIProvider,
    get_provider,
)


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestOllamaProvider:

    def test_embed_single_batch(self):
        provider = OllamaProvider(base_url="http://localhost:11434")
        mock_resp = _mock_response({
            "embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        })
        with patch.object(provider.session, "post", return_value=mock_resp) as mock_post:
            vectors = provider.embed(["hello", "world"])
        assert len(vectors) == 2
        assert vectors[0] == [0.1, 0.2, 0.3]
        assert vectors[1] == [0.4, 0.5, 0.6]
        # Verify the request payload
        call_args = mock_post.call_args
        assert call_args.kwargs["json"]["model"] == "nomic-embed-text"
        assert call_args.kwargs["json"]["input"] == ["hello", "world"]
        assert call_args.args[0].endswith("/api/embed")
        provider.close()

    def test_embed_batches_multiple_requests(self):
        provider = OllamaProvider(batch_size=2)
        responses = [
            _mock_response({"embeddings": [[0.1, 0.2], [0.3, 0.4]]}),
            _mock_response({"embeddings": [[0.5, 0.6]]}),
        ]
        with patch.object(provider.session, "post", side_effect=responses) as mock_post:
            vectors = provider.embed(["a", "b", "c"])
        assert len(vectors) == 3
        assert vectors[2] == [0.5, 0.6]
        assert mock_post.call_count == 2
        provider.close()

    def test_embed_empty_list_returns_empty(self):
        provider = OllamaProvider()
        assert provider.embed([]) == []
        provider.close()

    def test_request_failure_raises_embedding_error(self):
        import requests
        provider = OllamaProvider()
        with patch.object(provider.session, "post", side_effect=requests.ConnectionError("nope")):
            with pytest.raises(EmbeddingError, match="Ollama embed request failed"):
                provider.embed(["hello"])
        provider.close()

    def test_vector_count_mismatch_raises(self):
        provider = OllamaProvider()
        mock_resp = _mock_response({"embeddings": [[0.1, 0.2]]})  # 1 vector for 2 inputs
        with patch.object(provider.session, "post", return_value=mock_resp):
            with pytest.raises(EmbeddingError, match="returned 1 vectors for 2 inputs"):
                provider.embed(["a", "b"])
        provider.close()

    def test_custom_model_and_url(self):
        provider = OllamaProvider(
            base_url="http://myhost:1234",
            model="custom-model",
        )
        mock_resp = _mock_response({"embeddings": [[0.1]]})
        with patch.object(provider.session, "post", return_value=mock_resp) as mock_post:
            provider.embed(["x"])
        call_args = mock_post.call_args
        assert call_args.args[0] == "http://myhost:1234/api/embed"
        assert call_args.kwargs["json"]["model"] == "custom-model"
        provider.close()


class TestGetProvider:

    def test_ollama_provider(self):
        provider = get_provider("ollama")
        assert isinstance(provider, OllamaProvider)
        provider.close()

    def test_ollama_provider_case_insensitive(self):
        provider = get_provider("OLLAMA")
        assert isinstance(provider, OllamaProvider)
        provider.close()

    def test_unknown_provider_raises(self):
        with pytest.raises(EmbeddingError, match="Unknown embeddings provider"):
            get_provider("claude")

    def test_empty_provider_raises(self):
        with pytest.raises(EmbeddingError, match="Unknown embeddings provider"):
            get_provider("")


class TestOpenAIProvider:

    def test_embed_single_batch(self):
        provider = OpenAIProvider(api_key="sk-test")
        mock_resp = _mock_response({
            "data": [
                {"embedding": [0.1, 0.2], "index": 0},
                {"embedding": [0.3, 0.4], "index": 1},
            ],
        })
        with patch.object(provider.session, "post", return_value=mock_resp) as mock_post:
            vectors = provider.embed(["hello", "world"])
        assert len(vectors) == 2
        assert vectors[0] == [0.1, 0.2]
        assert vectors[1] == [0.3, 0.4]
        call = mock_post.call_args
        assert call.kwargs["json"]["model"] == "text-embedding-3-small"
        assert call.kwargs["json"]["input"] == ["hello", "world"]
        provider.close()

    def test_sorts_by_index(self):
        provider = OpenAIProvider(api_key="sk-test")
        mock_resp = _mock_response({
            "data": [
                {"embedding": [0.3, 0.4], "index": 1},
                {"embedding": [0.1, 0.2], "index": 0},
            ],
        })
        with patch.object(provider.session, "post", return_value=mock_resp):
            vectors = provider.embed(["a", "b"])
        # Should be reordered by index
        assert vectors[0] == [0.1, 0.2]
        assert vectors[1] == [0.3, 0.4]
        provider.close()

    def test_missing_api_key_raises(self):
        with pytest.raises(EmbeddingError, match="OPENAI_API_KEY"):
            OpenAIProvider(api_key="")

    def test_request_failure_raises(self):
        import requests
        provider = OpenAIProvider(api_key="sk-test")
        with patch.object(provider.session, "post", side_effect=requests.ConnectionError("nope")):
            with pytest.raises(EmbeddingError, match="OpenAI embed request failed"):
                provider.embed(["hello"])
        provider.close()

    def test_auth_header_set(self):
        provider = OpenAIProvider(api_key="sk-secret")
        assert provider.session.headers["Authorization"] == "Bearer sk-secret"
        provider.close()


class TestGeminiProvider:

    def test_embed_batch_multiple_parts(self):
        provider = GeminiProvider(api_key="gem-key")
        mock_resp = _mock_response({
            "embeddings": [
                {"values": [0.1, 0.2]},
                {"values": [0.3, 0.4]},
            ],
        })
        with patch.object(provider.session, "post", return_value=mock_resp) as mock_post:
            vectors = provider.embed(["hello", "world"])
        assert len(vectors) == 2
        assert vectors[0] == [0.1, 0.2]
        assert vectors[1] == [0.3, 0.4]
        call = mock_post.call_args
        url = call.args[0]
        assert "embedContent" in url
        assert "gemini-embedding-001" in url
        body = call.kwargs["json"]
        assert body["taskType"] == "SEMANTIC_SIMILARITY"
        assert len(body["content"]["parts"]) == 2
        provider.close()

    def test_single_embedding_response_shape(self):
        provider = GeminiProvider(api_key="gem-key")
        mock_resp = _mock_response({
            "embedding": {"values": [0.5, 0.6]},
        })
        with patch.object(provider.session, "post", return_value=mock_resp):
            vectors = provider.embed(["one"])
        assert vectors == [[0.5, 0.6]]
        provider.close()

    def test_missing_api_key_raises(self):
        with pytest.raises(EmbeddingError, match="GEMINI_API_KEY"):
            GeminiProvider(api_key="")

    def test_request_failure_raises(self):
        import requests
        provider = GeminiProvider(api_key="gem-key")
        with patch.object(provider.session, "post", side_effect=requests.ConnectionError("nope")):
            with pytest.raises(EmbeddingError, match="Gemini embed request failed"):
                provider.embed(["hello"])
        provider.close()

    def test_api_key_header_set(self):
        provider = GeminiProvider(api_key="gem-secret")
        assert provider.session.headers["x-goog-api-key"] == "gem-secret"
        provider.close()


class TestGetProviderPhase2:

    def test_openai_provider(self):
        provider = get_provider("openai", openai_api_key="sk-test")
        assert isinstance(provider, OpenAIProvider)
        provider.close()

    def test_gemini_provider(self):
        provider = get_provider("gemini", gemini_api_key="gem-test")
        assert isinstance(provider, GeminiProvider)
        provider.close()

    def test_openai_without_key_raises_on_construction(self):
        with pytest.raises(EmbeddingError, match="OPENAI_API_KEY"):
            get_provider("openai")  # no key -> raises in __init__

    def test_gemini_without_key_raises_on_construction(self):
        with pytest.raises(EmbeddingError, match="GEMINI_API_KEY"):
            get_provider("gemini")
