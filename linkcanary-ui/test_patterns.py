"""Comprehensive tests for link_checker.patterns module."""

import pytest

from link_checker.patterns import (
    PRESET_PATTERNS,
    URLPatternMatcher,
    get_preset_patterns,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_URLS = [
    "https://example.com/blog/post-1",
    "https://example.com/about",
    "https://cdn.example.com/image.png",
    "https://example.com/docs/report.pdf",
    "https://twitter.com/user/status/123",
    "https://linkedin.com/in/johndoe",
    "https://example.com/page?utm_source=google",
    "https://example.com/style.css",
    "https://example.com/app.js",
    "https://example.com/archive.zip",
]


# ===================================================================
# Glob matching – individual pattern styles
# ===================================================================

class TestGlobMatchPathPatterns:
    """Patterns starting with '/' match against the URL path."""

    def test_path_pattern_matches_subpath(self):
        matcher = URLPatternMatcher(include_patterns=["/blog/*"])
        ok, _ = matcher.should_check("https://example.com/blog/post-1")
        assert ok is True

    def test_path_pattern_no_match(self):
        matcher = URLPatternMatcher(include_patterns=["/blog/*"])
        ok, _ = matcher.should_check("https://example.com/about")
        assert ok is False

    def test_path_pattern_exact_segment(self):
        matcher = URLPatternMatcher(include_patterns=["/about"])
        ok, _ = matcher.should_check("https://example.com/about")
        assert ok is True

    def test_path_pattern_nested_wildcard(self):
        matcher = URLPatternMatcher(include_patterns=["/docs/*"])
        ok, _ = matcher.should_check("https://example.com/docs/report.pdf")
        assert ok is True

    def test_path_pattern_does_not_match_different_path(self):
        matcher = URLPatternMatcher(include_patterns=["/docs/*"])
        ok, _ = matcher.should_check("https://example.com/blog/post-1")
        assert ok is False


class TestGlobMatchDomainPatterns:
    """Patterns like *example.com* do domain / substring matching."""

    def test_domain_pattern_matches(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com*"])
        ok, _ = matcher.should_check("https://example.com/page")
        assert ok is True

    def test_domain_pattern_matches_subdomain(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com*"])
        ok, _ = matcher.should_check("https://cdn.example.com/image.png")
        assert ok is True

    def test_domain_pattern_no_match(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com*"])
        ok, _ = matcher.should_check("https://twitter.com/user")
        assert ok is False

    def test_domain_pattern_twitter(self):
        matcher = URLPatternMatcher(include_patterns=["*twitter.com*"])
        ok, _ = matcher.should_check("https://twitter.com/user/status/123")
        assert ok is True


class TestGlobMatchExtensionPatterns:
    """Patterns like *.pdf match file extensions (suffix/substring)."""

    def test_pdf_extension_matches(self):
        matcher = URLPatternMatcher(include_patterns=["*.pdf"])
        ok, _ = matcher.should_check("https://example.com/docs/report.pdf")
        assert ok is True

    def test_pdf_extension_no_match_on_html(self):
        matcher = URLPatternMatcher(include_patterns=["*.pdf"])
        ok, _ = matcher.should_check("https://example.com/about")
        assert ok is False

    def test_png_extension_matches(self):
        matcher = URLPatternMatcher(include_patterns=["*.png"])
        ok, _ = matcher.should_check("https://cdn.example.com/image.png")
        assert ok is True

    def test_css_extension_matches(self):
        matcher = URLPatternMatcher(include_patterns=["*.css"])
        ok, _ = matcher.should_check("https://example.com/style.css")
        assert ok is True


class TestGlobMatchPrefixPatterns:
    """Patterns like 'https://*' – prefix with wildcard."""

    def test_prefix_pattern_matches(self):
        matcher = URLPatternMatcher(include_patterns=["https://example.com/*"])
        ok, _ = matcher.should_check("https://example.com/blog/post-1")
        assert ok is True

    def test_prefix_pattern_no_match_different_domain(self):
        matcher = URLPatternMatcher(include_patterns=["https://example.com/*"])
        ok, _ = matcher.should_check("https://twitter.com/user")
        assert ok is False


class TestGlobMatchWildcardInMiddle:
    """Patterns with wildcards in the middle, e.g. 'example.com/*/post'."""

    def test_wildcard_in_middle(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com/*/post*"])
        ok, _ = matcher.should_check("https://example.com/blog/post-1")
        assert ok is True

    def test_wildcard_in_middle_no_match(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com/*/post*"])
        ok, _ = matcher.should_check("https://example.com/about")
        assert ok is False


class TestGlobMatchSubstringNoWildcards:
    """Patterns without wildcards act as substring matches."""

    def test_substring_match(self):
        matcher = URLPatternMatcher(include_patterns=["example.com"])
        ok, _ = matcher.should_check("https://example.com/page")
        assert ok is True

    def test_substring_match_partial_path(self):
        matcher = URLPatternMatcher(include_patterns=["blog"])
        ok, _ = matcher.should_check("https://example.com/blog/post-1")
        assert ok is True

    def test_substring_no_match(self):
        matcher = URLPatternMatcher(include_patterns=["foobar"])
        ok, _ = matcher.should_check("https://example.com/page")
        assert ok is False

    def test_substring_match_query_param(self):
        matcher = URLPatternMatcher(include_patterns=["utm_source"])
        ok, _ = matcher.should_check("https://example.com/page?utm_source=google")
        assert ok is True


# ===================================================================
# Regex matching mode
# ===================================================================

class TestRegexMatching:
    """Tests with pattern_type='regex'."""

    def test_regex_include_matches(self):
        matcher = URLPatternMatcher(
            include_patterns=[r"https://example\.com/blog/.*"],
            pattern_type="regex",
        )
        ok, _ = matcher.should_check("https://example.com/blog/post-1")
        assert ok is True

    def test_regex_include_no_match(self):
        matcher = URLPatternMatcher(
            include_patterns=[r"https://example\.com/blog/.*"],
            pattern_type="regex",
        )
        ok, _ = matcher.should_check("https://example.com/about")
        assert ok is False

    def test_regex_exclude(self):
        matcher = URLPatternMatcher(
            exclude_patterns=[r".*\.pdf$"],
            pattern_type="regex",
        )
        ok, _ = matcher.should_check("https://example.com/docs/report.pdf")
        assert ok is False

    def test_regex_exclude_does_not_block_non_matching(self):
        matcher = URLPatternMatcher(
            exclude_patterns=[r".*\.pdf$"],
            pattern_type="regex",
        )
        ok, _ = matcher.should_check("https://example.com/about")
        assert ok is True

    def test_regex_include_and_exclude(self):
        matcher = URLPatternMatcher(
            include_patterns=[r"https://example\.com/.*"],
            exclude_patterns=[r".*\.pdf$"],
            pattern_type="regex",
        )
        # Included domain but excluded extension
        ok, _ = matcher.should_check("https://example.com/docs/report.pdf")
        assert ok is False

        # Included domain, not excluded
        ok, _ = matcher.should_check("https://example.com/about")
        assert ok is True

    def test_regex_complex_pattern(self):
        matcher = URLPatternMatcher(
            include_patterns=[r"https?://.*example\.(com|org)/\d+"],
            pattern_type="regex",
        )
        ok, _ = matcher.should_check("https://www.example.com/123")
        assert ok is True

        ok, _ = matcher.should_check("http://example.org/456")
        assert ok is True

        ok, _ = matcher.should_check("https://example.com/about")
        assert ok is False


# ===================================================================
# should_check – filtering logic
# ===================================================================

class TestShouldCheckNoPatterns:
    """When no include/exclude patterns are set, everything passes."""

    def test_no_patterns_returns_true(self):
        matcher = URLPatternMatcher()
        ok, reason = matcher.should_check("https://example.com")
        assert ok is True
        assert "no patterns" in reason.lower() or reason != ""

    def test_no_patterns_any_url(self):
        matcher = URLPatternMatcher()
        for url in SAMPLE_URLS:
            ok, _ = matcher.should_check(url)
            assert ok is True

    def test_empty_lists_treated_as_no_patterns(self):
        matcher = URLPatternMatcher(include_patterns=[], exclude_patterns=[])
        ok, reason = matcher.should_check("https://example.com")
        assert ok is True


class TestShouldCheckOnlyInclude:
    """Only include patterns set – only matching URLs pass."""

    def test_include_match(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com*"])
        ok, _ = matcher.should_check("https://example.com/page")
        assert ok is True

    def test_include_no_match(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com*"])
        ok, _ = matcher.should_check("https://twitter.com/user")
        assert ok is False

    def test_multiple_include_patterns(self):
        matcher = URLPatternMatcher(
            include_patterns=["*example.com*", "*twitter.com*"]
        )
        ok1, _ = matcher.should_check("https://example.com/page")
        ok2, _ = matcher.should_check("https://twitter.com/user")
        ok3, _ = matcher.should_check("https://linkedin.com/in/johndoe")
        assert ok1 is True
        assert ok2 is True
        assert ok3 is False


class TestShouldCheckOnlyExclude:
    """Only exclude patterns set – everything passes except matches."""

    def test_exclude_blocks_match(self):
        matcher = URLPatternMatcher(exclude_patterns=["*.pdf"])
        ok, _ = matcher.should_check("https://example.com/docs/report.pdf")
        assert ok is False

    def test_exclude_allows_non_match(self):
        matcher = URLPatternMatcher(exclude_patterns=["*.pdf"])
        ok, _ = matcher.should_check("https://example.com/about")
        assert ok is True

    def test_multiple_exclude_patterns(self):
        matcher = URLPatternMatcher(
            exclude_patterns=["*.pdf", "*.png", "*.css"]
        )
        ok_pdf, _ = matcher.should_check("https://example.com/report.pdf")
        ok_png, _ = matcher.should_check("https://example.com/image.png")
        ok_css, _ = matcher.should_check("https://example.com/style.css")
        ok_html, _ = matcher.should_check("https://example.com/about")
        assert ok_pdf is False
        assert ok_png is False
        assert ok_css is False
        assert ok_html is True


class TestShouldCheckBothIncludeExclude:
    """Both include and exclude set – exclude takes priority."""

    def test_exclude_overrides_include(self):
        matcher = URLPatternMatcher(
            include_patterns=["*example.com*"],
            exclude_patterns=["*.pdf"],
        )
        # Matches include but also matches exclude → excluded
        ok, _ = matcher.should_check("https://example.com/docs/report.pdf")
        assert ok is False

    def test_included_and_not_excluded(self):
        matcher = URLPatternMatcher(
            include_patterns=["*example.com*"],
            exclude_patterns=["*.pdf"],
        )
        ok, _ = matcher.should_check("https://example.com/about")
        assert ok is True

    def test_not_included_regardless_of_exclude(self):
        matcher = URLPatternMatcher(
            include_patterns=["*example.com*"],
            exclude_patterns=["*.pdf"],
        )
        ok, _ = matcher.should_check("https://twitter.com/user")
        assert ok is False

    def test_reason_string_is_returned(self):
        matcher = URLPatternMatcher(
            include_patterns=["*example.com*"],
            exclude_patterns=["*.pdf"],
        )
        _, reason = matcher.should_check("https://example.com/docs/report.pdf")
        assert isinstance(reason, str)
        assert len(reason) > 0


# ===================================================================
# filter_urls
# ===================================================================

class TestFilterUrls:
    """filter_urls returns (included, excluded) lists."""

    def test_filter_no_patterns(self):
        matcher = URLPatternMatcher()
        included, excluded = matcher.filter_urls(SAMPLE_URLS)
        assert included == SAMPLE_URLS
        assert excluded == []

    def test_filter_with_include(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com*"])
        included, excluded = matcher.filter_urls(SAMPLE_URLS)
        assert all("example.com" in u for u in included)
        assert all("example.com" not in u for u in excluded)

    def test_filter_with_exclude(self):
        matcher = URLPatternMatcher(exclude_patterns=["*.pdf", "*.png"])
        included, excluded = matcher.filter_urls(SAMPLE_URLS)
        assert not any(u.endswith(".pdf") or u.endswith(".png") for u in included)
        assert all(u.endswith(".pdf") or u.endswith(".png") for u in excluded)

    def test_filter_with_both(self):
        matcher = URLPatternMatcher(
            include_patterns=["*example.com*"],
            exclude_patterns=["*.pdf"],
        )
        included, excluded = matcher.filter_urls(SAMPLE_URLS)
        # Included should have example.com URLs that are NOT .pdf
        for u in included:
            assert "example.com" in u
            assert not u.endswith(".pdf")

    def test_filter_empty_list(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com*"])
        included, excluded = matcher.filter_urls([])
        assert included == []
        assert excluded == []

    def test_filter_returns_two_lists(self):
        matcher = URLPatternMatcher()
        result = matcher.filter_urls(SAMPLE_URLS)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[1], list)

    def test_filter_all_excluded(self):
        matcher = URLPatternMatcher(include_patterns=["*nonexistent*"])
        included, excluded = matcher.filter_urls(SAMPLE_URLS)
        assert included == []
        assert len(excluded) == len(SAMPLE_URLS)

    def test_filter_preserves_total_count(self):
        matcher = URLPatternMatcher(
            include_patterns=["*example.com*"],
            exclude_patterns=["*.pdf"],
        )
        included, excluded = matcher.filter_urls(SAMPLE_URLS)
        assert len(included) + len(excluded) == len(SAMPLE_URLS)


# ===================================================================
# get_stats
# ===================================================================

class TestGetStats:
    """get_stats returns a dict with pattern count information."""

    def test_stats_no_patterns(self):
        matcher = URLPatternMatcher()
        stats = matcher.get_stats()
        assert isinstance(stats, dict)

    def test_stats_with_include(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com*", "*.pdf"])
        stats = matcher.get_stats()
        assert isinstance(stats, dict)
        # Should reflect 2 include patterns
        values = list(stats.values())
        # At least one numeric value should be 2
        assert any(v == 2 for v in values if isinstance(v, int))

    def test_stats_with_exclude(self):
        matcher = URLPatternMatcher(exclude_patterns=["*.pdf", "*.png", "*.css"])
        stats = matcher.get_stats()
        assert isinstance(stats, dict)
        values = list(stats.values())
        assert any(v == 3 for v in values if isinstance(v, int))

    def test_stats_with_both(self):
        matcher = URLPatternMatcher(
            include_patterns=["*example.com*"],
            exclude_patterns=["*.pdf", "*.png"],
        )
        stats = matcher.get_stats()
        assert isinstance(stats, dict)


# ===================================================================
# Preset patterns
# ===================================================================

class TestPresetPatterns:
    """Tests for PRESET_PATTERNS and get_preset_patterns."""

    def test_preset_patterns_is_dict(self):
        assert isinstance(PRESET_PATTERNS, dict)

    def test_preset_social_media_exists(self):
        assert "social-media" in PRESET_PATTERNS

    def test_preset_documents_exists(self):
        assert "documents" in PRESET_PATTERNS

    def test_preset_media_exists(self):
        assert "media" in PRESET_PATTERNS

    def test_preset_tracking_exists(self):
        assert "tracking" in PRESET_PATTERNS

    def test_preset_patterns_are_lists(self):
        for name, patterns in PRESET_PATTERNS.items():
            assert isinstance(patterns, list), f"Preset '{name}' is not a list"
            assert len(patterns) > 0, f"Preset '{name}' is empty"

    def test_get_preset_patterns_returns_list(self):
        result = get_preset_patterns("social-media")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_preset_patterns_social_media(self):
        patterns = get_preset_patterns("social-media")
        # Should contain well-known social media domains
        combined = " ".join(patterns)
        assert "linkedin" in combined.lower() or "twitter" in combined.lower()

    def test_get_preset_patterns_documents(self):
        patterns = get_preset_patterns("documents")
        combined = " ".join(patterns)
        assert ".pdf" in combined

    def test_get_preset_patterns_media(self):
        patterns = get_preset_patterns("media")
        combined = " ".join(patterns)
        assert ".jpg" in combined or ".png" in combined

    def test_get_preset_patterns_tracking(self):
        patterns = get_preset_patterns("tracking")
        combined = " ".join(patterns)
        assert "utm_source" in combined

    def test_get_preset_invalid_name(self):
        """Requesting a non-existent preset should fail or return empty."""
        with pytest.raises((KeyError, ValueError)):
            get_preset_patterns("nonexistent-preset")

    def test_preset_used_as_exclude(self):
        """Using a preset as exclude patterns works with the matcher."""
        social = get_preset_patterns("social-media")
        matcher = URLPatternMatcher(exclude_patterns=social)
        # Social media URLs should be excluded
        ok_tw, _ = matcher.should_check("https://twitter.com/user/status/1")
        ok_li, _ = matcher.should_check("https://linkedin.com/in/johndoe")
        # Non-social URL should pass
        ok_ex, _ = matcher.should_check("https://example.com/page")
        assert ok_tw is False
        assert ok_li is False
        assert ok_ex is True


# ===================================================================
# Edge cases
# ===================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_url_with_no_patterns(self):
        matcher = URLPatternMatcher()
        ok, _ = matcher.should_check("")
        assert ok is True

    def test_empty_url_with_include(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com*"])
        ok, _ = matcher.should_check("")
        assert ok is False

    def test_url_with_fragment(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com*"])
        ok, _ = matcher.should_check("https://example.com/page#section")
        assert ok is True

    def test_url_with_query_params(self):
        matcher = URLPatternMatcher(include_patterns=["*utm_source*"])
        ok, _ = matcher.should_check("https://example.com/page?utm_source=google")
        assert ok is True

    def test_url_with_port(self):
        matcher = URLPatternMatcher(include_patterns=["*localhost*"])
        ok, _ = matcher.should_check("http://localhost:8080/api/test")
        assert ok is True

    def test_case_sensitivity_in_domain(self):
        """URLs may have mixed-case domains."""
        matcher = URLPatternMatcher(include_patterns=["*example.com*"])
        ok, _ = matcher.should_check("https://Example.Com/page")
        # Behavior depends on implementation; just ensure no crash
        assert isinstance(ok, bool)

    def test_special_characters_in_url(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com*"])
        ok, _ = matcher.should_check(
            "https://example.com/path?q=hello+world&lang=en"
        )
        assert ok is True

    def test_encoded_url(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com*"])
        ok, _ = matcher.should_check(
            "https://example.com/path%20with%20spaces"
        )
        assert ok is True

    def test_should_check_returns_tuple(self):
        matcher = URLPatternMatcher()
        result = matcher.should_check("https://example.com")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_very_long_url(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com*"])
        long_url = "https://example.com/" + "a" * 10000
        ok, _ = matcher.should_check(long_url)
        assert ok is True

    def test_none_patterns_treated_as_empty(self):
        matcher = URLPatternMatcher(include_patterns=None, exclude_patterns=None)
        ok, _ = matcher.should_check("https://example.com")
        assert ok is True


# ===================================================================
# Constructor / pattern_type parameter
# ===================================================================

class TestConstructor:
    """Test URLPatternMatcher construction."""

    def test_default_construction(self):
        matcher = URLPatternMatcher()
        assert matcher is not None

    def test_glob_pattern_type(self):
        matcher = URLPatternMatcher(pattern_type="glob")
        ok, _ = matcher.should_check("https://example.com")
        assert ok is True

    def test_regex_pattern_type(self):
        matcher = URLPatternMatcher(pattern_type="regex")
        ok, _ = matcher.should_check("https://example.com")
        assert ok is True

    def test_include_only(self):
        matcher = URLPatternMatcher(include_patterns=["*example.com*"])
        assert matcher is not None

    def test_exclude_only(self):
        matcher = URLPatternMatcher(exclude_patterns=["*.pdf"])
        assert matcher is not None

    def test_both_patterns(self):
        matcher = URLPatternMatcher(
            include_patterns=["*example.com*"],
            exclude_patterns=["*.pdf"],
        )
        assert matcher is not None


# ===================================================================
# Integration-style tests combining multiple features
# ===================================================================

class TestIntegration:
    """Integration tests combining multiple features."""

    def test_exclude_social_media_and_documents(self):
        social = get_preset_patterns("social-media")
        docs = get_preset_patterns("documents")
        matcher = URLPatternMatcher(exclude_patterns=social + docs)
        included, excluded = matcher.filter_urls(SAMPLE_URLS)
        # Social media and document URLs should be excluded
        for u in included:
            assert "twitter.com" not in u
            assert "linkedin.com" not in u
            assert not u.endswith(".pdf")

    def test_include_domain_exclude_extensions(self):
        matcher = URLPatternMatcher(
            include_patterns=["*example.com*"],
            exclude_patterns=["*.pdf", "*.png", "*.css", "*.js", "*.zip"],
        )
        included, excluded = matcher.filter_urls(SAMPLE_URLS)
        for u in included:
            assert "example.com" in u
            assert not any(
                u.endswith(ext) for ext in [".pdf", ".png", ".css", ".js", ".zip"]
            )

    def test_filter_then_stats(self):
        matcher = URLPatternMatcher(
            include_patterns=["*example.com*"],
            exclude_patterns=["*.pdf"],
        )
        matcher.filter_urls(SAMPLE_URLS)
        stats = matcher.get_stats()
        assert isinstance(stats, dict)

    def test_regex_filter_urls(self):
        matcher = URLPatternMatcher(
            include_patterns=[r"https://example\.com/.*"],
            pattern_type="regex",
        )
        included, excluded = matcher.filter_urls(SAMPLE_URLS)
        for u in included:
            assert u.startswith("https://example.com/")
