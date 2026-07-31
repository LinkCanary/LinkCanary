"""Embedding providers for semantic-duplicate detection.

A single interface (`EmbeddingProvider`) sits in front of every backend so
the similarity/comparison code in `similarity.py` is provider-agnostic.

Phase 1 ships only `OllamaProvider` (local, no API key, no per-page cost,
matches LinkCanary's self-hosted/MIT story). OpenAI and Gemini providers
are planned for Phase 2 and will slot in behind the same ABC.

Ollama's embed endpoint is `POST {base_url}/api/embed` with a JSON body
`{"model": "...", "input": ["text1", "text2", ...]}` and returns
`{"embeddings": [[...], [...]]}`. We batch pages to keep payloads small.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Default Ollama endpoint. Overridable via --ollama-url / OLLAMA_URL.
DEFAULT_OLLAMA_URL = "http://localhost:11434"

# Default model. Pulled locally via `ollama pull nomic-embed-text`.
DEFAULT_OLLAMA_MODEL = "nomic-embed-text"

# Batch size: number of texts sent per /api/embed request. Keeps request
# bodies predictable; Ollama handles larger batches but very large
# payloads can hit HTTP body limits or slow the event loop.
DEFAULT_BATCH_SIZE = 16

# Per-request timeout for the embed call. Embedding is CPU-bound on
# Ollama; 120s is a generous ceiling for a batch of 16 pages.
DEFAULT_TIMEOUT = 120


class EmbeddingProvider(ABC):
    """Interface every embedding backend implements."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts and return one vector per text.

        Args:
            texts: List of plain-text strings (already extracted/truncated).

        Returns:
            List of embedding vectors in the same order as `texts`. Each
            vector is a list of floats. If a provider error makes it
            impossible to embed any text, implementations should raise
            `EmbeddingError`; partial failures should log and return
            zero-length placeholders so the caller can degrade gracefully.
        """
        raise NotImplementedError

    def close(self) -> None:
        """Release any underlying sessions/connections. Default: no-op."""
        return


class EmbeddingError(RuntimeError):
    """Raised when an embedding provider cannot produce vectors."""


class OllamaProvider(EmbeddingProvider):
    """Local Ollama embedding provider (default, no API key)."""

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_URL,
        model: str = DEFAULT_OLLAMA_MODEL,
        batch_size: int = DEFAULT_BATCH_SIZE,
        timeout: int = DEFAULT_TIMEOUT,
        user_agent: str = "LinkCanary/1.0",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.batch_size = max(1, batch_size)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        payload = {"model": self.model, "input": batch}
        url = f"{self.base_url}/api/embed"
        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise EmbeddingError(
                f"Ollama embed request failed ({url}): {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise EmbeddingError(f"Ollama returned non-JSON response: {exc}") from exc

        vectors = data.get("embeddings")
        if not vectors or len(vectors) != len(batch):
            raise EmbeddingError(
                f"Ollama returned {len(vectors) if vectors else 0} vectors "
                f"for {len(batch)} inputs"
            )
        return [list(map(float, vec)) for vec in vectors]

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            vectors.extend(self._embed_batch(batch))
        return vectors

    def close(self) -> None:
        self.session.close()


# --- Cloud providers (Phase 2) -----------------------------------------------

DEFAULT_OPENAI_MODEL = "text-embedding-3-small"
DEFAULT_OPENAI_URL = "https://api.openai.com/v1/embeddings"

DEFAULT_GEMINI_MODEL = "gemini-embedding-001"
DEFAULT_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


class OpenAIProvider(EmbeddingProvider):
    """OpenAI Embeddings API provider (cloud, requires OPENAI_API_KEY)."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_OPENAI_MODEL,
        batch_size: int = DEFAULT_BATCH_SIZE,
        timeout: int = DEFAULT_TIMEOUT,
        user_agent: str = "LinkCanary/1.0",
        base_url: str = DEFAULT_OPENAI_URL,
    ):
        if not api_key:
            raise EmbeddingError(
                "OpenAI provider requires OPENAI_API_KEY (set the env var "
                "or pass --openai-api-key)."
            )
        self.model = model
        self.batch_size = max(1, batch_size)
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        })

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        payload = {"model": self.model, "input": batch}
        try:
            response = self.session.post(
                self.base_url, json=payload, timeout=self.timeout
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise EmbeddingError(f"OpenAI embed request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise EmbeddingError(f"OpenAI returned non-JSON response: {exc}") from exc

        items = data.get("data")
        if not items or len(items) != len(batch):
            raise EmbeddingError(
                f"OpenAI returned {len(items) if items else 0} vectors "
                f"for {len(batch)} inputs"
            )
        # Sort by index to guarantee order matches the input batch.
        items_sorted = sorted(items, key=lambda d: d.get("index", 0))
        return [list(map(float, item["embedding"])) for item in items_sorted]

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            vectors.extend(self._embed_batch(batch))
        return vectors

    def close(self) -> None:
        self.session.close()


class GeminiProvider(EmbeddingProvider):
    """Google Gemini Embeddings API provider (cloud, requires GEMINI_API_KEY).

    Uses the ``embedContent`` REST endpoint with multiple ``parts`` for batching.
    The ``taskType`` is set to ``SEMANTIC_SIMILARITY`` which is the right task
    type for near-duplicate / outlier detection.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_GEMINI_MODEL,
        batch_size: int = DEFAULT_BATCH_SIZE,
        timeout: int = DEFAULT_TIMEOUT,
        user_agent: str = "LinkCanary/1.0",
        base_url: str = DEFAULT_GEMINI_BASE,
    ):
        if not api_key:
            raise EmbeddingError(
                "Gemini provider requires GEMINI_API_KEY (set the env var "
                "or pass --gemini-api-key)."
            )
        self.model = model
        self.batch_size = max(1, batch_size)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
            "User-Agent": user_agent,
        })

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        url = f"{self.base_url}/models/{self.model}:embedContent"
        payload = {
            "taskType": "SEMANTIC_SIMILARITY",
            "content": {"parts": [{"text": text} for text in batch]},
        }
        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise EmbeddingError(f"Gemini embed request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise EmbeddingError(f"Gemini returned non-JSON response: {exc}") from exc

        # embedContent may return "embeddings" (list) or "embedding" (single).
        embeddings = data.get("embeddings")
        if embeddings is None and "embedding" in data:
            embeddings = [data["embedding"]]
        if not embeddings or len(embeddings) != len(batch):
            raise EmbeddingError(
                f"Gemini returned {len(embeddings) if embeddings else 0} vectors "
                f"for {len(batch)} inputs"
            )
        return [list(map(float, emb["values"])) for emb in embeddings]

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            vectors.extend(self._embed_batch(batch))
        return vectors

    def close(self) -> None:
        self.session.close()


def get_provider(
    name: str,
    *,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_OLLAMA_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    timeout: int = DEFAULT_TIMEOUT,
    user_agent: str = "LinkCanary/1.0",
    openai_api_key: str | None = None,
    gemini_api_key: str | None = None,
) -> EmbeddingProvider:
    """Factory for embedding providers by name.

    Supports "ollama" (local, default), "openai" (cloud, needs OPENAI_API_KEY),
    and "gemini" (cloud, needs GEMINI_API_KEY).
    """
    name_lower = (name or "").lower().strip()
    if name_lower == "ollama":
        return OllamaProvider(
            base_url=ollama_url,
            model=model,
            batch_size=batch_size,
            timeout=timeout,
            user_agent=user_agent,
        )
    if name_lower == "openai":
        return OpenAIProvider(
            api_key=openai_api_key or "",
            model=model,
            batch_size=batch_size,
            timeout=timeout,
            user_agent=user_agent,
        )
    if name_lower == "gemini":
        return GeminiProvider(
            api_key=gemini_api_key or "",
            model=model,
            batch_size=batch_size,
            timeout=timeout,
            user_agent=user_agent,
        )
    raise EmbeddingError(
        f"Unknown embeddings provider: {name!r}. "
        f"Supported: 'ollama', 'openai', 'gemini'."
    )
