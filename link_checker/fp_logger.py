"""False positive logger for the priority classifier.

Appends newline-delimited JSON records to a .jsonl file alongside the main
report. Two event types are written:

  classification — emitted once per link per scan with the features the
                   classifier used and the priority it assigned.

  correction     — emitted when the user marks a classification as wrong via
                   --mark-fp. Records the URL, what was assigned, and what the
                   correct priority should be.

Together these accumulate the labeled data needed to retrain a simple
supervised classifier (e.g. scikit-learn gradient boosted tree) without any
custom infrastructure.
"""

import json
import logging
from datetime import datetime, timezone

_log = logging.getLogger(__name__)


class FPLogger:
    """Appends classifier events and user corrections to a JSONL file."""

    def __init__(self, log_path: str):
        self.log_path = log_path

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _append(self, record: dict) -> None:
        try:
            with open(self.log_path, 'a') as fh:
                fh.write(json.dumps(record) + '\n')
        except OSError as exc:
            _log.warning("Could not write to FP log %s: %s", self.log_path, exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_classification(
        self,
        *,
        link_url: str,
        source_page: str,
        status_code: int,
        issue_type: str,
        is_internal: bool,
        hop_count: int,
        assigned_priority: str,
    ) -> None:
        """Record a single classifier decision."""
        self._append({
            "event": "classification",
            "ts": datetime.now(timezone.utc).isoformat(),
            "link_url": link_url,
            "source_page": source_page,
            "status_code": status_code,
            "issue_type": issue_type,
            "is_internal": is_internal,
            "hop_count": hop_count,
            "assigned_priority": assigned_priority,
        })

    def log_correction(
        self,
        *,
        link_url: str,
        correct_priority: str,
        note: str = '',
    ) -> None:
        """Record a user correction for a previously classified URL."""
        record: dict = {
            "event": "correction",
            "ts": datetime.now(timezone.utc).isoformat(),
            "link_url": link_url,
            "correct_priority": correct_priority,
        }
        if note:
            record["note"] = note
        self._append(record)
