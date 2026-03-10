"""Tests for URL pattern matching."""

import pytest

from link_checker.patterns import (
    URLPatternMatcher,
    PRESET_PATTERNS,
    get_preset_patterns,
)


class TestGlobPathPatterns:

    def test_path_pattern_matches_exact(self):
        m = URLPatternMatcher(include_patterns=["/blog/*"])
        ok, _ = m.should_check("https://example.com/blog/post")
        assert ok

    def test_path_pattern_no_match(self):
        m = URLPatternMatcher(include_patterns=["/blog/*"])
        ok, _ = m.should_check("https://example.com/about")
        assert not ok

    def test_path_pattern_nested(self):
        m = URLPatternMatcher(include_patterns=["/docs/*"])
        ok, _ = m.should_check("https://example.com/docs/api/v2")
        assert ok

    def test_path_pattern_substring_fallback(self):
        m = URLPatternMatcher(include_patterns=["/blog/"])
        ok, _ = m.should_check("https://example.com/blog/post")
        assert ok


class TestGlobDomainPatterns:

    def test_domain_pattern_match(self):
        m = URLPatternMatcher(exclude_patterns=["*linkedin.com*"])
        ok, _ = m.should_check("https://www.linkedin.com/in/user")
        assert not ok

    def test_domain_pattern_no_match(self):
        m = URLPatternMatcher(exclude_patterns=["*linkedin.com*"])
        ok, _ = m.should_check("https://example.com/page")
        assert ok


class TestGlobExtensionPatterns:

    def test_pdf_extension(self):
        m = URLPatternMatcher(exclude_patterns=["*.pdf"])
        ok, _ = m.should_check("https://example.com/doc.pdf")
        assert not ok

    def test_non_matching_extension(self):
        m = URLPatternMatcher(exclude_patterns=["*.pdf"])
        ok, _ = m.should_check("https://example.com/page.html")
        assert ok

    def test_jpg_extension(self):
        m = URLPatternMatcher(exclude_patterns=["*.jpg"])
        ok, _ = m.should_check("https://example.com/photo.jpg")
        assert not ok


class TestGlobWildcardMiddle:

    def test_wildcard_in_middle(self):
        m = URLPatternMatcher(include_patterns=["https://example.com/*/page"])
        ok, _ = m.should_check("https://example.com/blog/page")
        assert ok


class TestGlobSubstringNoWildcards:

    def test_substring_match(self):
        m = URLPatternMatcher(exclude_patterns=["linkedin.com"])
        ok, _ = m.should_check("https://www.linkedin.com/in/user")
        assert not ok

    def test_substring_no_match(self):
        m = URLPatternMatcher(exclude_patterns=["linkedin.com"])
        ok, _ = m.should_check("https://example.com/page")
        assert ok


class TestGlobPrefixPatterns:

    def test_prefix_wildcard(self):
        m = URLPatternMatcher(include_patterns=["https://example.com/*"])
        ok, _ = m.should_check("https://example.com/blog/post")
        assert ok

    def test_prefix_no_match(self):
        m = URLPatternMatcher(include_patterns=["https://example.com/*"])
        ok, _ = m.should_check("https://other.com/page")
        assert not ok


class TestRegexMatching:

    def test_regex_include(self):
        m = URLPatternMatcher(
            include_patterns=[r"example\.com/blog/\d+"],
            pattern_type="regex",
        )
        ok, _ = m.should_check("https://example.com/blog/123")
        assert ok

    def test_regex_no_match(self):
        m = URLPatternMatcher(
            include_patterns=[r"example\.com/blog/\d+"],
            pattern_type="regex",
        )
        ok, _ = m.should_check("https://example.com/blog/about")
        assert not ok

    def test_regex_exclude(self):
        m = URLPatternMatcher(
            exclude_patterns=[r"\.(pdf|doc)$"],
            pattern_type="regex",
        )
        ok, _ = m.should_check("https://example.com/file.pdf")
        assert not ok


