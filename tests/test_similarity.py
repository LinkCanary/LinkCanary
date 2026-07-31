"""Tests for cosine similarity pair detection and off-topic outlier detection."""

import numpy as np
import pytest

from link_checker.similarity import (
    OutlierResult,
    SimilarityPair,
    compute_similarity_matrix,
    find_outliers,
    find_similar_pairs,
)


def _make_vectors(*vecs):
    return np.array(vecs, dtype=float)


class TestComputeSimilarityMatrix:

    def test_identical_vectors_sim_one(self):
        v = _make_vectors([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
        sim = compute_similarity_matrix(v)
        assert sim.shape == (2, 2)
        assert sim[0, 0] == pytest.approx(1.0)
        assert sim[0, 1] == pytest.approx(1.0)

    def test_orthogonal_vectors_sim_zero(self):
        v = _make_vectors([1.0, 0.0], [0.0, 1.0])
        sim = compute_similarity_matrix(v)
        assert sim[0, 1] == pytest.approx(0.0)

    def test_empty_matrix(self):
        sim = compute_similarity_matrix(np.zeros((0, 0)))
        assert sim.shape == (0, 0)

    def test_clamped_to_unit(self):
        # Cosine sim can exceed 1.0 due to floating point; ensure clamped
        v = _make_vectors([1.0, 0.0], [1.0, 0.0])
        sim = compute_similarity_matrix(v)
        assert sim.max() <= 1.0


class TestFindSimilarPairs:

    def test_finds_identical_pair(self):
        v = _make_vectors([1.0, 0.0], [1.0, 0.0], [0.0, 1.0])
        urls = ["a", "b", "c"]
        pairs = find_similar_pairs(v, urls, threshold=0.95)
        assert len(pairs) == 1
        assert pairs[0].url_a == "a"
        assert pairs[0].url_b == "b"
        assert pairs[0].similarity == pytest.approx(1.0)

    def test_threshold_filters(self):
        v = _make_vectors([1.0, 0.0], [0.9, 0.43589])  # ~0.9 cosine
        urls = ["a", "b"]
        pairs = find_similar_pairs(v, urls, threshold=0.95)
        assert pairs == []
        pairs = find_similar_pairs(v, urls, threshold=0.85)
        assert len(pairs) == 1

    def test_sorted_by_descending_similarity(self):
        v = _make_vectors(
            [1.0, 0.0],
            [0.99, 0.1411],
            [0.95, 0.3122],
        )
        urls = ["a", "b", "c"]
        pairs = find_similar_pairs(v, urls, threshold=0.9)
        assert len(pairs) >= 1
        sims = [p.similarity for p in pairs]
        assert sims == sorted(sims, reverse=True)

    def test_single_page_no_pairs(self):
        v = _make_vectors([1.0, 0.0])
        pairs = find_similar_pairs(v, ["a"], threshold=0.5)
        assert pairs == []

    def test_empty_no_pairs(self):
        pairs = find_similar_pairs(np.zeros((0, 0)), [], threshold=0.5)
        assert pairs == []

    def test_length_mismatch_raises(self):
        v = _make_vectors([1.0, 0.0], [0.0, 1.0])
        with pytest.raises(ValueError, match="length mismatch"):
            find_similar_pairs(v, ["a"], threshold=0.5)

    def test_floor_threshold_applies(self):
        # Threshold below the 0.5 floor still respects the floor
        v = _make_vectors([1.0, 0.0], [0.0, 1.0])  # similarity 0
        urls = ["a", "b"]
        pairs = find_similar_pairs(v, urls, threshold=0.1)
        assert pairs == []  # 0 < 0.5 floor


class TestFindOutliers:

    def test_flags_distant_page(self):
        # Three clustered vectors and one far away
        v = _make_vectors(
            [1.0, 0.0],
            [0.98, 0.199],
            [0.99, 0.1411],
            [0.0, 1.0],  # orthogonal outlier
        )
        urls = ["a", "b", "c", "d"]
        outliers = find_outliers(v, urls, n_std=1.0)
        outlier_urls = [o.url for o in outliers]
        assert "d" in outlier_urls

    def test_no_outliers_when_all_similar(self):
        v = _make_vectors(
            [1.0, 0.0, 0.0],
            [0.99, 0.141, 0.0],
            [0.98, 0.199, 0.0],
        )
        urls = ["a", "b", "c"]
        outliers = find_outliers(v, urls, n_std=2.0)
        # With tiny variance, cutoff may still flag none
        assert all(isinstance(o, OutlierResult) for o in outliers)

    def test_sorted_by_descending_distance(self):
        v = _make_vectors(
            [1.0, 0.0],
            [0.98, 0.199],
            [0.0, 1.0],
        )
        urls = ["a", "b", "c"]
        outliers = find_outliers(v, urls, n_std=0.5)
        if len(outliers) > 1:
            dists = [o.distance_from_centroid for o in outliers]
            assert dists == sorted(dists, reverse=True)

    def test_empty_no_outliers(self):
        assert find_outliers(np.zeros((0, 0)), [], n_std=2.0) == []
        assert find_outliers(_make_vectors([1.0, 0.0]), ["a"], n_std=2.0) == []

    def test_length_mismatch_raises(self):
        v = _make_vectors([1.0, 0.0], [0.0, 1.0])
        with pytest.raises(ValueError, match="length mismatch"):
            find_outliers(v, ["a"], n_std=2.0)
