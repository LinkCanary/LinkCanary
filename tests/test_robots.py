"""Tests for robots.txt parsing and compliance checking."""

import pytest

from link_checker.robots import RobotsTxtParser, RobotsComplianceChecker, RobotsRule


class TestRobotsRule:

    def test_default_values(self):
        rule = RobotsRule(user_agent="*")
        assert rule.allow_paths == []
        assert rule.disallow_paths == []
        assert rule.crawl_delay is None

    def test_custom_values(self):
        rule = RobotsRule(
            user_agent="googlebot",
            allow_paths=["/public/"],
            disallow_paths=["/private/"],
            crawl_delay=2.0,
        )
        assert rule.user_agent == "googlebot"
        assert rule.crawl_delay == 2.0


class TestParseRobotsTxt:

    def setup_method(self):
        self.parser = RobotsTxtParser()

    def test_basic_disallow(self):
        content = "User-agent: *\nDisallow: /admin/"
        rules = self.parser.parse_robots_txt(content)
        assert len(rules) == 1
        assert rules[0].user_agent == "*"
        assert "/admin/" in rules[0].disallow_paths

    def test_basic_allow(self):
        content = "User-agent: *\nAllow: /public/\nDisallow: /"
        rules = self.parser.parse_robots_txt(content)
        assert len(rules) == 1
        assert "/public/" in rules[0].allow_paths
        assert "/" in rules[0].disallow_paths

    def test_multiple_user_agents(self):
        content = "User-agent: *\nDisallow: /admin/\n\nUser-agent: googlebot\nDisallow: /private/"
        rules = self.parser.parse_robots_txt(content)
        assert len(rules) == 2

    def test_crawl_delay(self):
        content = "User-agent: *\nCrawl-delay: 5\nDisallow: /"
        rules = self.parser.parse_robots_txt(content)
        assert rules[0].crawl_delay == 5.0

    def test_invalid_crawl_delay(self):
        content = "User-agent: *\nCrawl-delay: invalid\nDisallow: /"
        rules = self.parser.parse_robots_txt(content)
        assert rules[0].crawl_delay is None

    def test_comments_ignored(self):
        content = "# This is a comment\nUser-agent: *\n# Another comment\nDisallow: /admin/"
        rules = self.parser.parse_robots_txt(content)
        assert len(rules) == 1
        assert "/admin/" in rules[0].disallow_paths

    def test_empty_content(self):
        rules = self.parser.parse_robots_txt("")
        assert rules == []

    def test_multiple_disallow_paths(self):
        content = "User-agent: *\nDisallow: /admin/\nDisallow: /private/\nDisallow: /tmp/"
        rules = self.parser.parse_robots_txt(content)
        assert len(rules[0].disallow_paths) == 3


class TestMatchesPattern:

    def setup_method(self):
        self.parser = RobotsTxtParser()

    def test_root_matches_everything(self):
        assert self.parser._matches_pattern("/anything", "/")

    def test_prefix_match(self):
        assert self.parser._matches_pattern("/admin/page", "/admin/")

    def test_prefix_no_match(self):
        assert not self.parser._matches_pattern("/public/page", "/admin/")

    def test_wildcard(self):
        assert self.parser._matches_pattern("/admin/secret/page", "/admin/*/page")

    def test_end_anchor(self):
        assert self.parser._matches_pattern("/page.html", "/*.html$")

    def test_end_anchor_no_match(self):
        assert not self.parser._matches_pattern("/page.html/extra", "/*.html$")

    def test_wildcard_extension(self):
        assert self.parser._matches_pattern("/files/doc.pdf", "/*.pdf")

    def test_exact_path(self):
        assert self.parser._matches_pattern("/admin", "/admin")


class TestIsAllowed:

    def setup_method(self):
        self.parser = RobotsTxtParser()

    def _inject_rules(self, content):
        rules = self.parser.parse_robots_txt(content)
        self.parser._cache["https://example.com"] = rules

    def test_disallowed_path(self):
        self._inject_rules("User-agent: *\nDisallow: /admin/")
        allowed, reason = self.parser.is_allowed(
            "https://example.com/admin/page", "https://example.com",
        )
        assert not allowed

    def test_allowed_path(self):
        self._inject_rules("User-agent: *\nDisallow: /admin/")
        allowed, reason = self.parser.is_allowed(
            "https://example.com/public/page", "https://example.com",
        )
        assert allowed

    def test_allow_overrides_disallow(self):
        self._inject_rules(
            "User-agent: *\nAllow: /admin/public/\nDisallow: /admin/"
        )
        allowed, _ = self.parser.is_allowed(
            "https://example.com/admin/public/page", "https://example.com",
        )
        assert allowed

    def test_no_rules_allows_all(self):
        self.parser._cache["https://example.com"] = []
        allowed, reason = self.parser.is_allowed(
            "https://example.com/anything", "https://example.com",
        )
        assert allowed
        assert "no robots.txt" in reason

    def test_empty_disallow_allows_all(self):
        self._inject_rules("User-agent: *\nDisallow:")
        allowed, _ = self.parser.is_allowed(
            "https://example.com/anything", "https://example.com",
        )
        assert allowed


class TestGetCrawlDelay:

    def setup_method(self):
        self.parser = RobotsTxtParser()

    def test_crawl_delay_present(self):
        rules = self.parser.parse_robots_txt(
            "User-agent: *\nCrawl-delay: 10\nDisallow: /"
        )
        self.parser._cache["https://example.com"] = rules
        delay = self.parser.get_crawl_delay("https://example.com")
        assert delay == 10.0

    def test_crawl_delay_absent(self):
        rules = self.parser.parse_robots_txt("User-agent: *\nDisallow: /")
        self.parser._cache["https://example.com"] = rules
        delay = self.parser.get_crawl_delay("https://example.com")
        assert delay is None


class TestRobotsComplianceChecker:

    def test_ignore_robots(self):
        checker = RobotsComplianceChecker(ignore_robots=True)
        allowed, reason = checker.check_url(
            "https://example.com/admin/", "https://example.com",
        )
        assert allowed
        assert "ignored" in reason

    def test_filter_urls_ignore_mode(self):
        checker = RobotsComplianceChecker(ignore_robots=True)
        urls = ["https://example.com/a", "https://example.com/b"]
        allowed, skipped = checker.filter_urls(urls, "https://example.com")
        assert len(allowed) == 2
        assert len(skipped) == 0

    def test_get_stats(self):
        checker = RobotsComplianceChecker(ignore_robots=True)
        stats = checker.get_stats()
        assert stats["ignored"] is True
        assert stats["urls_skipped"] == 0

    def test_default_not_ignored(self):
        checker = RobotsComplianceChecker()
        stats = checker.get_stats()
        assert stats["ignored"] is False
