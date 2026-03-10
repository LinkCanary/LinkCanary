"""Integration tests simulating real WordPress /blog/ subdirectory site crawls.

These tests verify the complete crawl pipeline handles subdirectory URLs
correctly, from HTML parsing through link extraction to URL resolution.
"""

from unittest.mock import patch

from link_checker.crawler import PageCrawler
from link_checker.utils import resolve_relative_url, normalize_url


WORDPRESS_BLOG_HOME = """
<!DOCTYPE html>
<html>
<head>
    <base href="https://myblog.com/blog/">
    <title>My Blog</title>
</head>
<body>
    <nav>
        <a href="/blog/">Home</a>
        <a href="category/tech/">Tech</a>
        <a href="category/news/">News</a>
        <a href="/blog/about/">About</a>
        <a href="/contact/">Contact</a>
    </nav>
    <article>
        <h2><a href="2024/01/hello-world/">Hello World</a></h2>
        <p>Welcome to my blog.</p>
    </article>
    <article>
        <h2><a href="2024/02/second-post/">Second Post</a></h2>
        <p>Another post.</p>
    </article>
    <footer>
        <a href="https://external.com/link">External</a>
        <a href="//cdn.example.com/asset.js">CDN Asset</a>
    </footer>
</body>
</html>
"""

WORDPRESS_BLOG_POST = """
<!DOCTYPE html>
<html>
<head>
    <base href="https://myblog.com/blog/">
    <title>Hello World - My Blog</title>
</head>
<body>
    <nav>
        <a href="/blog/">Home</a>
        <a href="category/tech/">Tech</a>
    </nav>
    <article>
        <h1>Hello World</h1>
        <p>Read my <a href="2024/02/second-post/">next post</a>.</p>
        <p>Check out <a href="/blog/category/tech/">tech articles</a>.</p>
        <img src="/blog/wp-content/uploads/image.png" alt="Photo">
    </article>
</body>
</html>
"""

WORDPRESS_NO_BASE_TAG = """
<!DOCTYPE html>
<html>
<head><title>Blog Post</title></head>
<body>
    <a href="/blog/other-post/">Other Post</a>
    <a href="/blog/category/news/">News</a>
    <a href="/about/">About Site</a>
    <a href="relative-page/">Relative</a>
</body>
</html>
"""

WORDPRESS_SUBDIRECTORY_DEEP = """
<!DOCTYPE html>
<html>
<head>
    <base href="https://example.com/sites/blog/">
    <title>Deep Subdirectory Blog</title>
</head>
<body>
    <a href="posts/my-article/">My Article</a>
    <a href="/sites/blog/archive/">Archive</a>
    <a href="https://example.com/sites/blog/tags/">Tags</a>
</body>
</html>
"""


class TestWordPressBlogCrawlEndToEnd:
    """Simulate crawling a WordPress site installed at /blog/ subdirectory."""

    def _make_crawler(self, base_url="https://myblog.com/blog/"):
        return PageCrawler(base_url=base_url, delay=0)

    def test_blog_home_extracts_all_links(self):
        crawler = self._make_crawler()
        links = crawler.extract_links(
            "https://myblog.com/blog/", WORDPRESS_BLOG_HOME
        )
        urls = [link.link_url for link in links if link.element_type == 'a']
        assert "https://myblog.com/blog/" in urls
        assert "https://myblog.com/blog/category/tech/" in urls
        assert "https://myblog.com/blog/category/news/" in urls
        assert "https://myblog.com/blog/about/" in urls
        assert "https://myblog.com/contact/" in urls
        assert "https://myblog.com/blog/2024/01/hello-world/" in urls
        assert "https://myblog.com/blog/2024/02/second-post/" in urls
        assert "https://external.com/link" in urls
        crawler.close()

    def test_blog_home_no_stripped_paths(self):
        """Verify /blog/ is never stripped from resolved URLs."""
        crawler = self._make_crawler()
        links = crawler.extract_links(
            "https://myblog.com/blog/", WORDPRESS_BLOG_HOME
        )
        internal_urls = [
            link.link_url for link in links
            if link.is_internal and link.element_type == 'a'
        ]
        for url in internal_urls:
            if "myblog.com" in url and url != "https://myblog.com/contact/":
                assert "/blog/" in url, f"URL missing /blog/ subdirectory: {url}"
        crawler.close()

    def test_blog_post_page_links(self):
        crawler = self._make_crawler()
        links = crawler.extract_links(
            "https://myblog.com/blog/2024/01/hello-world/",
            WORDPRESS_BLOG_POST,
        )
        urls = [link.link_url for link in links]
        assert "https://myblog.com/blog/2024/02/second-post/" in urls
        assert "https://myblog.com/blog/category/tech/" in urls
        assert "https://myblog.com/blog/wp-content/uploads/image.png" in urls
        crawler.close()

    def test_no_base_tag_uses_page_url(self):
        """When no <base> tag, relative URLs resolve against the page URL."""
        crawler = self._make_crawler()
        links = crawler.extract_links(
            "https://myblog.com/blog/2024/01/hello-world/",
            WORDPRESS_NO_BASE_TAG,
        )
        urls = [link.link_url for link in links]
        assert "https://myblog.com/blog/other-post/" in urls
        assert "https://myblog.com/blog/category/news/" in urls
        assert "https://myblog.com/about/" in urls
        assert "https://myblog.com/blog/2024/01/hello-world/relative-page/" in urls
        crawler.close()

    def test_deep_subdirectory_blog(self):
        """Test a blog at /sites/blog/ (two levels deep)."""
        crawler = self._make_crawler(base_url="https://example.com/sites/blog/")
        links = crawler.extract_links(
            "https://example.com/sites/blog/",
            WORDPRESS_SUBDIRECTORY_DEEP,
        )
        urls = [link.link_url for link in links]
        assert "https://example.com/sites/blog/posts/my-article/" in urls
        assert "https://example.com/sites/blog/archive/" in urls
        assert "https://example.com/sites/blog/tags/" in urls
        crawler.close()

    def test_internal_external_classification(self):
        crawler = self._make_crawler()
        links = crawler.extract_links(
            "https://myblog.com/blog/", WORDPRESS_BLOG_HOME
        )
        internal = [lnk for lnk in links if lnk.is_internal and lnk.element_type == 'a']
        external = [lnk for lnk in links if not lnk.is_internal and lnk.element_type == 'a']
        internal_urls = [lnk.link_url for lnk in internal]
        external_urls = [lnk.link_url for lnk in external]
        assert "https://myblog.com/blog/category/tech/" in internal_urls
        assert "https://external.com/link" in external_urls
        crawler.close()


