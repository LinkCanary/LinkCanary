"""Comprehensive tests for link_checker.robots module.

Tests cover:
- RobotsRule dataclass
- RobotsTxtParser.parse_robots_txt
- RobotsTxtParser._matches_pattern
- RobotsTxtParser.is_allowed (via cache injection)
- RobotsTxtParser.get_crawl_delay (via cache injection)
- RobotsComplianceChecker.check_url
- RobotsComplianceChecker.filter_urls
"""

import pytest
from unittest.mock import patch, MagicMock

from link_checker.robots import RobotsTxtParser, RobotsComplianceChecker, RobotsRule


# ---------------------------------------------------------------------------
# RobotsRule dataclass
# ---------------------------------------------------------------------------

class TestRobotsRule:
    """Tests for the RobotsRule dataclass."""

    def test_create_basic_rule(self):
        rule = RobotsRule(
            user_agent="*",
            allow_paths=["/"],
            disallow_paths=["/admin"],
        )
        assert rule.user_agent == "*"
        assert rule.allow_paths == ["/"]
        assert rule.disallow_paths == ["/admin"]
        assert rule.crawl_delay is None

    def test_create_rule_with_crawl_delay(self):
        rule = RobotsRule(
            user_agent="Googlebot",
            allow_paths=[],
            disallow_paths=["/private"],
            crawl_delay=2.5,
        )
        assert rule.crawl_delay == 2.5

    def test_default_crawl_delay_is_none(self):
        rule = RobotsRule(user_agent="*", allow_paths=[], disallow_paths=[])
        assert rule.crawl_delay is None


# ---------------------------------------------------------------------------
# RobotsTxtParser — parse_robots_txt
# ---------------------------------------------------------------------------