class TestShouldCheckNoPatterns:

    def test_no_patterns_allows_all(self):
        m = URLPatternMatcher()
        ok, reason = m.should_check("https://example.com/anything")
        assert ok
        assert reason == "no patterns"


class TestShouldCheckOnlyInclude:

    def test_matching_include(self):
        m = URLPatternMatcher(include_patterns=["*example.com*"])
        ok, _ = m.should_check("https://example.com/page")
        assert ok

    def test_non_matching_include(self):
        m = URLPatternMatcher(include_patterns=["*example.com*"])
        ok, reason = m.should_check("https://other.com/page")
        assert not ok
        assert "not in include" in reason


class TestShouldCheckOnlyExclude:

    def test_matching_exclude(self):
        m = URLPatternMatcher(exclude_patterns=["*linkedin.com*"])
        ok, _ = m.should_check("https://linkedin.com/in/user")
        assert not ok

    def test_non_matching_exclude(self):
        m = URLPatternMatcher(exclude_patterns=["*linkedin.com*"])
        ok, reason = m.should_check("https://example.com/page")
        assert ok
        assert "not excluded" in reason


class TestShouldCheckBoth:

    def test_exclude_takes_priority(self):
        m = URLPatternMatcher(
            include_patterns=["*example.com*"],
            exclude_patterns=["*.pdf"],
        )
        ok, _ = m.should_check("https://example.com/file.pdf")
        assert not ok

    def test_included_not_excluded(self):
        m = URLPatternMatcher(
            include_patterns=["*example.com*"],
            exclude_patterns=["*.pdf"],
        )
        ok, _ = m.should_check("https://example.com/page.html")
        assert ok


class TestFilterUrls:

    def test_filter_splits_correctly(self):
        m = URLPatternMatcher(exclude_patterns=["*linkedin.com*"])
        included, excluded = m.filter_urls([
            "https://example.com/page",
            "https://linkedin.com/in/user",
            "https://example.com/about",
        ])
        assert len(included) == 2
        assert len(excluded) == 1
        assert "https://linkedin.com/in/user" in excluded

    def test_filter_empty_list(self):
        m = URLPatternMatcher(exclude_patterns=["*.pdf"])
        included, excluded = m.filter_urls([])
        assert included == []
        assert excluded == []


class TestGetStats:

    def test_stats_structure(self):
        m = URLPatternMatcher(
            include_patterns=["*.html"],
            exclude_patterns=["*.pdf", "*.doc"],
            pattern_type="glob",
        )
        stats = m.get_stats()
        assert stats["include_patterns"] == 1
        assert stats["exclude_patterns"] == 2
        assert stats["pattern_type"] == "glob"


class TestPresetPatterns:

    def test_social_media_preset_exists(self):
        assert "social-media" in PRESET_PATTERNS
        assert len(PRESET_PATTERNS["social-media"]) > 0

    def test_documents_preset_exists(self):
        assert "documents" in PRESET_PATTERNS

    def test_media_preset_exists(self):
        assert "media" in PRESET_PATTERNS

    def test_tracking_preset_exists(self):
        assert "tracking" in PRESET_PATTERNS

    def test_get_preset_patterns_known(self):
        patterns = get_preset_patterns("social-media")
        assert len(patterns) > 0
        assert any("linkedin" in p for p in patterns)

    def test_get_preset_patterns_unknown(self):
        patterns = get_preset_patterns("nonexistent")
        assert patterns == []


class TestEdgeCases:

    def test_empty_url(self):
        m = URLPatternMatcher(include_patterns=["*example.com*"])
        ok, _ = m.should_check("")
        assert not ok

    def test_url_with_query_params(self):
        m = URLPatternMatcher(exclude_patterns=["*utm_source*"])
        ok, _ = m.should_check("https://example.com/page?utm_source=google")
        assert not ok

    def test_url_with_port(self):
        m = URLPatternMatcher(include_patterns=["*example.com*"])
        ok, _ = m.should_check("https://example.com:8080/page")
        assert ok
