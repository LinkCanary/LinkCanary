"""Tests for the Go crawl-engine subprocess wrapper and CLI integration."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from link_checker.crawl_engine import (
    CrawlEngineResult,
    find_crawl_engine,
    is_available,
    _parse_output,
    _build_args,
)
from link_checker.crawler import ExtractedLink
from link_checker.checker import LinkStatus


class TestCrawlEngineFinder(unittest.TestCase):
    """Test binary discovery logic."""

    def test_find_crawl_engine_returns_path_or_none(self):
        """find_crawl_engine returns a string or None, never raises."""
        result = find_crawl_engine()
        # Could be None if binary not built, or a path string
        self.assertTrue(result is None or isinstance(result, str))

    def test_is_available_returns_bool(self):
        """is_available returns a boolean."""
        result = is_available()
        self.assertIsInstance(result, bool)


class TestParseOutput(unittest.TestCase):
    """Test JSON output parsing into Python objects."""

    def test_parse_links(self):
        data = {
            "links": [
                {
                    "source_url": "https://example.com/page1/",
                    "link_url": "https://example.com/page2/",
                    "link_text": "Page 2",
                    "is_internal": True,
                    "element_type": "a",
                    "is_mixed_content": False,
                },
                {
                    "source_url": "https://example.com/page1/",
                    "link_url": "https://external.com/",
                    "link_text": "External",
                    "is_internal": False,
                    "element_type": "a",
                    "is_mixed_content": False,
                },
            ]
        }
        result = _parse_output(data)
        self.assertEqual(len(result.links), 2)
        self.assertIsInstance(result.links[0], ExtractedLink)
        self.assertEqual(result.links[0].link_url, "https://example.com/page2/")
        self.assertTrue(result.links[0].is_internal)
        self.assertFalse(result.links[1].is_internal)

    def test_parse_link_statuses(self):
        data = {
            "link_statuses": [
                {
                    "url": "https://example.com/page/",
                    "status_code": 200,
                    "is_redirect": False,
                    "redirect_chain": [],
                    "final_url": "https://example.com/page/",
                    "is_loop": False,
                    "is_canonical_redirect": False,
                    "error": "",
                    "retries": 0,
                    "response_time_ms": 42.5,
                },
                {
                    "url": "https://example.com/old/",
                    "status_code": 200,
                    "is_redirect": True,
                    "redirect_chain": [
                        {"status": 301, "url": "https://example.com/old/"},
                        {"status": 200, "url": "https://example.com/new/"},
                    ],
                    "final_url": "https://example.com/new/",
                    "is_loop": False,
                    "is_canonical_redirect": False,
                    "error": "",
                    "retries": 1,
                    "response_time_ms": 100.0,
                },
            ]
        }
        result = _parse_output(data)
        self.assertEqual(len(result.link_statuses), 2)
        status = result.link_statuses["https://example.com/page/"]
        self.assertIsInstance(status, LinkStatus)
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.response_time_ms, 42.5)

        redirect_status = result.link_statuses["https://example.com/old/"]
        self.assertTrue(redirect_status.is_redirect)
        self.assertEqual(len(redirect_status.redirect_chain), 2)
        self.assertEqual(redirect_status.redirect_chain[0], (301, "https://example.com/old/"))
        self.assertEqual(redirect_status.retries, 1)

    def test_parse_empty_output(self):
        result = _parse_output({})
        self.assertEqual(len(result.links), 0)
        self.assertEqual(len(result.link_statuses), 0)
        self.assertEqual(result.page_urls, [])
        self.assertEqual(result.page_html, {})

    def test_parse_page_html(self):
        data = {
            "page_html": {
                "https://example.com/page/": "<html><body>Test</body></html>",
            }
        }
        result = _parse_output(data)
        self.assertEqual(
            result.page_html["https://example.com/page/"],
            "<html><body>Test</body></html>",
        )

    def test_parse_metadata_and_stats(self):
        data = {
            "metadata": {
                "base_url": "https://example.com",
                "sitemap_mode": True,
                "page_count": 5,
                "total_links": 20,
                "unique_links": 15,
                "checked_links": 15,
            },
            "robots_stats": {"urls_skipped": 3, "ignored": False},
            "retry_stats": {"urls_with_retries": 2, "total_retries": 5},
            "baseline_urls": ["https://example.com/base/"],
        }
        result = _parse_output(data)
        self.assertTrue(result.metadata["sitemap_mode"])
        self.assertEqual(result.metadata["page_count"], 5)
        self.assertEqual(result.robots_stats["urls_skipped"], 3)
        self.assertEqual(result.retry_stats["total_retries"], 5)
        self.assertEqual(len(result.baseline_urls), 1)


class TestBuildArgs(unittest.TestCase):
    """Test argument construction for the Go binary."""

    def _make_args(self, **overrides):
        """Create a mock parsed_args namespace with defaults."""
        defaults = {
            "sitemap_url": "https://example.com/sitemap.xml",
            "url": None,
            "urls_file": None,
            "delay": 0.5,
            "timeout": 10,
            "no_retry": False,
            "max_retries": 3,
            "retry_delay": 1.0,
            "retry_backoff": 2.0,
            "auth_user": None,
            "auth_pass": None,
            "auth_pass_env": None,
            "headers": [],
            "cookies": [],
            "internal_only": False,
            "external_only": False,
            "exclude_patterns": [],
            "include_patterns": [],
            "pattern_type": "glob",
            "max_pages": None,
            "verbose": False,
            "user_agent": "LinkCanary/1.0",
            "include_subdomains": False,
            "ignore_robots": False,
            "since": None,
            "baseline_sitemap": None,
        }
        defaults.update(overrides)
        return MagicMock(**defaults)

    def test_sitemap_mode_args(self):
        args = self._make_args()
        cmd = _build_args(args, collect_html=False)
        self.assertIn("--sitemap-url", cmd)
        self.assertIn("https://example.com/sitemap.xml", cmd)
        self.assertIn("--delay", cmd)
        self.assertIn("0.5", cmd)
        self.assertIn("--timeout", cmd)
        self.assertIn("10", cmd)

    def test_url_mode_args(self):
        args = self._make_args(url="https://example.com/page/")
        cmd = _build_args(args, collect_html=False)
        self.assertIn("--url", cmd)
        self.assertIn("https://example.com/page/", cmd)
        self.assertNotIn("--sitemap-url", cmd)

    def test_no_retry_flag(self):
        args = self._make_args(no_retry=True)
        cmd = _build_args(args, collect_html=False)
        self.assertIn("--no-retry", cmd)
        self.assertNotIn("--max-retries", cmd)

    def test_collect_html_flag(self):
        args = self._make_args()
        cmd = _build_args(args, collect_html=True)
        self.assertIn("--collect-html", cmd)

    def test_auth_args(self):
        args = self._make_args(
            auth_user="admin",
            auth_pass="secret",
        )
        cmd = _build_args(args, collect_html=False)
        self.assertIn("--auth-user", cmd)
        self.assertIn("admin", cmd)
        self.assertIn("--auth-pass", cmd)
        self.assertIn("secret", cmd)

    def test_pattern_args(self):
        args = self._make_args(
            exclude_patterns=["*linkedin.com*"],
            include_patterns=["/blog/*"],
            pattern_type="glob",
        )
        cmd = _build_args(args, collect_html=False)
        self.assertIn("--exclude-pattern", cmd)
        self.assertIn("*linkedin.com*", cmd)
        self.assertIn("--include-pattern", cmd)
        self.assertIn("/blog/*", cmd)
        self.assertIn("--pattern-type", cmd)
        self.assertIn("glob", cmd)

    def test_include_subdomains_flag(self):
        args = self._make_args(include_subdomains=True)
        cmd = _build_args(args, collect_html=False)
        self.assertIn("--include-subdomains", cmd)

    def test_baseline_sitemap_arg(self):
        args = self._make_args(baseline_sitemap="https://example.com/baseline.xml")
        cmd = _build_args(args, collect_html=False)
        self.assertIn("--baseline-sitemap", cmd)
        self.assertIn("https://example.com/baseline.xml", cmd)


@unittest.skipUnless(is_available(), "Go crawl-engine binary not available")
class TestCrawlEngineIntegration(unittest.TestCase):
    """Integration tests that run the actual Go binary."""

    def test_run_crawl_engine_with_url(self):
        """Test running the Go binary against a local HTTP server."""
        import http.server
        import threading

        # Simple test server
        html = b"<html><body><a href='/other/'>Other</a></body></html>"

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(html)

            def do_HEAD(self):
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()

        try:
            from link_checker.crawl_engine import run_crawl_engine
            args = MagicMock(
                sitemap_url=None,
                url=f"http://127.0.0.1:{port}/",
                urls_file=None,
                delay=0,
                timeout=5,
                no_retry=True,
                max_retries=0,
                retry_delay=0.1,
                retry_backoff=2.0,
                auth_user=None,
                auth_pass=None,
                auth_pass_env=None,
                headers=[],
                cookies=[],
                internal_only=False,
                external_only=False,
                exclude_patterns=[],
                include_patterns=[],
                pattern_type="glob",
                max_pages=None,
                verbose=False,
                user_agent="LinkCanary-test",
                include_subdomains=False,
                ignore_robots=True,
                since=None,
                baseline_sitemap=None,
            )
            result = run_crawl_engine(args, collect_html=False)
            self.assertIsInstance(result, CrawlEngineResult)
            self.assertGreater(len(result.links), 0)
            server.shutdown()
        finally:
            server.shutdown()
            thread.join(timeout=2)


class TestCLIFlagParsing(unittest.TestCase):
    """Test that the CLI correctly parses --crawl-engine flag."""

    def test_crawl_engine_default_auto(self):
        from link_checker.cli import create_parser
        parser = create_parser()
        args = parser.parse_args(["https://example.com/sitemap.xml"])
        self.assertEqual(args.crawl_engine, "auto")

    def test_crawl_engine_go(self):
        from link_checker.cli import create_parser
        parser = create_parser()
        args = parser.parse_args(["--crawl-engine", "go", "https://example.com/sitemap.xml"])
        self.assertEqual(args.crawl_engine, "go")

    def test_crawl_engine_python(self):
        from link_checker.cli import create_parser
        parser = create_parser()
        args = parser.parse_args(["--crawl-engine", "python", "https://example.com/sitemap.xml"])
        self.assertEqual(args.crawl_engine, "python")

    def test_crawl_engine_env_var(self):
        from link_checker.cli import create_parser
        old_val = os.environ.get("CRAWL_ENGINE")
        os.environ["CRAWL_ENGINE"] = "python"
        try:
            parser = create_parser()
            args = parser.parse_args(["https://example.com/sitemap.xml"])
            self.assertEqual(args.crawl_engine, "python")
        finally:
            if old_val is None:
                del os.environ["CRAWL_ENGINE"]
            else:
                os.environ["CRAWL_ENGINE"] = old_val


if __name__ == "__main__":
    unittest.main()
