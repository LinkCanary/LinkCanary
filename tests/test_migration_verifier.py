"""Tests for migration report verification (Migration Report Schema v1.0)."""

import pytest

from link_checker.checker import LinkStatus
from link_checker.migration_verifier import (
    COLLISION,
    MISSING,
    REDIRECT_MISSING,
    REVIEW,
    UNEXPECTED_LIVE,
    VERIFIED,
    MigrationReportError,
    MigrationVerifier,
    load_migration_report,
    summarize,
    validate_report,
    verification_csv,
)


def sample_report():
    return {
        "version": "1.0",
        "generated_by": "portage@0.1.0",
        "generated_at": "2026-08-08T20:00:00.000Z",
        "destination_base_url": "https://example.com",
        "destination_platform": "astro",
        "records": [
            {
                "source_platform": "squarespace",
                "source_url": "https://oldsite.com/blog/a",
                "destination_path": "/blog/a/",
                "status": "migrated",
                "images_rehosted": True,
                "links_rewritten": True,
            },
            {
                "source_platform": "squarespace",
                "source_url": "https://oldsite.com/blog/b",
                "destination_path": "/blog/b/",
                "status": "redirected",
                "redirect_target": "https://example.com/blog/b/",
                "images_rehosted": True,
                "links_rewritten": True,
            },
            {
                "source_platform": "squarespace",
                "source_url": "https://oldsite.com/blog/draft",
                "destination_path": None,
                "status": "excluded",
                "reason": "draft",
                "images_rehosted": False,
                "links_rewritten": False,
            },
            {
                "source_platform": "squarespace",
                "source_url": "https://oldsite.com/blog/broken",
                "destination_path": None,
                "status": "failed",
                "reason": "transform error",
                "images_rehosted": False,
                "links_rewritten": False,
            },
        ],
    }


def _status(url, code, is_redirect=False, chain=None, final="", error=""):
    return LinkStatus(
        url=url,
        status_code=code,
        is_redirect=is_redirect,
        redirect_chain=chain or [],
        final_url=final or url,
        error=error,
    )


class FakeChecker:
    """check_link responder driven by a URL → LinkStatus table."""

    def __init__(self, table):
        self.table = table
        self.called = []

    def check_link(self, url):
        self.called.append(url)
        return self.table.get(url, _status(url, 0, error="not stubbed"))


def _verify(report, table, site=None):
    verifier = MigrationVerifier(FakeChecker(table))
    return verifier.verify(report, site=site)


class TestValidateReport:
    def test_accepts_conforming_report(self):
        validate_report(sample_report())

    def test_rejects_wrong_version(self):
        report = sample_report()
        report["version"] = "2"
        with pytest.raises(MigrationReportError, match="version"):
            validate_report(report)

    def test_rejects_missing_header_field(self):
        report = sample_report()
        del report["destination_base_url"]
        with pytest.raises(MigrationReportError, match="destination_base_url"):
            validate_report(report)

    def test_rejects_missing_record_field(self):
        report = sample_report()
        del report["records"][0]["source_url"]
        with pytest.raises(MigrationReportError, match="source_url"):
            validate_report(report)

    def test_rejects_unknown_status(self):
        report = sample_report()
        report["records"][0]["status"] = "maybe"
        with pytest.raises(MigrationReportError, match="status"):
            validate_report(report)

    def test_rejects_relative_destination_path(self):
        report = sample_report()
        report["records"][0]["destination_path"] = "blog/a/"
        with pytest.raises(MigrationReportError, match="start with"):
            validate_report(report)

    def test_load_migration_report(self, tmp_path):
        import json

        path = tmp_path / "migration-report.json"
        path.write_text(json.dumps(sample_report()), encoding="utf-8")
        assert load_migration_report(str(path))["version"] == "1.0"

    def test_load_rejects_non_conforming(self, tmp_path):
        import json

        path = tmp_path / "migration-report.json"
        path.write_text(json.dumps({"version": "0.9"}), encoding="utf-8")
        with pytest.raises(MigrationReportError):
            load_migration_report(str(path))


