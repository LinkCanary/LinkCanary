"""Crawl-to-crawl diffing — what's new, resolved, or persistent.

Compares two crawls' per-issue rows on a stable key of ``(link_url, source_page)``
and buckets each issue as ``new`` (only in the newer crawl), ``resolved`` (only in
the prior crawl), or ``persistent`` (in both). Results are grouped by priority so
"3 new critical issues since last Tuesday" is the headline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models.schemas import ReportIssue

PRIORITIES = ("critical", "high", "medium", "low", "info")


@dataclass
class DiffBucket:
    """Issues grouped by priority for one diff category (new/resolved/persistent)."""
    issues: list[ReportIssue] = field(default_factory=list)

    def by_priority(self) -> dict[str, list[ReportIssue]]:
        grouped: dict[str, list[ReportIssue]] = {p: [] for p in PRIORITIES}
        for issue in self.issues:
            p = issue.priority if issue.priority in grouped else "low"
            grouped[p].append(issue)
        return grouped

    def counts(self) -> dict[str, int]:
        grouped = self.by_priority()
        return {p: len(grouped[p]) for p in PRIORITIES} | {"total": len(self.issues)}


@dataclass
class CrawlDiff:
    new: DiffBucket = field(default_factory=DiffBucket)
    resolved: DiffBucket = field(default_factory=DiffBucket)
    persistent: DiffBucket = field(default_factory=DiffBucket)


def _issue_key(issue: ReportIssue) -> tuple[str, str]:
    """Stable identity of an issue across runs."""
    return (issue.link_url, issue.source_page)


def diff_issues(current: list[ReportIssue], prior: list[ReportIssue]) -> CrawlDiff:
    """Diff ``current`` (newer) against ``prior`` (older).

    Issues are matched on ``(link_url, source_page)``. ``persistent`` issues are
    taken from the current crawl (their latest state).
    """
    prior_keys = {_issue_key(i) for i in prior}
    current_keys = {_issue_key(i) for i in current}

    new = [i for i in current if _issue_key(i) not in prior_keys]
    resolved = [i for i in prior if _issue_key(i) not in current_keys]
    persistent = [i for i in current if _issue_key(i) in prior_keys]

    return CrawlDiff(
        new=DiffBucket(issues=new),
        resolved=DiffBucket(issues=resolved),
        persistent=DiffBucket(issues=persistent),
    )
