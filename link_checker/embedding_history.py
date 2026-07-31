"""Run-history persistence and diffing for semantic findings (Phase 3).

Stores a lightweight record of each crawl run's similar pairs and off-topic
outliers so that the next run can classify findings as:

  - **new**         — appeared since the last run (the CI-native alert)
  - **persistent**  — also present in the prior run (known, not re-alerted)
  - **resolved**    — was present in the prior run but is gone now

This is the piece that has no equivalent in Screaming Frog's desktop model:
SF reports all duplicates every time you run it, so known pairs resurface
on every audit. LinkCanary, running unattended on a schedule, can tell you
"these two pages *became* similar since Tuesday" — a regression signal
nobody catches until a client asks why two pages compete for the same
keyword.

The history file is JSON:

    {
      "version": 1,
      "model": "nomic-embed-text",
      "provider": "ollama",
      "runs": [
        {
          "timestamp": "2026-07-30T12:00:00",
          "pairs": [["url_a", "url_b"], ...],
          "outliers": ["url1", "url2", ...]
        }
      ]
    }

Pair fingerprints are stored as sorted 2-tuples so order doesn't matter.
Only the most recent ``max_runs`` entries are kept (default 10) to bound
the file size. A model or provider mismatch invalidates the history
(findings from different models are not comparable).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .similarity import OutlierResult, SimilarityPair

logger = logging.getLogger(__name__)

HISTORY_FORMAT_VERSION = 1
DEFAULT_MAX_RUNS = 10


def _pair_fingerprint(url_a: str, url_b: str) -> tuple[str, str]:
    """Canonical, order-independent fingerprint for a similar pair."""
    return tuple(sorted((url_a, url_b)))  # type: ignore[return-value]


class EmbeddingHistory:
    """Run-history store for semantic findings, backed by a JSON file.

    Usage in the CLI flow::

        history = EmbeddingHistory(path, model, provider)
        history.load()
        prior_pairs, prior_outliers = history.prior_findings()

        # ... compute current pairs and outliers ...

        diff_pairs = diff_pairs(current_pairs, prior_pairs)
        history.record_run(current_pairs, current_outliers)
        history.save()
    """

    def __init__(
        self,
        path: str,
        model: str,
        provider: str,
        max_runs: int = DEFAULT_MAX_RUNS,
    ):
        self.path = Path(path)
        self.model = model
        self.provider = provider
        self.max_runs = max_runs
        self._runs: list[dict] = []
        self._dirty = False

    def load(self) -> None:
        """Load history from disk. Empty if missing or model/provider mismatch."""
        if not self.path.exists():
            self._runs = []
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Embedding history unreadable (%s): starting empty", exc)
            self._runs = []
            return

        cached_model = data.get("model")
        cached_provider = data.get("provider")
        if cached_model != self.model or cached_provider != self.provider:
            logger.info(
                "Embedding history model/provider mismatch "
                "(cached %s/%s vs current %s/%s): treating as first run",
                cached_provider, cached_model, self.provider, self.model,
            )
            self._runs = []
            self._dirty = True
            return

        self._runs = data.get("runs", [])
        self._dirty = False

    def prior_findings(self) -> tuple[set[tuple[str, str]], set[str]]:
        """Return the pair-fingerprint set and outlier-URL set from the
        most recent prior run. Empty sets if there is no prior run."""
        if not self._runs:
            return set(), set()
        last = self._runs[-1]
        prior_pairs = {tuple(p) for p in last.get("pairs", [])}
        prior_outliers = set(last.get("outliers", []))
        return prior_pairs, prior_outliers

    def record_run(
        self,
        pairs: list[SimilarityPair],
        outliers: list[OutlierResult],
    ) -> None:
        """Append the current run's findings to the history."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
            "pairs": [
                list(_pair_fingerprint(p.url_a, p.url_b)) for p in pairs
            ],
            "outliers": [o.url for o in outliers],
        }
        self._runs.append(entry)
        # Trim to max_runs, keeping the most recent.
        if len(self._runs) > self.max_runs:
            self._runs = self._runs[-self.max_runs :]
        self._dirty = True

    def save(self) -> None:
        """Persist the history to disk if there are unsaved changes."""
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": HISTORY_FORMAT_VERSION,
            "model": self.model,
            "provider": self.provider,
            "runs": self._runs,
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self._dirty = False
        logger.info(
            "Embedding history saved to %s (%d runs)", self.path, len(self._runs)
        )

    @property
    def run_count(self) -> int:
        return len(self._runs)


# --- Diffing helpers --------------------------------------------------------

def diff_pairs(
    current: list[SimilarityPair],
    prior_fingerprints: set[tuple[str, str]],
) -> list[SimilarityPair]:
    """Tag each current pair with 'new' or 'persistent' in-place.

    Args:
        current: The current run's similar pairs (mutated: ``.status`` set).
        prior_fingerprints: Pair fingerprints from the prior run.

    Returns:
        The same list (for convenience), with each pair's ``status`` set to
        ``"new"`` or ``"persistent"``.
    """
    for pair in current:
        fp = _pair_fingerprint(pair.url_a, pair.url_b)
        pair.status = "persistent" if fp in prior_fingerprints else "new"
    return current


def diff_outliers(
    current: list[OutlierResult],
    prior_outlier_urls: set[str],
) -> list[OutlierResult]:
    """Tag each current outlier with 'new' or 'persistent' in-place.

    Args:
        current: The current run's outliers (mutated: ``.status`` set).
        prior_outlier_urls: Outlier URLs from the prior run.

    Returns:
        The same list, with each outlier's ``status`` set to ``"new"`` or
        ``"persistent"``.
    """
    for outlier in current:
        outlier.status = "persistent" if outlier.url in prior_outlier_urls else "new"
    return current


def count_resolved_pairs(
    current: list[SimilarityPair],
    prior_fingerprints: set[tuple[str, str]],
) -> int:
    """How many prior pairs are no longer flagged as similar."""
    current_fps = {_pair_fingerprint(p.url_a, p.url_b) for p in current}
    return len(prior_fingerprints - current_fps)


def count_resolved_outliers(
    current: list[OutlierResult],
    prior_outlier_urls: set[str],
) -> int:
    """How many prior outliers are no longer flagged."""
    current_urls = {o.url for o in current}
    return len(prior_outlier_urls - current_urls)
