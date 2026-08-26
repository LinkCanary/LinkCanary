"""Shared report reading — load per-issue rows from a crawl's CSV report.

Both the report endpoint and the diff service read the same per-issue CSV, so
this lives in one place to keep the field mapping consistent.
"""

from __future__ import annotations

import csv

from ..models.schemas import ReportIssue


def load_issues_from_path(local_path: str) -> list[ReportIssue]:
    """Parse a crawl's ``report.csv`` into ``ReportIssue`` objects.

    Raises ``FileNotFoundError`` if the report file is missing; callers decide
    how to surface that (404 for a report view, empty-diff for a crawl with no
    report yet).
    """
    issues: list[ReportIssue] = []
    with open(local_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            example_pages = row.get("example_pages", "")
            issues.append(ReportIssue(
                source_page=row.get("source_page", ""),
                occurrence_count=int(row.get("occurrence_count", 1)),
                example_pages=example_pages.split("|") if example_pages else [],
                link_url=row.get("link_url", ""),
                link_text=row.get("link_text", ""),
                link_type=row.get("link_type", ""),
                element_type=row.get("element_type", "a"),
                status_code=int(row.get("status_code", 0)),
                issue_type=row.get("issue_type", ""),
                priority=row.get("priority", ""),
                redirect_chain=row.get("redirect_chain") or None,
                final_url=row.get("final_url") or None,
                recommended_fix=row.get("recommended_fix", ""),
                response_time_ms=float(row["response_time_ms"]) if row.get("response_time_ms") else None,
                anchor_quality=row.get("anchor_quality", ""),
            ))
    return issues