class TestCrawlPipelineWithMockedHTTP:
    """Test the full crawl_page pipeline with mocked HTTP responses."""

    @patch.object(PageCrawler, 'fetch_page')
    def test_crawl_page_wordpress_blog(self, mock_fetch):
        mock_fetch.return_value = WORDPRESS_BLOG_HOME
        crawler = PageCrawler(
            base_url="https://myblog.com/blog/",
            delay=0,
        )
        links = crawler.crawl_page("https://myblog.com/blog/")
        a_links = [lnk for lnk in links if lnk.element_type == 'a']
        assert len(a_links) >= 7
        urls = [lnk.link_url for lnk in a_links]
        assert "https://myblog.com/blog/2024/01/hello-world/" in urls
        assert "https://myblog.com/blog/category/tech/" in urls
        crawler.close()

    @patch.object(PageCrawler, 'fetch_page')
    def test_crawl_multiple_pages_no_path_stripping(self, mock_fetch):
        """Crawl multiple pages and verify no /blog/ paths get stripped."""
        def side_effect(url):
            if url == "https://myblog.com/blog/":
                return WORDPRESS_BLOG_HOME
            elif "hello-world" in url:
                return WORDPRESS_BLOG_POST
            return None

        mock_fetch.side_effect = side_effect
        crawler = PageCrawler(
            base_url="https://myblog.com/blog/",
            delay=0,
        )
        all_links = crawler.crawl_pages([
            "https://myblog.com/blog/",
            "https://myblog.com/blog/2024/01/hello-world/",
        ])
        a_links = [lnk for lnk in all_links if lnk.element_type == 'a']
        for link in a_links:
            if "myblog.com" in link.link_url and "/blog/" not in link.link_url:
                if link.link_url != "https://myblog.com/contact/":
                    raise AssertionError(
                        f"Link missing /blog/ subdirectory: {link.link_url} "
                        f"(from {link.source_url})"
                    )
        crawler.close()

    @patch.object(PageCrawler, 'fetch_page')
    def test_crawl_page_returns_empty_on_fetch_failure(self, mock_fetch):
        mock_fetch.return_value = None
        crawler = PageCrawler(base_url="https://myblog.com/blog/", delay=0)
        links = crawler.crawl_page("https://myblog.com/blog/broken/")
        assert links == []
        crawler.close()


class TestURLResolutionPipeline:
    """Test the URL resolution pipeline with various subdirectory scenarios."""

    def test_resolve_chain_blog_relative(self):
        page = "https://example.com/blog/2024/01/post/"
        hrefs = [
            ("../02/other-post/", "https://example.com/blog/2024/01/02/other-post/"),
            ("/blog/tags/python/", "https://example.com/blog/tags/python/"),
            ("comment/#reply", "https://example.com/blog/2024/01/post/comment/"),
            ("https://cdn.example.com/image.png", "https://cdn.example.com/image.png"),
        ]
        for href, expected in hrefs:
            result = resolve_relative_url(page, href)
            assert result == expected, (
                f"resolve_relative_url({page!r}, {href!r}) = {result!r}, "
                f"expected {expected!r}"
            )

    def test_normalize_preserves_blog_path(self):
        urls = [
            "https://Example.com/blog/My-Post/",
            "HTTPS://EXAMPLE.COM/blog/My-Post/",
            "https://example.com:443/blog/My-Post/",
        ]
        for url in urls:
            normalized = normalize_url(url)
            assert "/blog/" in normalized, f"normalize_url lost /blog/: {url} -> {normalized}"

    def test_full_pipeline_resolve_then_normalize(self):
        base = "https://example.com/blog/category/tech/"
        href = "../../2024/01/post/"
        resolved = resolve_relative_url(base, href)
        normalized = normalize_url(resolved)
        assert "/blog/" in normalized
        assert "2024/01/post" in normalized
