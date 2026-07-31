"""Tests for the run-history persistence and new-vs-persistent diffing."""

import json

from link_checker.embedding_history import (
    EmbeddingHistory,
    count_resolved_outliers,
    count_resolved_pairs,
    diff_outliers,
    diff_pairs,
)
from link_checker.similarity import OutlierResult, SimilarityPair


class TestEmbeddingHistory:

    def test_empty_history_no_prior(self, tmp_path):
        h = EmbeddingHistory(str(tmp_path / "h.json"), model="m", provider="ollama")
        h.load()
        pairs, outliers = h.prior_findings()
        assert pairs == set()
        assert outliers == set()
        assert h.run_count == 0

    def test_record_and_reload(self, tmp_path):
        path = str(tmp_path / "h.json")
        h = EmbeddingHistory(path, model="m", provider="ollama")
        h.load()
        h.record_run(
            pairs=[SimilarityPair(url_a="https://a.com/", url_b="https://b.com/", similarity=0.99)],
            outliers=[OutlierResult(url="https://c.com/", distance_from_centroid=0.8)],
        )
        h.save()
        assert h.run_count == 1

        h2 = EmbeddingHistory(path, model="m", provider="ollama")
        h2.load()
        assert h2.run_count == 1
        prior_pairs, prior_outliers = h2.prior_findings()
        assert prior_pairs == {("https://a.com/", "https://b.com/")}
        assert prior_outliers == {"https://c.com/"}

    def test_pair_fingerprint_order_independent(self, tmp_path):
        path = str(tmp_path / "h.json")
        h = EmbeddingHistory(path, model="m", provider="ollama")
        h.load()
        h.record_run(
            pairs=[SimilarityPair(url_a="https://b.com/", url_b="https://a.com/", similarity=0.99)],
            outliers=[],
        )
        h.save()

        h2 = EmbeddingHistory(path, model="m", provider="ollama")
        h2.load()
        prior_pairs, _ = h2.prior_findings()
        # Stored as sorted tuple, so (a, b) not (b, a)
        assert prior_pairs == {("https://a.com/", "https://b.com/")}

    def test_model_mismatch_invalidates(self, tmp_path):
        path = str(tmp_path / "h.json")
        h = EmbeddingHistory(path, model="model-a", provider="ollama")
        h.load()
        h.record_run(
            pairs=[SimilarityPair("https://a.com/", "https://b.com/", 0.99)],
            outliers=[],
        )
        h.save()

        h2 = EmbeddingHistory(path, model="model-b", provider="ollama")
        h2.load()
        assert h2.run_count == 0
        assert h2.prior_findings() == (set(), set())

    def test_provider_mismatch_invalidates(self, tmp_path):
        path = str(tmp_path / "h.json")
        h = EmbeddingHistory(path, model="m", provider="ollama")
        h.load()
        h.record_run(
            pairs=[SimilarityPair("https://a.com/", "https://b.com/", 0.99)],
            outliers=[],
        )
        h.save()

        h2 = EmbeddingHistory(path, model="m", provider="openai")
        h2.load()
        assert h2.run_count == 0

    def test_max_runs_trim(self, tmp_path):
        path = str(tmp_path / "h.json")
        h = EmbeddingHistory(path, model="m", provider="ollama", max_runs=3)
        h.load()
        for i in range(5):
            h.record_run(
                pairs=[SimilarityPair(f"https://a{i}.com/", f"https://b{i}.com/", 0.99)],
                outliers=[],
            )
        h.save()
        assert h.run_count == 3  # trimmed to max_runs

        # The most recent 3 should be kept
        h2 = EmbeddingHistory(path, model="m", provider="ollama", max_runs=3)
        h2.load()
        assert h2.run_count == 3
        prior_pairs, _ = h2.prior_findings()
        # Last run was i=4
        assert ("https://a4.com/", "https://b4.com/") in prior_pairs

    def test_unreadable_file_starts_empty(self, tmp_path):
        path = str(tmp_path / "h.json")
        with open(path, "w") as f:
            f.write("{broken json")
        h = EmbeddingHistory(path, model="m", provider="ollama")
        h.load()
        assert h.run_count == 0

    def test_save_creates_parent_dirs(self, tmp_path):
        path = str(tmp_path / "sub" / "deep" / "h.json")
        h = EmbeddingHistory(path, model="m", provider="ollama")
        h.load()
        h.record_run([], [])
        h.save()
        import os
        assert os.path.exists(path)

    def test_file_format(self, tmp_path):
        path = str(tmp_path / "h.json")
        h = EmbeddingHistory(path, model="my-model", provider="gemini")
        h.load()
        h.record_run(
            pairs=[SimilarityPair("https://a.com/", "https://b.com/", 0.95)],
            outliers=[OutlierResult("https://c.com/", 0.7)],
        )
        h.save()
        with open(path) as f:
            data = json.load(f)
        assert data["version"] == 1
        assert data["model"] == "my-model"
        assert data["provider"] == "gemini"
        assert len(data["runs"]) == 1
        assert data["runs"][0]["pairs"] == [["https://a.com/", "https://b.com/"]]
        assert data["runs"][0]["outliers"] == ["https://c.com/"]