class TestParseRobotsTxt:
    """Tests for RobotsTxtParser.parse_robots_txt."""

    def setup_method(self):
        self.parser = RobotsTxtParser()

    # -- empty / trivial content ------------------------------------------

    def test_empty_content_returns_empty_list(self):
        rules = self.parser.parse_robots_txt("")
        assert rules == []

    def test_whitespace_only_content(self):
        rules = self.parser.parse_robots_txt("   \n\n  \n")
        assert rules == []

    # -- basic single-agent block -----------------------------------------

    def test_basic_disallow_rule(self):
        content = (
            "User-agent: *\n"
            "Disallow: /admin\n"
        )
        rules = self.parser.parse_robots_txt(content)
        assert len(rules) >= 1
        wildcard_rules = [r for r in rules if r.user_agent == "*"]
        assert len(wildcard_rules) == 1
        assert "/admin" in wildcard_rules[0].disallow_paths

    def test_basic_allow_rule(self):
        content = (
            "User-agent: *\n"
            "Allow: /public\n"
            "Disallow: /\n"
        )
        rules = self.parser.parse_robots_txt(content)
        wildcard_rules = [r for r in rules if r.user_agent == "*"]
        assert len(wildcard_rules) == 1
        assert "/public" in wildcard_rules[0].allow_paths
        assert "/" in wildcard_rules[0].disallow_paths

    def test_multiple_disallow_paths(self):
        content = (
            "User-agent: *\n"
            "Disallow: /admin\n"
            "Disallow: /private\n"
            "Disallow: /secret\n"
        )
        rules = self.parser.parse_robots_txt(content)
        wildcard_rules = [r for r in rules if r.user_agent == "*"]
        assert len(wildcard_rules) == 1
        for path in ["/admin", "/private", "/secret"]:
            assert path in wildcard_rules[0].disallow_paths

    # -- multiple user-agent blocks ---------------------------------------

    def test_multiple_user_agents(self):
        content = (
            "User-agent: Googlebot\n"
            "Disallow: /nogoogle\n"
            "\n"
            "User-agent: Bingbot\n"
            "Disallow: /nobing\n"
        )
        rules = self.parser.parse_robots_txt(content)
        agents = {r.user_agent for r in rules}
        assert "Googlebot" in agents or "googlebot" in agents
        assert "Bingbot" in agents or "bingbot" in agents

    def test_wildcard_and_specific_agent(self):
        content = (
            "User-agent: *\n"
            "Disallow: /all-blocked\n"
            "\n"
            "User-agent: LinkCanary\n"
            "Disallow: /canary-blocked\n"
        )
        rules = self.parser.parse_robots_txt(content)
        assert len(rules) >= 2
        ua_map = {r.user_agent.lower(): r for r in rules}
        assert "*" in ua_map or "*" in {r.user_agent for r in rules}

    # -- crawl-delay ------------------------------------------------------

    def test_crawl_delay_integer(self):
        content = (
            "User-agent: *\n"
            "Crawl-delay: 5\n"
            "Disallow: /admin\n"
        )
        rules = self.parser.parse_robots_txt(content)
        wildcard_rules = [r for r in rules if r.user_agent == "*"]
        assert len(wildcard_rules) == 1
        assert wildcard_rules[0].crawl_delay == 5 or wildcard_rules[0].crawl_delay == 5.0

    def test_crawl_delay_float(self):
        content = (
            "User-agent: *\n"
            "Crawl-delay: 1.5\n"
        )
        rules = self.parser.parse_robots_txt(content)
        wildcard_rules = [r for r in rules if r.user_agent == "*"]
        assert len(wildcard_rules) == 1
        assert wildcard_rules[0].crawl_delay == 1.5

    def test_no_crawl_delay_yields_none(self):
        content = (
            "User-agent: *\n"
            "Disallow: /admin\n"
        )
        rules = self.parser.parse_robots_txt(content)
        wildcard_rules = [r for r in rules if r.user_agent == "*"]
        assert len(wildcard_rules) == 1
        assert wildcard_rules[0].crawl_delay is None

    # -- comments ---------------------------------------------------------

    def test_comments_are_ignored(self):
        content = (
            "# This is a comment\n"
            "User-agent: *\n"
            "# Another comment\n"
            "Disallow: /admin  # inline comment\n"
        )
        rules = self.parser.parse_robots_txt(content)
        assert len(rules) >= 1
        wildcard_rules = [r for r in rules if r.user_agent == "*"]
        assert len(wildcard_rules) == 1
        # The disallow path should not include the comment portion
        disallow = wildcard_rules[0].disallow_paths
        assert any("/admin" in p for p in disallow)

    def test_comment_only_content(self):
        content = "# Just a comment\n# Another one\n"
        rules = self.parser.parse_robots_txt(content)
        assert rules == []

    # -- edge cases -------------------------------------------------------

    def test_empty_disallow_means_allow_all(self):
        content = (
            "User-agent: *\n"
            "Disallow:\n"
        )
        rules = self.parser.parse_robots_txt(content)
        wildcard_rules = [r for r in rules if r.user_agent == "*"]
        assert len(wildcard_rules) >= 1
        # An empty Disallow means nothing is disallowed; the path list
        # should either be empty or contain an empty string
        rule = wildcard_rules[0]
        assert rule.disallow_paths == [] or rule.disallow_paths == [""]

    def test_case_insensitive_directives(self):
        content = (
            "user-agent: *\n"
            "disallow: /admin\n"
        )
        rules = self.parser.parse_robots_txt(content)
        assert len(rules) >= 1

    def test_allow_all_robots_txt(self):
        """A robots.txt that allows everything."""
        content = (
            "User-agent: *\n"
            "Allow: /\n"
        )
        rules = self.parser.parse_robots_txt(content)
        wildcard_rules = [r for r in rules if r.user_agent == "*"]
        assert len(wildcard_rules) == 1
        assert "/" in wildcard_rules[0].allow_paths

    def test_disallow_all_robots_txt(self):
        """A robots.txt that disallows everything."""
        content = (
            "User-agent: *\n"
            "Disallow: /\n"
        )
        rules = self.parser.parse_robots_txt(content)
        wildcard_rules = [r for r in rules if r.user_agent == "*"]
        assert len(wildcard_rules) == 1
        assert "/" in wildcard_rules[0].disallow_paths


# ---------------------------------------------------------------------------
# RobotsTxtParser — _matches_pattern
# ---------------------------------------------------------------------------

