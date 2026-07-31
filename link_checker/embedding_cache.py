"""Content-addressed embedding cache for Phase 2.

Caches page embeddings by a SHA-256 hash of the extracted text, so a
scheduled nightly crawl doesn't recompute embeddings for pages that
haven't changed. This matters more for LinkCanary than for a one-off
desktop audit, since LinkCanary runs are frequent and unattended, and
cloud providers (OpenAI, Gemini) charge per token.

The cache is persisted as a JSON file alongside the report:

    {
      "version": 1,
      "model": "nomic-embed-text",
      "provider": "ollama",
      "entries": {
        "<sha256-hex>": {
          "vector": [0.1, 0.2, ...],
          "url": "https://example.com/page/",
          "cached_at": "2026-07-29T12:00:00"
        }
      }
    }

Cache invalidates when:
  - the content hash changes (different page text), or
  - the model or provider changes (vectors from different models are not
    comparable).

If the model/provider in the cache file doesn't match the current run,
the cache is treated as empty (a model switch implies re-embedding everything).
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_FORMAT_VERSION = 1


def content_hash(text: str) -> str:
    """SHA-256 hex digest of the extracted page text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingCache:
    """Content-addressed embedding cache backed by a JSON file.

    Usage:
        cache = EmbeddingCache("/path/to/cache.json", model="...", provider="...")
        cache.load()
        # For each page:
        vec = cache.get(text_hash)        # None if miss
        if vec is None:
            vec = provider.embed([text])[0]
            cache.put(text_hash, url, vec)
        cache.save()
    """

    def __init__(self, path: str, model: str, provider: str):
        self.path = Path(path)
        self.model = model
        self.provider = provider
        # entries: hash -> {"vector": [...], "url": str, "cached_at": str}
        self._entries: dict[str, dict] = {}
        self._dirty = False
        self._loaded = False

    def load(self) -> None:
        """Load the cache from disk. If the file doesn't exist or the
        model/provider doesn't match, start with an empty cache."""
        self._loaded = True
        if not self.path.exists():
            self._entries = {}
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Embedding cache unreadable (%s): starting empty", exc)
            self._entries = {}
            return

        cached_model = data.get("model")
        cached_provider = data.get("provider")
        if cached_model != self.model or cached_provider != self.provider:
            logger.info(
                "Embedding cache model/provider mismatch "
                "(cached %s/%s vs current %s/%s): re-embedding all pages",
                cached_provider, cached_model, self.provider, self.model,
            )
            self._entries = {}
            self._dirty = True  # will rewrite with new model/provider
            return

        self._entries = data.get("entries", {})
        self._dirty = False

    def get(self, text_hash: str) -> Optional[list[float]]:
        """Return the cached vector for a content hash, or None on miss."""
        entry = self._entries.get(text_hash)
        if entry is None:
            return None
        return entry.get("vector")

    def put(self, text_hash: str, url: str, vector: list[float]) -> None:
        """Store a vector in the cache, keyed by content hash."""
        self._entries[text_hash] = {
            "vector": vector,
            "url": url,
            "cached_at": datetime.utcnow().isoformat(timespec="seconds"),
        }
        self._dirty = True

    def save(self) -> None:
        """Persist the cache to disk if there are unsaved changes."""
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": CACHE_FORMAT_VERSION,
            "model": self.model,
            "provider": self.provider,
            "entries": self._entries,
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self._dirty = False
        logger.info("Embedding cache saved to %s (%d entries)", self.path, len(self._entries))

    @property
    def size(self) -> int:
        return len(self._entries)

    def stats(self) -> dict:
        """Return hit/miss stats (populated by the caller via counters)."""
        return {"entries": len(self._entries)}
