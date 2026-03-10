"""Tests for the backlink checker.

Focuses on <base> HTML tag support, relative URL resolution,
and subdirectory URL handling to prevent false positives.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'linkcanary-ui'))

from linkcanary_ui.api.backlinks import (  # noqa: E402
    contains_link,
    _normalize_for_comparison,
)


class TestNormalizeForComparison:
    """Tests for URL normalization used in backlink comparison."""

    def test_adds_https_scheme(self):
        assert _normalize_for_comparison("example.com/blog/").startswith("https://")

    def test_protocol_relative(self):
        result = _normalize_for_comparison("//example.com/blog/post")
        assert result.startswith("https://example.com")

    def test_already_has_scheme(self):
        result = _normalize_for_comparison("https://example.com/blog/")
        assert result.startswith("https://example.com")

    def test_strips_whitespace(self):
        result = _normalize_for_comparison("  https://example.com/blog/  ")
        assert "  " not in result


class TestContainsLinkAbsolute:
    """Tests for contains_link with absolute URLs."""

    def test_exact_match(self):
        html = '<a href="https://example.com/blog/post-1/">Post 1</a>'
        found, text = contains_link(html, "https://example.com/blog/post-1/")
        assert found is True
        assert text == "Post 1"

    def test_no_match(self):
        html = '<a href="https://example.com/other/">Other</a>'
        found, _ = contains_link(html, "https://example.com/blog/post-1/")
        assert found is False

    def test_trailing_slash_match(self):
        html = '<a href="https://example.com/blog/post-1">Post</a>'
        found, _ = contains_link(html, "https://example.com/blog/post-1/")
        assert found is True

    def test_extracts_link_text(self):
        html = '<a href="https://example.com/target">Click <strong>here</strong></a>'
        found, text = contains_link(html, "https://example.com/target")
        assert found is True
        assert text == "Click here"


class TestContainsLinkRelative:
    """Tests for contains_link with relative URLs (subdirectory bug fix)."""

    def test_relative_path_on_blog_page(self):
        html = '<a href="other-post/">Other</a>'
        found, _ = contains_link(
            html,
            "https://example.com/blog/my-post/other-post/",
            source_url="https://example.com/blog/my-post/",
        )
        assert found is True

    def test_absolute_path_preserves_blog(self):
        html = '<a href="/blog/target-post/">Target</a>'
        found, _ = contains_link(
            html,
            "https://example.com/blog/target-post/",
            source_url="https://example.com/blog/my-post/",
        )
        assert found is True

    def test_root_relative_without_subdirectory(self):
        html = '<a href="/about/">About</a>'
        found, _ = contains_link(
            html,
            "https://example.com/about/",
            source_url="https://example.com/blog/my-post/",
        )
        assert found is True

    def test_relative_without_source_url_skips(self):
        html = '<a href="/blog/post/">Post</a>'
        found, _ = contains_link(html, "https://example.com/blog/post/")
        assert found is False


class TestContainsLinkBaseTag:
    """Tests for contains_link with <base href> tag (WordPress subdirectory fix)."""

    def test_base_tag_resolves_relative_links(self):
        html = '<html><head><base href="https://example.com/blog/"></head><body><a href="target-post/">Target</a></body></html>'
        found, text = contains_link(
            html,
            "https://example.com/blog/target-post/",
            source_url="https://example.com/other-page/",
        )
        assert found is True
        assert text == "Target"

    def test_base_tag_with_subdirectory_path(self):
        html = '<html><head><base href="https://example.com/blog/category/"></head><body><a href="my-post/">My Post</a></body></html>'
        found, _ = contains_link(
            html,
            "https://example.com/blog/category/my-post/",
            source_url="https://example.com/",
        )
        assert found is True

    def test_base_tag_does_not_affect_absolute_urls(self):
        html = '<html><head><base href="https://example.com/blog/"></head><body><a href="https://other.com/page/">External</a></body></html>'
        found, _ = contains_link(
            html,
            "https://other.com/page/",
            source_url="https://example.com/",
        )
        assert found is True

    def test_no_base_tag_uses_source_url(self):
        html = '<html><head></head><body><a href="post-name/">Post</a></body></html>'
        found, _ = contains_link(
            html,
            "https://example.com/blog/current/post-name/",
            source_url="https://example.com/blog/current/",
        )
        assert found is True

    def test_empty_base_href_uses_source_url(self):
        html = '<html><head><base href=""></head><body><a href="/blog/post/">Post</a></body></html>'
        found, _ = contains_link(
            html,
            "https://example.com/blog/post/",
            source_url="https://example.com/page/",
        )
        assert found is True

    def test_base_tag_relative_path(self):
        html = '<html><head><base href="/blog/"></head><body><a href="my-post/">Post</a></body></html>'
        found, _ = contains_link(
            html,
            "https://example.com/blog/my-post/",
            source_url="https://example.com/other/",
        )
        assert found is True

    def test_wordpress_blog_subdirectory_scenario(self):
        """Simulates a WordPress site at /blog/ with relative internal links."""
        html = '''
        <html><head>
            <base href="https://myblog.com/blog/">
        </head><body>
            <nav>
                <a href="category/tech/">Tech</a>
                <a href="category/news/">News</a>
            </nav>
            <article>
                <a href="2024/01/my-article/">My Article</a>
                <a href="/blog/about/">About</a>
            </article>
        </body></html>
        '''
        found, _ = contains_link(
            html,
            "https://myblog.com/blog/2024/01/my-article/",
            source_url="https://myblog.com/blog/index.html",
        )
        assert found is True

        found, _ = contains_link(
            html,
            "https://myblog.com/blog/about/",
            source_url="https://myblog.com/blog/index.html",
        )
        assert found is True


class TestContainsLinkEdgeCases:
    """Edge case tests for contains_link."""

    def test_empty_html(self):
        found, _ = contains_link("", "https://example.com")
        assert found is False

    def test_malformed_html(self):
        html = '<a href="https://example.com/page">unclosed'
        found, _ = contains_link(html, "https://example.com/page")
        assert found is True

    def test_multiple_links_finds_target(self):
        html = '''
        <a href="https://example.com/other">Other</a>
        <a href="https://example.com/target">Target</a>
        <a href="https://example.com/another">Another</a>
        '''
        found, text = contains_link(html, "https://example.com/target")
        assert found is True
        assert text == "Target"

    def test_protocol_relative_link(self):
        html = '<a href="//example.com/page">Page</a>'
        found, _ = contains_link(
            html,
            "https://example.com/page",
            source_url="https://example.com/",
        )
        assert found is True
