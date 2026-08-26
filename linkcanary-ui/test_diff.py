"""Tests for crawl-to-crawl diffing and project domain normalization."""

from linkcanary_ui.models.schemas import ReportIssue
from linkcanary_ui.services.diff import diff_issues
from linkcanary_ui.services.projects import normalize_domain


def _issue(url, source_page="page", priority="high", issue_type="broken_404"):
    return ReportIssue(
        source_page=source_page,
        occurrence_count=1,
        example_pages=[],
        link_url=url,
        link_text="",
        link_type="internal",
        element_type="a",
        status_code=404,
        issue_type=issue_type,
        priority=priority,
        redirect_chain=None,
        final_url=None,
        recommended_fix="",
        response_time_ms=None,
        anchor_quality="",
    )


def test_diff_new_resolved_persistent():
    current = [_issue("https://x.com/a"), _issue("https://x.com/b", priority="medium")]
    prior = [_issue("https://x.com/a"), _issue("https://x.com/d", priority="critical")]

    d = diff_issues(current, prior)

    assert [i.link_url for i in d.new.issues] == ["https://x.com/b"]
    assert [i.link_url for i in d.resolved.issues] == ["https://x.com/d"]
    assert [i.link_url for i in d.persistent.issues] == ["https://x.com/a"]


def test_diff_counts_group_by_priority():
    current = [
        _issue("https://x.com/a", priority="critical"),
        _issue("https://x.com/b", priority="high"),
        _issue("https://x.com/c", priority="high"),
    ]
    d = diff_issues(current, [])

    counts = d.new.counts()
    assert counts["critical"] == 1
    assert counts["high"] == 2
    assert counts["total"] == 3


def test_diff_key_includes_source_page():
    # Same link_url, different source_page → treated as distinct issues.
    current = [_issue("https://x.com/a", source_page="/p1")]
    prior = [_issue("https://x.com/a", source_page="/p2")]

    d = diff_issues(current, prior)
    assert len(d.new.issues) == 1
    assert len(d.resolved.issues) == 1
    assert len(d.persistent.issues) == 0


def test_normalize_domain_strips_www_and_port():
    assert normalize_domain("https://www.Example.com:443/sitemap.xml") == "example.com"
    assert normalize_domain("https://example.com/sitemap.xml") == "example.com"
    assert normalize_domain("https://blog.example.com/sitemap.xml") == "blog.example.com"


def test_normalize_domain_non_url_fallback():
    assert normalize_domain("not a url") == "not a url"