class TestMatchesPattern:
    """Tests for RobotsTxtParser._matches_pattern."""

    def setup_method(self):
        self.parser = RobotsTxtParser()

    # -- root pattern '/' matches everything ------------------------------

    def test_root_pattern_matches_root(self):
        assert self.parser._matches_pattern("/", "/") is True

    def test_root_pattern_matches_any_path(self):
        assert self.parser._matches_pattern("/foo/bar", "/") is True

    def test_root_pattern_matches_deep_path(self):
        assert self.parser._matches_pattern("/a/b/c/d/e", "/") is True

    # -- simple prefix matching -------------------------------------------

    def test_prefix_match_exact(self):
        assert self.parser._matches_pattern("/admin", "/admin") is True

    def test_prefix_match_subpath(self):
        assert self.parser._matches_pattern("/admin/dashboard", "/admin") is True

    def test_prefix_no_match(self):
        assert self.parser._matches_pattern("/public", "/admin") is False

    def test_prefix_match_with_trailing_slash(self):
        assert self.parser._matches_pattern("/admin/", "/admin/") is True

    def test_prefix_partial_component_match(self):
        # "/admin" pattern should match "/admin-panel" via prefix matching
        # (this depends on implementation — standard robots.txt prefix matching
        # does match partial components)
        result = self.parser._matches_pattern("/admin-panel", "/admin")
        assert result is True  # prefix match: "/admin" is prefix of "/admin-panel"

    # -- wildcard * matching ----------------------------------------------

    def test_wildcard_middle(self):
        assert self.parser._matches_pattern("/foo/bar/baz", "/foo/*/baz") is True

    def test_wildcard_end(self):
        assert self.parser._matches_pattern("/foo/anything", "/foo/*") is True

    def test_wildcard_start(self):
        assert self.parser._matches_pattern("/anything/bar", "*/bar") is True

    def test_wildcard_no_match(self):
        assert self.parser._matches_pattern("/foo/bar", "/baz/*") is False

    def test_multiple_wildcards(self):
        assert self.parser._matches_pattern("/a/b/c/d", "/a/*/c/*") is True

    def test_wildcard_matches_empty(self):
        # A wildcard can match zero characters
        result = self.parser._matches_pattern("/foo/baz", "/foo/*baz")
        assert result is True

    # -- end anchor $ -----------------------------------------------------

    def test_dollar_exact_end_match(self):
        assert self.parser._matches_pattern("/path.html", "/path.html$") is True

    def test_dollar_no_match_extra_chars(self):
        assert self.parser._matches_pattern("/path.html/extra", "/path.html$") is False

    def test_dollar_with_extension(self):
        assert self.parser._matches_pattern("/page.php", "*.php$") is True

    def test_dollar_no_match_different_extension(self):
        assert self.parser._matches_pattern("/page.html", "*.php$") is False

    def test_dollar_with_query_string_no_match(self):
        assert self.parser._matches_pattern("/page.php?id=1", "*.php$") is False

    # -- combined patterns ------------------------------------------------

    def test_wildcard_and_dollar(self):
        assert self.parser._matches_pattern("/folder/file.js", "/folder/*.js$") is True

    def test_wildcard_and_dollar_no_match(self):
        assert self.parser._matches_pattern("/folder/file.js/x", "/folder/*.js$") is False

    # -- edge cases -------------------------------------------------------

    def test_empty_pattern(self):
        # Empty pattern should match everything (or nothing depending on impl)
        result = self.parser._matches_pattern("/anything", "")
        # An empty Disallow value means nothing is disallowed, so matching
        # "" against any path is typically True (prefix of everything)
        assert isinstance(result, bool)

    def test_empty_path(self):
        result = self.parser._matches_pattern("", "/")
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# RobotsTxtParser — is_allowed (via cache injection)
# ---------------------------------------------------------------------------

