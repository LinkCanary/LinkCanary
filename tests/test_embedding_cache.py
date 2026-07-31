"""Tests for the content-addressed embedding cache."""

import json

from link_checker.embedding_cache import EmbeddingCache, content_hash


class TestContentHash:

    def test_deterministic(self):
        assert content_hash("hello") == content_hash("hello")

    def test_different_inputs_differ(self):
        assert content_hash("hello") != content_hash("world")

    def test_hex_string(self):
        h = content_hash("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestEmbeddingCache:

    def test_miss_returns_none(self, tmp_path):
        cache = EmbeddingCache(str(tmp_path / "c.json"), model="m", provider="ollama")
        cache.load()
        assert cache.get(content_hash("nope")) is None

    def test_put_then_get(self, tmp_path):
        cache = EmbeddingCache(str(tmp_path / "c.json"), model="m", provider="ollama")
        cache.load()
        h = content_hash("page text")
        cache.put(h, "https://example.com/", [0.1, 0.2, 0.3])
        assert cache.get(h) == [0.1, 0.2, 0.3]

    def test_save_and_reload(self, tmp_path):
        path = str(tmp_path / "c.json")
        cache = EmbeddingCache(path, model="m", provider="ollama")
        cache.load()
        h = content_hash("page text")
        cache.put(h, "https://example.com/", [0.1, 0.2])
        cache.save()
        assert cache._dirty is False

        cache2 = EmbeddingCache(path, model="m", provider="ollama")
        cache2.load()
        assert cache2.get(h) == [0.1, 0.2]
        assert cache2.size == 1

    def test_model_mismatch_invalidates(self, tmp_path):
        path = str(tmp_path / "c.json")
        cache = EmbeddingCache(path, model="model-a", provider="ollama")
        cache.load()
        h = content_hash("page text")
        cache.put(h, "https://example.com/", [0.1, 0.2])
        cache.save()

        # Reload with a different model -> entries should be dropped
        cache2 = EmbeddingCache(path, model="model-b", provider="ollama")
        cache2.load()
        assert cache2.get(h) is None
        assert cache2.size == 0

    def test_provider_mismatch_invalidates(self, tmp_path):
        path = str(tmp_path / "c.json")
        cache = EmbeddingCache(path, model="m", provider="ollama")
        cache.load()
        cache.put(content_hash("x"), "https://example.com/", [0.1])
        cache.save()

        cache2 = EmbeddingCache(path, model="m", provider="openai")
        cache2.load()
        assert cache2.size == 0

    def test_unreadable_file_starts_empty(self, tmp_path):
        path = str(tmp_path / "c.json")
        with open(path, "w") as f:
            f.write("{not valid json")
        cache = EmbeddingCache(path, model="m", provider="ollama")
        cache.load()
        assert cache.size == 0

    def test_nonexistent_file_starts_empty(self, tmp_path):
        cache = EmbeddingCache(str(tmp_path / "missing.json"), model="m", provider="ollama")
        cache.load()
        assert cache.size == 0

    def test_save_creates_parent_dirs(self, tmp_path):
        path = str(tmp_path / "subdir" / "nested" / "c.json")
        cache = EmbeddingCache(path, model="m", provider="ollama")
        cache.load()
        cache.put(content_hash("x"), "url", [0.1])
        cache.save()
        import os
        assert os.path.exists(path)

    def test_save_only_writes_when_dirty(self, tmp_path):
        path = str(tmp_path / "c.json")
        cache = EmbeddingCache(path, model="m", provider="ollama")
        cache.load()
        # No puts -> save should be a no-op (file not created)
        cache.save()
        import os
        assert not os.path.exists(path)

    def test_cache_file_format(self, tmp_path):
        path = str(tmp_path / "c.json")
        cache = EmbeddingCache(path, model="my-model", provider="openai")
        cache.load()
        cache.put(content_hash("text"), "https://example.com/", [1.0, 2.0])
        cache.save()
        with open(path) as f:
            data = json.load(f)
        assert data["version"] == 1
        assert data["model"] == "my-model"
        assert data["provider"] == "openai"
        assert len(data["entries"]) == 1
