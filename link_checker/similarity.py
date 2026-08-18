"""Cosine similarity and off-topic outlier detection for page embeddings.

Given one vector per crawled page, this module:

  1. Computes pairwise cosine similarity and reports pairs above a
     threshold (default 0.95, matching Screaming Frog's default) as
     semantic duplicates / near-duplicates.
  2. Computes each page's distance from the site-wide content centroid
     and reports pages beyond N standard deviations (default 2.0) as
     off-topic outliers.

Vectors are L2-normalized on input so cosine similarity reduces to a dot
product. The centroid is the mean of the normalized vectors; distance
from the centroid is `1 - cosine_sim(page, centroid)` on the 0..1 scale
(for non-negative embedding spaces such as nomic-embed-text).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import combinations
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Default thresholds, matching Screaming Frog's defaults so anyone coming
# from SF doesn't have to relearn what a score means.
DEFAULT_SIMILARITY_THRESHOLD = 0.95
DEFAULT_OUTLIER_N_STD = 2.0

# Below this similarity we don't even consider a pair, regardless of the
# user's threshold. Used to skip the obvious 0.x noise on large sites.
_MIN_SIMILARITY_FLOOR = 0.5


@dataclass
class SimilarityPair:
    """A pair of pages flagged as semantically similar."""
    url_a: str
    url_b: str
    similarity: float
    # Populated by the history diff: "new", "persistent", "resolved", or "".
    status: str = ""


@dataclass
class OutlierResult:
    """A page flagged as an off-topic outlier."""
    url: str
    distance_from_centroid: float
    # Populated by the history diff: "new", "persistent", "resolved", or "".
    status: str = ""


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """L2-normalize each row of a 2D matrix. Zero rows stay zero."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return matrix / norms


def compute_similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    """Compute the pairwise cosine similarity matrix.

    Args:
        vectors: (n, d) array of page embedding vectors.

    Returns:
        (n, n) symmetric float array with 1.0 on the diagonal.
    """
    if vectors.size == 0:
        return np.zeros((0, 0), dtype=float)
    normalized = _l2_normalize(vectors.astype(float))
    sim = normalized @ normalized.T
    # Clamp to [0, 1] to guard against tiny floating-point excursions
    # for non-negative embedding spaces.
    return np.clip(sim, 0.0, 1.0)


def find_similar_pairs(
    vectors: np.ndarray,
    urls: list[str],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[SimilarityPair]:
    """Find all page pairs whose cosine similarity meets the threshold.

    Args:
        vectors: (n, d) array of page embedding vectors.
        urls: Page URLs, same length and order as `vectors`.
        threshold: Minimum cosine similarity to flag a pair.

    Returns:
        List of `SimilarityPair`, sorted by descending similarity.
    """
    if len(urls) != len(vectors):
        raise ValueError(
            f"vectors and urls length mismatch: {len(vectors)} vs {len(urls)}"
        )

    if len(urls) < 2 or vectors.size == 0:
        return []

    effective_threshold = max(threshold, _MIN_SIMILARITY_FLOOR)
    sim = compute_similarity_matrix(vectors)

    pairs: list[SimilarityPair] = []
    for i, j in combinations(range(len(urls)), 2):
        score = float(sim[i, j])
        if score >= effective_threshold:
            pairs.append(SimilarityPair(
                url_a=urls[i],
                url_b=urls[j],
                similarity=score,
            ))

    pairs.sort(key=lambda p: p.similarity, reverse=True)
    return pairs


def find_outliers(
    vectors: np.ndarray,
    urls: list[str],
    n_std: float = DEFAULT_OUTLIER_N_STD,
) -> list[OutlierResult]:
    """Flag pages whose embedding sits far from the site-wide centroid.

    Distance is `1 - cosine_sim(page, centroid)` on the 0..1 scale.
    Pages whose distance exceeds `mean + n_std * std` of all page distances
    are flagged as off-topic outliers.

    Args:
        vectors: (n, d) array of page embedding vectors.
        urls: Page URLs, same length and order as `vectors`.
        n_std: Number of standard deviations above the mean distance to flag.

    Returns:
        List of `OutlierResult`, sorted by descending distance.
    """
    if len(urls) != len(vectors):
        raise ValueError(
            f"vectors and urls length mismatch: {len(vectors)} vs {len(urls)}"
        )

    if len(urls) < 2 or vectors.size == 0:
        return []

    normalized = _l2_normalize(vectors.astype(float))
    centroid = normalized.mean(axis=0, keepdims=True)
    # Re-normalize the centroid (mean of unit vectors is not unit length).
    centroid = _l2_normalize(centroid)

    # cosine_sim of each page to the centroid; distance = 1 - sim.
    sims = (normalized @ centroid.T).reshape(-1)
    sims = np.clip(sims, 0.0, 1.0)
    distances = 1.0 - sims

    mean_dist = float(distances.mean())
    std_dist = float(distances.std())
    cutoff = mean_dist + n_std * std_dist

    results: list[OutlierResult] = []
    for idx, url in enumerate(urls):
        dist = float(distances[idx])
        if dist > cutoff and std_dist > 0:
            results.append(OutlierResult(url=url, distance_from_centroid=dist))

    results.sort(key=lambda o: o.distance_from_centroid, reverse=True)
    return results
