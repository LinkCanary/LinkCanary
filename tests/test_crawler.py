"""Tests for the PageCrawler link extraction.

Focuses on <base> HTML tag handling and subdirectory URL resolution
to prevent false positive 404 errors.
"""

import pytest

from link_checker.crawler import PageCrawler


@pytest.fixture
def crawler():
    return PageCrawler(base_url="https://example.com")


class TestBaseTagHandling:
    """Tests for base href tag support in link extraction."""

    def test_base_tag_overrides_page_url(self, crawler):
        html = '<html><head><base href="https://example.com/blog/"></head><body><a href="post-name/">Post</a></body></html>'
        links = crawler.extract_links("https://example.com/other-page/", html)
        assert len(links) == 1
        assert links[0].link_url == "https://example.com/blog/post-name/"

    def test_base_tag_with_root_domain(self, crawler):
        html = '<html><head><base href="https://example.com/"></head><body><a href="blog/post-name/">Post</a></body></html>'
        links = crawler.extract_links("https://example.com/blog/my-post/", html)
        assert len(links) == 1
        assert links[0].link_url == "https://example.com/blog/post-name/"

    def test_no_base_tag_uses_page_url(self, crawler):
        html = '<html><body><a href="other-post/">Post</a></body></html>'
        links = crawler.extract_links("https://example.com/blog/my-post/", html)
        assert len(links) == 1
        assert links[0].link_url == "https://example.com/blog/my-post/other-post/"

    def test_base_tag_with_absolute_href_links(self, crawler):
        html = '<html><head><base href="https://example.com/blog/"></head><body><a href="/about/">About</a></body></html>'
        links = crawler.extract_links("https://example.com/blog/post/", html)
        assert len(links) == 1
        assert links[0].link_url == "https://example.com/about/"

    def test_base_tag_empty_href_ignored(self, crawler):
        html = '<html><head><base href=""></head><body><a href="post/">Post</a></body></html>'
        links = crawler.extract_links("https://example.com/blog/", html)
        assert len(links) == 1
        assert links[0].link_url == "https://example.com/blog/post/"

    def test_base_tag_relative_path_resolved(self, crawler):
        html = '<html><head><base href="/blog/"></head><body><a href="post-name/">Post</a></body></html>'
        links = crawler.extract_links("https://example.com/other/", html)
        assert len(links) == 1
        assert links[0].link_url == "https://example.com/blog/post-name/"

    def test_wordpress_blog_with_base_tag(self, crawler):
        html = '<html><head><base href="https://example.com/"></head><body><a href="/blog/my-post/">My Post</a><a href="/blog/other-post/">Other Post</a><a href="/about/">About</a></body></html>'
        links = crawler.extract_links("https://example.com/blog/page/", html)
        urls = [link.link_url for link in links]
        assert "https://example.com/blog/my-post/" in urls
        assert "https://example.com/blog/other-post/" in urls
        assert "https://example.com/about/" in urls


class TestSubdirectoryLinkExtraction:
    """Tests for subdirectory URL resolution without base tags."""

    def test_blog_subdirectory_absolute_paths(self, crawler):
        html = '<html><body><a href="/blog/post-one/">Post 1</a><a href="/blog/post-two/">Post 2</a></body></html>'
        links = crawler.extract_links("https://example.com/blog/", html)
        urls = [link.link_url for link in links]
        assert "https://example.com/blog/post-one/" in urls
        assert "https://example.com/blog/post-two/" in urls

    def test_blog_subdirectory_relative_paths(self, crawler):
        html = '<html><body><a href="post-one/">Post 1</a><a href="post-two/">Post 2</a></body></html>'
        links = crawler.extract_links("https://example.com/blog/", html)
        urls = [link.link_url for link in links]
        assert "https://example.com/blog/post-one/" in urls
        assert "https://example.com/blog/post-two/" in urls

    def test_skips_mailto_and_javascript(self, crawler):
        html = '<html><body><a href="mailto:test@example.com">Email</a><a href="javascript:void(0)">Click</a><a href="/blog/real-post/">Real</a></body></html>'
        links = crawler.extract_links("https://example.com/blog/", html)
        assert len(links) == 1
        assert links[0].link_url == "https://example.com/blog/real-post/"

    def test_external_links_marked_correctly(self, crawler):
        html = '<html><body><a href="https://other.com/page">External</a><a href="/blog/post/">Internal</a></body></html>'
        links = crawler.extract_links("https://example.com/blog/", html)
        external = [lnk for lnk in links if not lnk.is_internal]
        internal = [lnk for lnk in links if lnk.is_internal]
        assert len(external) == 1
        assert len(internal) == 1

    def test_link_text_extracted(self, crawler):
        html = '<html><body><a href="/blog/post/">My Blog Post Title</a></body></html>'
        links = crawler.extract_links("https://example.com/blog/", html)
        assert links[0].link_text == "My Blog Post Title"

    def test_source_url_tracked(self, crawler):
        html = '<html><body><a href="/page/">Link</a></body></html>'
        links = crawler.extract_links("https://example.com/blog/post/", html)
        assert links[0].source_url == "https://example.com/blog/post/"