class TestDiffPairs:

    def test_new_pair_tagged_new(self):
        pairs = [SimilarityPair("https://a.com/", "https://b.com/", 0.99)]
        diff_pairs(pairs, prior_fingerprints=set())
        assert pairs[0].status == "new"

    def test_persistent_pair_tagged_persistent(self):
        pairs = [SimilarityPair("https://a.com/", "https://b.com/", 0.99)]
        prior = {("https://a.com/", "https://b.com/")}
        diff_pairs(pairs, prior)
        assert pairs[0].status == "persistent"

    def test_order_independent_matching(self):
        # Pair stored as (a, b) but current is (b, a) should still match
        pairs = [SimilarityPair("https://b.com/", "https://a.com/", 0.99)]
        prior = {("https://a.com/", "https://b.com/")}
        diff_pairs(pairs, prior)
        assert pairs[0].status == "persistent"

    def test_mixed_new_and_persistent(self):
        pairs = [
            SimilarityPair("https://a.com/", "https://b.com/", 0.99),
            SimilarityPair("https://c.com/", "https://d.com/", 0.98),
        ]
        prior = {("https://a.com/", "https://b.com/")}
        diff_pairs(pairs, prior)
        assert pairs[0].status == "persistent"
        assert pairs[1].status == "new"


class TestDiffOutliers:

    def test_new_outlier(self):
        outliers = [OutlierResult("https://x.com/", 0.8)]
        diff_outliers(outliers, prior_outlier_urls=set())
        assert outliers[0].status == "new"

    def test_persistent_outlier(self):
        outliers = [OutlierResult("https://x.com/", 0.8)]
        diff_outliers(outliers, prior_outlier_urls={"https://x.com/"})
        assert outliers[0].status == "persistent"


class TestCountResolved:

    def test_resolved_pairs(self):
        pairs = [SimilarityPair("https://a.com/", "https://b.com/", 0.99)]
        prior = {("https://a.com/", "https://b.com/"), ("https://c.com/", "https://d.com/")}
        assert count_resolved_pairs(pairs, prior) == 1

    def test_no_resolved_when_all_persist(self):
        pairs = [SimilarityPair("https://a.com/", "https://b.com/", 0.99)]
        prior = {("https://a.com/", "https://b.com/")}
        assert count_resolved_pairs(pairs, prior) == 0

    def test_resolved_outliers(self):
        outliers = [OutlierResult("https://x.com/", 0.8)]
        prior = {"https://x.com/", "https://y.com/"}
        assert count_resolved_outliers(outliers, prior) == 1