class TestMigrationVerifier:
    def test_migrated_destination_200_verified(self):
        report = sample_report()
        rows = _verify(report, {"https://example.com/blog/a/": _status("u", 200)})
        a = next(r for r in rows if r.source_url.endswith("/blog/a"))
        assert a.verification == VERIFIED
        assert a.destination_url == "https://example.com/blog/a/"
        assert a.observed_status == 200

    def test_migrated_destination_404_missing(self):
        report = sample_report()
        rows = _verify(report, {"https://example.com/blog/a/": _status("u", 404)})
        a = next(r for r in rows if r.source_url.endswith("/blog/a"))
        assert a.verification == MISSING

    def test_redirected_verifies_source_redirect_and_destination(self):
        report = sample_report()
        table = {
            "https://example.com/blog/b/": _status("dest", 200),
            "https://oldsite.com/blog/b": _status(
                "src", 200, is_redirect=True,
                chain=[(301, "https://oldsite.com/blog/b"), (200, "https://example.com/blog/b/")],
                final="https://example.com/blog/b/",
            ),
        }
        rows = _verify(report, table)
        b = next(r for r in rows if r.source_url.endswith("/blog/b"))
        assert b.verification == VERIFIED

    def test_redirected_source_not_redirecting_flagged(self):
        report = sample_report()
        table = {
            "https://example.com/blog/b/": _status("dest", 200),
            "https://oldsite.com/blog/b": _status("src", 404),
        }
        rows = _verify(report, table)
        b = next(r for r in rows if r.source_url.endswith("/blog/b"))
        assert b.verification == REDIRECT_MISSING

    def test_excluded_source_gone_verified(self):
        report = sample_report()
        rows = _verify(report, {"https://oldsite.com/blog/draft": _status("u", 404)})
        draft = next(r for r in rows if r.source_url.endswith("/blog/draft"))
        assert draft.verification == VERIFIED

    def test_excluded_source_still_live_unexpected_live(self):
        report = sample_report()
        rows = _verify(report, {"https://oldsite.com/blog/draft": _status("u", 200)})
        draft = next(r for r in rows if r.source_url.endswith("/blog/draft"))
        assert draft.verification == UNEXPECTED_LIVE

    def test_failed_record_needs_review(self):
        report = sample_report()
        rows = _verify(report, {})
        broken = next(r for r in rows if r.source_url.endswith("/blog/broken"))
        assert broken.verification == REVIEW

    def test_collision_detected(self):
        report = sample_report()
        report["records"].append(dict(report["records"][0]))  # duplicate destination
        rows = _verify(report, {})
        collisions = [r for r in rows if r.verification == COLLISION]
        assert len(collisions) == 2

    def test_site_override(self):
        report = sample_report()
        rows = _verify(report, {"https://staging.example.com/blog/a/": _status("u", 200)}, site="https://staging.example.com")
        a = next(r for r in rows if r.source_url.endswith("/blog/a"))
        assert a.destination_url == "https://staging.example.com/blog/a/"


class TestSummarizeAndCsv:
    def test_summarize_counts(self):
        report = sample_report()
        table = {
            "https://example.com/blog/a/": _status("u", 200),
            "https://example.com/blog/b/": _status("u", 200),
            "https://oldsite.com/blog/b": _status("s", 200, is_redirect=True),
            "https://oldsite.com/blog/draft": _status("u", 404),
        }
        rows = _verify(report, table)
        counts = summarize(rows)
        assert counts[VERIFIED] == 3  # a, b, draft
        assert counts[REVIEW] == 1    # failed
        assert counts[MISSING] == 0

    def test_verification_csv_headers(self):
        report = sample_report()
        rows = _verify(report, {})
        csv_text = verification_csv(rows)
        assert csv_text.startswith("source_url,destination_url,record_status,verification,")
        assert "failed" in csv_text
