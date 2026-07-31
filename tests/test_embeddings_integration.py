"""Integration tests for the --embeddings flow in the CLI.

Patches at the method level (SitemapParser.fetch_sitemap,
PageCrawler.fetch_page, LinkChecker.check_link) so the full
semantic-duplicate pipeline can be exercised end-to-end without a
running Ollama instance or real HTTP.
"""

from unittest.mock import patch, MagicMock

import pytest

from link_checker import cli
from link_checker.checker import LinkStatus


SITE_HTML_A = """
<!DOCTYPE html><html><head><title>A</title></head>
<body><nav><a href="/">Home</a></nav>
<main><article><p>How to train your dragon step by step.</p></article></main>
<footer>Copyright</footer></body></html>
"""

SITE_HTML_B = """
<!DOCTYPE html><html><head><title>B</title></head>
<body><nav><a href="/">Home</a></nav>
<main><article><p>How to train your dragon, a step by step guide.</p></article></main>
<footer>Copyright</footer></body></html>
"""

SITE_HTML_C = """
<!DOCTYPE html><html><head><title>C</title></head>
<body><nav><a href="/">Home</a></nav>
<main><article><p>Quantum chromodynamics fundamentals overview.</p></article></main>
<footer>Copyright</footer></body></html>
"""

SITEMAP_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/a/</loc></url>
  <url><loc>https://example.com/b/</loc></url>
  <url><loc>https://example.com/c/</loc></url>
