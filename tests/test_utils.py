"""Tests for URL resolution and utility functions.

Focuses on subdirectory URL handling to prevent false positive 404 errors
when crawling WordPress/blog sites with /blog/ or other subdirectory paths.
"""


from link_checker.utils import (
    normalize_url,
    resolve_relative_url,
    is_internal_link,
    should_skip_link,
    is_canonical_redirect,
)


class TestResolveRelativeUrl:
    """Tests for resolve_relative_url with subdirectory paths."""

    def test_absolute_path_preserves_blog_subdirectory(self):
        result = resolve_relative_url(
            "https://example.com/blog/my-post/",
            "/blog/post-name/",
        )
        assert result == "https://example.com/blog/post-name/"

    def test_relative_path_resolves_within_blog(self):
        result = resolve_relative_url(
            "https://example.com/blog/my-post/",
            "other-post/",
        )
        assert result == "https://example.com/blog/my-post/other-post/"

    def test_root_relative_path_without_subdirectory(self):
        result = resolve_relative_url(
            "https://example.com/blog/my-post/",
            "/about/",
        )
        assert result == "https://example.com/about/"

    def test_absolute_url_unchanged(self):
        result = resolve_relative_url(
            "https://example.com/blog/my-post/",
            "https://other.com/page",
        )
        assert result == "https://other.com/page"

    def test_deeply_nested_subdirectory(self):
        result = resolve_relative_url(
            "https://example.com/en/blog/2024/post/",
            "/en/blog/2024/other-post/",
        )
        assert result == "https://example.com/en/blog/2024/other-post/"

    def test_relative_dot_dot_preserves_structure(self):
        result = resolve_relative_url(
            "https://example.com/blog/category/post/",
            "../other-category/",
        )
        assert result == "https://example.com/blog/category/other-category/"

    def test_sitemap_base_with_absolute_href(self):
        result = resolve_relative_url(
            "https://example.com/sitemap.xml",
            "/blog/post-name/",
        )
        assert result == "https://example.com/blog/post-name/"

    def test_wordpress_style_blog_subdirectory(self):
        result = resolve_relative_url(
            "https://example.com/blog/",
            "my-first-post/",
        )
        assert result == "https://example.com/blog/my-first-post/"

    def test_trailing_slash_page_url(self):
        result = resolve_relative_url(
            "https://example.com/blog/my-post/",
            "images/photo.jpg",
        )
        assert result == "https://example.com/blog/my-post/images/photo.jpg"

    def test_no_trailing_slash_page_url(self):
        result = resolve_relative_url(
            "https://example.com/blog/my-post",
            "other-post",
        )
        assert result == "https://example.com/blog/other-post"

    def test_empty_relative_url(self):
        result = resolve_relative_url(
            "https://example.com/blog/",
            "",
        )
        assert result == ""

    def test_fragment_only_skipped(self):
        result = resolve_relative_url(
            "https://example.com/blog/",
            "#section",
        )
        assert result == ""

    def test_mailto_skipped(self):
        result = resolve_relative_url(
            "https://example.com/blog/",
            "mailto:test@example.com",
        )
        assert result == ""

    def test_fragment_stripped_from_result(self):
        result = resolve_relative_url(
            "https://example.com/blog/",
            "/blog/post/#comments",
        )
        assert result == "https://example.com/blog/post/"

    def test_protocol_relative_url(self):
        result = resolve_relative_url(
            "https://example.com/blog/",
            "//cdn.example.com/image.png",
        )
        assert result == "https://cdn.example.com/image.png"

    def test_query_string_preserved(self):
        result = resolve_relative_url(
            "https://example.com/blog/",
            "/blog/search?q=test",
        )
        assert result == "https://example.com/blog/search?q=test"


class TestNormalizeUrl:
    """Tests for URL normalization."""

    def test_lowercase_scheme_and_host(self):
        result = normalize_url("HTTP://EXAMPLE.COM/Blog/Post")
        assert result == "http://example.com/Blog/Post"

    def test_remove_default_http_port(self):
        result = normalize_url("http://example.com:80/blog/")
        assert result == "http://example.com/blog/"

    def test_remove_default_https_port(self):
        result = normalize_url("https://example.com:443/blog/")
        assert result == "https://example.com/blog/"

    def test_keep_non_default_port(self):
        result = normalize_url("http://example.com:8080/blog/")
        assert "8080" in result

    def test_remove_fragment(self):
        result = normalize_url("https://example.com/blog/#section")
        assert result == "https://example.com/blog/"

    def test_sort_query_params(self):
        result = normalize_url("https://example.com/blog/?z=1&a=2")
        assert result == "https://example.com/blog/?a=2&z=1"

    def test_empty_url(self):
        assert normalize_url("") == ""

    def test_subdirectory_path_preserved(self):
        result = normalize_url("https://example.com/blog/my-post/")
        assert result == "https://example.com/blog/my-post/"


class TestIsInternalLink:
    """Tests for internal link detection."""

    def test_same_domain_internal(self):
        assert is_internal_link(
            "https://example.com/blog/post",
            "https://example.com/sitemap.xml",
        )

    def test_different_domain_external(self):
        assert not is_internal_link(
            "https://other.com/page",
            "https://example.com/sitemap.xml",
        )

    def test_subdomain_not_internal_by_default(self):
        assert not is_internal_link(
            "https://blog.example.com/post",
            "https://example.com/sitemap.xml",
        )

    def test_subdomain_internal_when_enabled(self):
        assert is_internal_link(
            "https://blog.example.com/post",
            "https://example.com/sitemap.xml",
            include_subdomains=True,
        )


class TestIsCanonicalRedirect:
    """Tests for canonical redirect detection."""

    def test_trailing_slash_is_canonical(self):
        assert is_canonical_redirect(
            "https://example.com/blog",
            "https://example.com/blog/",
        )

    def test_case_difference_is_canonical(self):
        assert is_canonical_redirect(
            "https://example.com/Blog/",
            "https://example.com/blog/",
        )

    def test_different_path_not_canonical(self):
        assert not is_canonical_redirect(
            "https://example.com/blog/",
            "https://example.com/news/",
        )

    def test_protocol_change_is_canonical(self):
        assert is_canonical_redirect(
            "http://example.com/blog/",
            "https://example.com/blog/",
        )


class TestShouldSkipLink:
    """Tests for link filtering."""

    def test_skip_mailto(self):
        assert should_skip_link("mailto:user@example.com")

    def test_skip_tel(self):
        assert should_skip_link("tel:+1234567890")

    def test_skip_javascript(self):
        assert should_skip_link("javascript:void(0)")

    def test_skip_anchor_only(self):
        assert should_skip_link("#section")

    def test_skip_empty(self):
        assert should_skip_link("")

    def test_allow_relative_path(self):
        assert not should_skip_link("/blog/post/")

    def test_allow_absolute_url(self):
        assert not should_skip_link("https://example.com/")

    def test_allow_relative_no_slash(self):
        assert not should_skip_link("post-name/")