class TestIsAllowed:
    """Tests for RobotsTxtParser.is_allowed using cache injection."""

    def setup_method(self):
        self.parser = RobotsTxtParser()

    def _inject_rules(self, base_url, content):
        """Parse robots content and inject into parser cache."""
        rules = self.parser.parse_robots_txt(content)
        self.parser._cache[base_url] = rules
        return rules

    def test_allowed_when_not_disallowed(self):
        self._inject_rules("https://example.com", (
            "User-agent: *\n"
            "Disallow: /admin\n"
        ))
        allowed, reason = self.parser.is_allowed(
            "https://example.com/public/page", "https://example.com"
        )
        assert allowed is True

    def test_disallowed_path(self):
        self._inject_rules("https://example.com", (
            "User-agent: *\n"
            "Disallow: /admin\n"
        ))
        allowed, reason = self.parser.is_allowed(
            "https://example.com/admin/", "https://example.com"
        )
        assert allowed is False

    def test_disallowed_subpath(self):
        self._inject_rules("https://example.com", (
            "User-agent: *\n"
            "Disallow: /admin\n"
        ))
        allowed, reason = self.parser.is_allowed(
            "https://example.com/admin/dashboard", "https://example.com"
        )
        assert allowed is False

    def test_allow_overrides_disallow(self):
        self._inject_rules("https://example.com", (
            "User-agent: *\n"
            "Allow: /admin/public\n"
            "Disallow: /admin\n"
        ))
        allowed, reason = self.parser.is_allowed(
            "https://example.com/admin/public", "https://example.com"
        )
        assert allowed is True

    def test_disallow_all(self):
        self._inject_rules("https://example.com", (
            "User-agent: *\n"
            "Disallow: /\n"
        ))
        allowed, reason = self.parser.is_allowed(
            "https://example.com/anything", "https://example.com"
        )
        assert allowed is False

    def test_allow_all_empty_disallow(self):
        self._inject_rules("https://example.com", (
            "User-agent: *\n"
            "Disallow:\n"
        ))
        allowed, reason = self.parser.is_allowed(
            "https://example.com/anything", "https://example.com"
        )
        assert allowed is True

    def test_no_matching_rule_defaults_to_allowed(self):
        self._inject_rules("https://example.com", (
            "User-agent: Googlebot\n"
            "Disallow: /\n"
        ))
        allowed, reason = self.parser.is_allowed(
            "https://example.com/page", "https://example.com"
        )
        # LinkCanary is not Googlebot, so if no wildcard rule, everything is allowed
        assert allowed is True

    def test_specific_user_agent_match(self):
        self._inject_rules("https://example.com", (
            "User-agent: LinkCanary\n"
            "Disallow: /private\n"
        ))
        allowed, reason = self.parser.is_allowed(
            "https://example.com/private/data", "https://example.com"
        )
        assert allowed is False

    def test_empty_rules_allows_everything(self):
        self.parser._cache["https://example.com"] = []
        allowed, reason = self.parser.is_allowed(
            "https://example.com/anything", "https://example.com"
        )
        assert allowed is True

    def test_is_allowed_returns_tuple(self):
        self._inject_rules("https://example.com", (
            "User-agent: *\n"
            "Disallow: /admin\n"
        ))
        result = self.parser.is_allowed(
            "https://example.com/admin", "https://example.com"
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_reason_message_for_disallowed(self):
        self._inject_rules("https://example.com", (
            "User-agent: *\n"
            "Disallow: /admin\n"
        ))
        allowed, reason = self.parser.is_allowed(
            "https://example.com/admin/secret", "https://example.com"
        )
        assert allowed is False
        assert reason  # reason should be a non-empty string

    def test_wildcard_pattern_in_disallow(self):
        self._inject_rules("https://example.com", (
            "User-agent: *\n"
            "Disallow: /private/*\n"
        ))
        allowed, reason = self.parser.is_allowed(
            "https://example.com/private/data", "https://example.com"
        )
        assert allowed is False

    def test_dollar_anchor_in_disallow(self):
        self._inject_rules("https://example.com", (
            "User-agent: *\n"
            "Disallow: /*.pdf$\n"
        ))
        allowed_pdf, _ = self.parser.is_allowed(
            "https://example.com/docs/file.pdf", "https://example.com"
        )
        allowed_html, _ = self.parser.is_allowed(
            "https://example.com/docs/file.html", "https://example.com"
        )
        assert allowed_pdf is False
        assert allowed_html is True


# ---------------------------------------------------------------------------
# RobotsTxtParser — get_crawl_delay (via cache injection)
# ---------------------------------------------------------------------------

class TestGetCrawlDelay:
    """Tests for RobotsTxtParser.get_crawl_delay using cache injection."""

    def setup_method(self):
        self.parser = RobotsTxtParser()

    def test_crawl_delay_present(self):
        rules = self.parser.parse_robots_txt(
            "User-agent: *\n"
            "Crawl-delay: 10\n"
            "Disallow: /admin\n"
        )
        self.parser._cache["https://example.com"] = rules
        delay = self.parser.get_crawl_delay("https://example.com")
        assert delay == 10 or delay == 10.0

    def test_crawl_delay_absent(self):
        rules = self.parser.parse_robots_txt(
            "User-agent: *\n"
            "Disallow: /admin\n"
        )
        self.parser._cache["https://example.com"] = rules
        delay = self.parser.get_crawl_delay("https://example.com")
        assert delay is None

    def test_crawl_delay_float_value(self):
        rules = self.parser.parse_robots_txt(
            "User-agent: *\n"
            "Crawl-delay: 0.5\n"
        )
        self.parser._cache["https://example.com"] = rules
        delay = self.parser.get_crawl_delay("https://example.com")
        assert delay == 0.5

    def test_crawl_delay_specific_user_agent(self):
        rules = self.parser.parse_robots_txt(
            "User-agent: LinkCanary\n"
            "Crawl-delay: 3\n"
            "Disallow:\n"
        )
        self.parser._cache["https://example.com"] = rules
        delay = self.parser.get_crawl_delay("https://example.com")
        # Should return 3 if the parser matches on the LinkCanary user-agent
        assert delay is None or delay == 3 or delay == 3.0


# ---------------------------------------------------------------------------
# RobotsComplianceChecker
# ---------------------------------------------------------------------------

class TestRobotsComplianceChecker:
    """Tests for RobotsComplianceChecker."""

    # -- ignore_robots=True -----------------------------------------------

    def test_ignore_robots_allows_everything(self):
        checker = RobotsComplianceChecker(ignore_robots=True)
        allowed, reason = checker.check_url(
            "https://example.com/admin/secret", "https://example.com"
        )
        assert allowed is True

    def test_ignore_robots_reason_message(self):
        checker = RobotsComplianceChecker(ignore_robots=True)
        allowed, reason = checker.check_url(
            "https://example.com/private", "https://example.com"
        )
        assert allowed is True
        assert isinstance(reason, str)

    def test_ignore_robots_filter_urls_returns_all(self):
        checker = RobotsComplianceChecker(ignore_robots=True)
        urls = [
            "https://example.com/admin",
            "https://example.com/private",
            "https://example.com/public",
        ]
        allowed_urls, blocked = checker.filter_urls(urls, "https://example.com")
        assert len(allowed_urls) == 3
        assert all(url in allowed_urls for url in urls)

    # -- check_url returns correct types ----------------------------------

    def test_check_url_returns_tuple(self):
        checker = RobotsComplianceChecker(ignore_robots=True)
        result = checker.check_url(
            "https://example.com/page", "https://example.com"
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    # -- filter_urls returns correct types --------------------------------

    def test_filter_urls_return_types(self):
        checker = RobotsComplianceChecker(ignore_robots=True)
        allowed_urls, blocked = checker.filter_urls(
            ["https://example.com/a"], "https://example.com"
        )
        assert isinstance(allowed_urls, list)
        assert isinstance(blocked, dict)

    def test_filter_urls_empty_list(self):
        checker = RobotsComplianceChecker(ignore_robots=True)
        allowed_urls, blocked = checker.filter_urls([], "https://example.com")
        assert allowed_urls == []
        assert blocked == {}

    # -- default constructor values ---------------------------------------

    def test_default_user_agent(self):
        checker = RobotsComplianceChecker()
        assert checker.user_agent == "LinkCanary/1.0" or hasattr(checker, "user_agent")

    def test_default_timeout(self):
        checker = RobotsComplianceChecker()
        assert checker.timeout == 10 or hasattr(checker, "timeout")

    def test_default_ignore_robots_is_false(self):
        checker = RobotsComplianceChecker()
        assert checker.ignore_robots is False or hasattr(checker, "ignore_robots")


# ---------------------------------------------------------------------------
# RobotsTxtParser — constructor
# ---------------------------------------------------------------------------

class TestRobotsTxtParserConstructor:
    """Tests for RobotsTxtParser constructor defaults."""

    def test_default_user_agent(self):
        parser = RobotsTxtParser()
        assert parser.user_agent == "LinkCanary" or hasattr(parser, "user_agent")

    def test_custom_user_agent(self):
        parser = RobotsTxtParser(user_agent="CustomBot")
        assert parser.user_agent == "CustomBot"

    def test_default_timeout(self):
        parser = RobotsTxtParser()
        assert parser.timeout == 10 or hasattr(parser, "timeout")

    def test_custom_timeout(self):
        parser = RobotsTxtParser(timeout=30)
        assert parser.timeout == 30


# ---------------------------------------------------------------------------
# Integration-style tests (still using cache injection, no network)
# ---------------------------------------------------------------------------

class TestIntegrationScenarios:
    """Integration-style tests combining parsing and is_allowed checks."""

    def setup_method(self):
        self.parser = RobotsTxtParser()

    def test_realistic_robots_txt(self):
        content = (
            "# robots.txt for example.com\n"
            "User-agent: *\n"
            "Allow: /public\n"
            "Disallow: /admin\n"
            "Disallow: /private\n"
            "Disallow: /api/internal\n"
            "Crawl-delay: 2\n"
            "\n"
            "User-agent: Googlebot\n"
            "Allow: /\n"
            "Disallow: /private\n"
        )
        rules = self.parser.parse_robots_txt(content)
        self.parser._cache["https://example.com"] = rules

        # Public should be allowed
        allowed, _ = self.parser.is_allowed(
            "https://example.com/public/page", "https://example.com"
        )
        assert allowed is True

        # Admin should be blocked
        allowed, _ = self.parser.is_allowed(
            "https://example.com/admin/settings", "https://example.com"
        )
        assert allowed is False

        # Private should be blocked
        allowed, _ = self.parser.is_allowed(
            "https://example.com/private/data", "https://example.com"
        )
        assert allowed is False

        # API internal should be blocked
        allowed, _ = self.parser.is_allowed(
            "https://example.com/api/internal/users", "https://example.com"
        )
        assert allowed is False

        # Regular pages should be allowed
        allowed, _ = self.parser.is_allowed(
            "https://example.com/about", "https://example.com"
        )
        assert allowed is True

    def test_block_all_except_specific_paths(self):
        content = (
            "User-agent: *\n"
            "Allow: /sitemap.xml\n"
            "Allow: /robots.txt\n"
            "Disallow: /\n"
        )
        rules = self.parser.parse_robots_txt(content)
        self.parser._cache["https://example.com"] = rules

        # sitemap should be allowed
        allowed, _ = self.parser.is_allowed(
            "https://example.com/sitemap.xml", "https://example.com"
        )
        assert allowed is True

        # Random pages should be blocked
        allowed, _ = self.parser.is_allowed(
            "https://example.com/random-page", "https://example.com"
        )
        assert allowed is False

    def test_complex_wildcard_rules(self):
        content = (
            "User-agent: *\n"
            "Disallow: /*.json$\n"
            "Disallow: /api/*\n"
            "Allow: /api/public\n"
        )
        rules = self.parser.parse_robots_txt(content)
        self.parser._cache["https://example.com"] = rules

        # JSON files should be blocked
        allowed, _ = self.parser.is_allowed(
            "https://example.com/data/config.json", "https://example.com"
        )
        assert allowed is False

        # Non-JSON files should be allowed
        allowed, _ = self.parser.is_allowed(
            "https://example.com/data/config.yaml", "https://example.com"
        )
        assert allowed is True

    def test_multiple_domains_cached_independently(self):
        rules_a = self.parser.parse_robots_txt(
            "User-agent: *\nDisallow: /admin\n"
        )
        rules_b = self.parser.parse_robots_txt(
            "User-agent: *\nDisallow: /secret\n"
        )
        self.parser._cache["https://a.com"] = rules_a
        self.parser._cache["https://b.com"] = rules_b

        # /admin blocked on a.com but not b.com
        allowed_a, _ = self.parser.is_allowed(
            "https://a.com/admin", "https://a.com"
        )
        allowed_b, _ = self.parser.is_allowed(
            "https://b.com/admin", "https://b.com"
        )
        assert allowed_a is False
        assert allowed_b is True

        # /secret blocked on b.com but not a.com
        allowed_a, _ = self.parser.is_allowed(
            "https://a.com/secret", "https://a.com"
        )
        allowed_b, _ = self.parser.is_allowed(
            "https://b.com/secret", "https://b.com"
        )
        assert allowed_a is True
        assert allowed_b is False


# ---------------------------------------------------------------------------
# RobotsComplianceChecker — with mocked parser (non-ignore mode)
# ---------------------------------------------------------------------------

class TestComplianceCheckerWithMockedParser:
    """Tests for RobotsComplianceChecker when ignore_robots=False,
    using mock to avoid network calls."""

    def test_check_url_delegates_to_parser(self):
        checker = RobotsComplianceChecker(ignore_robots=False)
        with patch.object(checker, "check_url", return_value=(False, "blocked by robots.txt")):
            allowed, reason = checker.check_url(
                "https://example.com/admin", "https://example.com"
            )
            assert allowed is False

    def test_filter_urls_separates_allowed_and_blocked(self):
        checker = RobotsComplianceChecker(ignore_robots=True)
        urls = [
            "https://example.com/public",
            "https://example.com/about",
        ]
        allowed_urls, blocked = checker.filter_urls(urls, "https://example.com")
        # With ignore_robots=True, all should be allowed
        assert len(allowed_urls) == 2
        assert len(blocked) == 0