</urlset>
"""

PAGE_HTML = {
    "https://example.com/a/": SITE_HTML_A,
    "https://example.com/b/": SITE_HTML_B,
    "https://example.com/c/": SITE_HTML_C,
}

# Vectors: a and b identical (similarity 1.0), c orthogonal (outlier).
VECTORS = [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]


def _ok_link_status(url):
    return LinkStatus(url=url, status_code=200)


def _mock_embed_post(*args, **kwargs):
    """Stand in for requests.Session.post in embeddings.OllamaProvider."""
    json_body = kwargs.get("json") or {}
    inputs = json_body.get("input", [])
    # Return the precomputed vectors in the same order as PAGE_HTML keys.
    ordered_urls = list(PAGE_HTML.keys())
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    # Map each input text to a vector deterministically by order.
    resp.json.return_value = {
        "embeddings": [VECTORS[i] for i in range(len(inputs))]
    }
    return resp


@pytest.fixture
def tmp_report(tmp_path):
    return str(tmp_path / "report.csv")


class TestEmbeddingsCLIIntegration:

    def test_embeddings_flags_similar_pair_and_outlier(self, tmp_report):
        def fake_fetch_sitemap(self, url):
            return SITEMAP_XML

        def fake_fetch_page(self, url):
            return PAGE_HTML.get(url, "")

        def fake_check_link(self, url):
            return _ok_link_status(url)

        with patch(
            "link_checker.sitemap.SitemapParser.fetch_sitemap",
            new=fake_fetch_sitemap,
        ), patch(
            "link_checker.crawler.PageCrawler.fetch_page",
            new=fake_fetch_page,
        ), patch(
            "link_checker.checker.LinkChecker.check_link",
            new=fake_check_link,
        ), patch(
            "link_checker.embeddings.requests.Session.post",
            side_effect=_mock_embed_post,
        ):
            exit_code = cli.main([
                "https://example.com/sitemap.xml",
                "--crawl-engine", "python",
                "--embeddings",
                "--similarity-threshold", "0.95",
                "--outlier-threshold", "1.0",
                "--no-orphan-check",
                "--skip-ok",
                "--embeddings-cache", "none",
                "-o", tmp_report,
                "--no-fp-log",
            ])

        assert exit_code == cli.EXIT_SEMANTIC_ISSUES

        import pandas as pd
        df = pd.read_csv(tmp_report)
        semantic_rows = df[df["issue_type"] == "semantic_duplicate"]
        off_topic_rows = df[df["issue_type"] == "off_topic"]
        # a and b are identical -> at least one semantic_duplicate row
        assert len(semantic_rows) >= 1
        # c is orthogonal -> should be flagged as off_topic
        assert len(off_topic_rows) >= 1

    def test_embeddings_disabled_by_default(self, tmp_report):
        def fake_fetch_sitemap(self, url):
            return SITEMAP_XML

        def fake_fetch_page(self, url):
            return PAGE_HTML.get(url, "")

        def fake_check_link(self, url):
            return _ok_link_status(url)

        with patch(
            "link_checker.sitemap.SitemapParser.fetch_sitemap",
            new=fake_fetch_sitemap,
        ), patch(
            "link_checker.crawler.PageCrawler.fetch_page",
            new=fake_fetch_page,
        ), patch(
            "link_checker.checker.LinkChecker.check_link",
            new=fake_check_link,
        ):
            exit_code = cli.main([
                "https://example.com/sitemap.xml",
                "--crawl-engine", "python",
                "--no-orphan-check",
                "--skip-ok",
                "-o", tmp_report,
                "--no-fp-log",
            ])

        assert exit_code == cli.EXIT_SUCCESS
        import pandas as pd
        try:
            df = pd.read_csv(tmp_report)
        except pd.errors.EmptyDataError:
            df = pd.DataFrame()
        assert "semantic_duplicate" not in df.get("issue_type", pd.Series()).values
        assert "off_topic" not in df.get("issue_type", pd.Series()).values

    def test_embeddings_provider_unreachable_degrades_gracefully(self, tmp_report):
        import requests

        def fake_fetch_sitemap(self, url):
            return SITEMAP_XML

        def fake_fetch_page(self, url):
            return PAGE_HTML.get(url, "")

        def fake_check_link(self, url):
            return _ok_link_status(url)

        def fake_embed_post(*args, **kwargs):
            raise requests.ConnectionError("Ollama not running")

        with patch(
            "link_checker.sitemap.SitemapParser.fetch_sitemap",
            new=fake_fetch_sitemap,
        ), patch(
            "link_checker.crawler.PageCrawler.fetch_page",
            new=fake_fetch_page,
        ), patch(
            "link_checker.checker.LinkChecker.check_link",
            new=fake_check_link,
        ), patch(
            "link_checker.embeddings.requests.Session.post",
            side_effect=fake_embed_post,
        ):
            exit_code = cli.main([
                "https://example.com/sitemap.xml",
                "--crawl-engine", "python",
                "--embeddings",
                "--no-orphan-check",
                "--skip-ok",
                "--embeddings-cache", "none",
                "-o", tmp_report,
                "--no-fp-log",
            ])

        # No broken links and embeddings failed -> exit 0, no semantic rows.
        assert exit_code == cli.EXIT_SUCCESS
        import pandas as pd
        try:
            df = pd.read_csv(tmp_report)
        except pd.errors.EmptyDataError:
            df = pd.DataFrame()
        assert "semantic_duplicate" not in df.get("issue_type", pd.Series()).values
        assert "off_topic" not in df.get("issue_type", pd.Series()).values

    def test_embeddings_cache_skips_provider_on_second_run(self, tmp_path):
        """Second run with a cache should not call the embedding provider
        for pages whose text hasn't changed."""
        tmp_report = str(tmp_path / "report.csv")
        cache_path = str(tmp_path / "cache.embeddings.json")

        embed_call_count = {"n": 0}

        def fake_fetch_sitemap(self, url):
            return SITEMAP_XML

        def fake_fetch_page(self, url):
            return PAGE_HTML.get(url, "")

        def fake_check_link(self, url):
            return _ok_link_status(url)

        def fake_embed_post(*args, **kwargs):
            embed_call_count["n"] += 1
            json_body = kwargs.get("json") or {}
            inputs = json_body.get("input", [])
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status.return_value = None
            resp.json.return_value = {"embeddings": [VECTORS[i] for i in range(len(inputs))]}
            return resp

        common_patches = [
            patch("link_checker.sitemap.SitemapParser.fetch_sitemap", new=fake_fetch_sitemap),
            patch("link_checker.crawler.PageCrawler.fetch_page", new=fake_fetch_page),
            patch("link_checker.checker.LinkChecker.check_link", new=fake_check_link),
            patch("link_checker.embeddings.requests.Session.post", side_effect=fake_embed_post),
        ]

        # First run: all 3 pages are cache misses -> provider called.
        for p in common_patches:
            p.start()
        try:
            cli.main([
                "https://example.com/sitemap.xml",
                "--crawl-engine", "python",
                "--embeddings",
                "--no-orphan-check",
                "--skip-ok",
                "--embeddings-cache", cache_path,
                "-o", tmp_report,
                "--no-fp-log",
            ])
        finally:
            for p in common_patches:
                p.stop()

        first_run_calls = embed_call_count["n"]
        assert first_run_calls >= 1, "first run should call the provider"

        # Second run: same pages -> cache hits -> provider not called.
        embed_call_count["n"] = 0
        for p in common_patches:
            p.start()
        try:
            cli.main([
                "https://example.com/sitemap.xml",
                "--crawl-engine", "python",
                "--embeddings",
                "--no-orphan-check",
                "--skip-ok",
                "--embeddings-cache", cache_path,
                "-o", tmp_report,
                "--no-fp-log",
            ])
        finally:
            for p in common_patches:
                p.stop()

        assert embed_call_count["n"] == 0, (
            f"second run should hit cache and not call provider, "
            f"but got {embed_call_count['n']} calls"
        )

    def test_embeddings_history_diffs_new_vs_persistent(self, tmp_path):
        """First run marks pairs as 'new'; second run marks the same pairs
        as 'persistent' and new pairs as 'new'."""
        tmp_report = str(tmp_path / "report.csv")
        cache_path = str(tmp_path / "cache.embeddings.json")
        history_path = str(tmp_path / "history.embeddings.json")

        # We'll vary the vectors between runs to simulate a new pair appearing.
        # Run 1: a/b identical, c orthogonal (1 pair: a-b).
        # Run 2: a/b identical, b/c now identical too (2 pairs: a-b persistent, b-c new).
        vectors_state = {"run": 0}
        # Run 1 vectors
        VECTORS_RUN1 = [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
        # Run 2 vectors: c moves to match a/b
        VECTORS_RUN2 = [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]

        def fake_fetch_sitemap(self, url):
            return SITEMAP_XML

        def fake_fetch_page(self, url):
            return PAGE_HTML.get(url, "")

        def fake_check_link(self, url):
            return _ok_link_status(url)

        def fake_embed_post(*args, **kwargs):
            json_body = kwargs.get("json") or {}
            inputs = json_body.get("input", [])
            vecs = VECTORS_RUN1 if vectors_state["run"] == 0 else VECTORS_RUN2
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status.return_value = None
            resp.json.return_value = {"embeddings": [vecs[i] for i in range(len(inputs))]}
            return resp

        common_patches = [
            patch("link_checker.sitemap.SitemapParser.fetch_sitemap", new=fake_fetch_sitemap),
            patch("link_checker.crawler.PageCrawler.fetch_page", new=fake_fetch_page),
            patch("link_checker.checker.LinkChecker.check_link", new=fake_check_link),
            patch("link_checker.embeddings.requests.Session.post", side_effect=fake_embed_post),
        ]

        import pandas as pd

        # --- Run 1: one pair (a-b), should be "new" ---
        for p in common_patches:
            p.start()
        try:
            cli.main([
                "https://example.com/sitemap.xml",
                "--crawl-engine", "python",
                "--embeddings",
                "--no-orphan-check",
                "--skip-ok",
                "--embeddings-cache", cache_path,
                "--embeddings-history", history_path,
                "--similarity-threshold", "0.95",
                "--outlier-threshold", "2.0",
                "-o", tmp_report,
                "--no-fp-log",
            ])
        finally:
            for p in common_patches:
                p.stop()

        df1 = pd.read_csv(tmp_report)
        sem1 = df1[df1["issue_type"] == "semantic_duplicate"]
        assert len(sem1) >= 1
        # First run: all pairs should be "new"
        statuses1 = set(sem1["pair_status"].dropna().unique())
        assert "new" in statuses1
        assert "persistent" not in statuses1

        # --- Run 2: two pairs (a-b persistent, a-c and b-c new) ---
        # Clear cache so vectors are re-embedded with the new set.
        import os
        if os.path.exists(cache_path):
            os.remove(cache_path)
        vectors_state["run"] = 1

        for p in common_patches:
            p.start()
        try:
            cli.main([
                "https://example.com/sitemap.xml",
                "--crawl-engine", "python",
                "--embeddings",
                "--no-orphan-check",
                "--skip-ok",
                "--embeddings-cache", cache_path,
                "--embeddings-history", history_path,
                "--similarity-threshold", "0.95",
                "--outlier-threshold", "2.0",
                "-o", tmp_report,
                "--no-fp-log",
            ])
        finally:
            for p in common_patches:
                p.stop()

        df2 = pd.read_csv(tmp_report)
        sem2 = df2[df2["issue_type"] == "semantic_duplicate"]
        # With all three identical, there are 3 pairs: a-b, a-c, b-c
        # a-b was in run 1 -> persistent; a-c and b-c -> new
        statuses2 = sem2["pair_status"].value_counts().to_dict()
        assert statuses2.get("persistent", 0) >= 1, "at least one persistent pair expected"
        assert statuses2.get("new", 0) >= 1, "at least one new pair expected"
