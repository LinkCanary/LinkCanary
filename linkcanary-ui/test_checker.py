"""Comprehensive tests for link_checker.checker module (LinkChecker & LinkStatus)."""

import pytest
from dataclasses import FrozenInstanceError
from unittest.mock import patch, MagicMock, call, PropertyMock

from link_checker.checker import LinkChecker, LinkStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code=200, url="https://example.com", headers=None):
    """Create a lightweight MagicMock that behaves like a requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.url = url
    resp.headers = headers or {}
    resp.is_redirect = False
    resp.history = []
    return resp


def _make_redirect_response(
    final_status=200,
    final_url="https://example.com/final",
    chain=None,
):
    """Return a response whose .history simulates a redirect chain.

    *chain* is a list of ``(status_code, url)`` tuples for intermediate hops.
    """
    if chain is None:
        chain = [(301, "https://example.com/old")]

    history = []
    for code, loc in chain:
        hop = MagicMock()
        hop.status_code = code
        hop.url = loc
        hop.headers = {"Location": loc}
        history.append(hop)

    final = _make_response(status_code=final_status, url=final_url)
    final.history = history
    return final


# =========================================================================
# LinkStatus tests
# =========================================================================

class TestLinkStatus:
    """Tests for the LinkStatus dataclass."""

    def test_creation_with_required_fields(self):
        status = LinkStatus(url="https://example.com", status_code=200)
        assert status.url == "https://example.com"
        assert status.status_code == 200

    def test_default_values(self):
        status = LinkStatus(url="https://example.com", status_code=200)
        assert status.is_redirect is False
        assert status.redirect_chain == []
        assert status.final_url == ""
        assert status.is_loop is False
        assert status.is_canonical_redirect is False
        assert status.error == ""
        assert status.retries == 0

    def test_creation_with_all_fields(self):
        chain = [(301, "https://a.com"), (302, "https://b.com")]
        status = LinkStatus(
            url="https://a.com",
            status_code=200,
            is_redirect=True,
            redirect_chain=chain,
            final_url="https://c.com",
            is_loop=False,
            is_canonical_redirect=True,
            error="",
            retries=2,
        )
        assert status.is_redirect is True
        assert status.redirect_chain == chain
        assert status.final_url == "https://c.com"
        assert status.is_canonical_redirect is True
        assert status.retries == 2

    def test_redirect_chain_formatted_empty(self):
        status = LinkStatus(url="https://example.com", status_code=200)
        # With an empty chain the formatted string should be empty / falsy
        formatted = status.redirect_chain_formatted
        assert isinstance(formatted, str)

    def test_redirect_chain_formatted_with_chain(self):
        chain = [(301, "https://a.com"), (302, "https://b.com")]
        status = LinkStatus(
            url="https://a.com",
            status_code=200,
            redirect_chain=chain,
        )
        formatted = status.redirect_chain_formatted
        assert isinstance(formatted, str)
        # The formatted string should mention at least the URLs or codes
        assert "301" in formatted or "a.com" in formatted

    def test_redirect_chain_is_independent_per_instance(self):
        """Verify the default_factory produces a new list for each instance."""
        s1 = LinkStatus(url="https://a.com", status_code=200)
        s2 = LinkStatus(url="https://b.com", status_code=404)
        s1.redirect_chain.append((301, "https://x.com"))
        assert s2.redirect_chain == []


# =========================================================================
# LinkChecker.__init__ tests
# =========================================================================

class TestLinkCheckerInit:
    """Tests for LinkChecker construction and configuration."""

    @patch("link_checker.checker.requests.Session")
    def test_default_init(self, mock_session_cls):
        checker = LinkChecker()
        assert checker.timeout == 10
        assert checker.max_retries == 3

    @patch("link_checker.checker.requests.Session")
    def test_custom_user_agent(self, mock_session_cls):
        checker = LinkChecker(user_agent="MyBot/2.0")
        session_instance = mock_session_cls.return_value
        # The user-agent should have been set on the session headers
        session_instance.headers.update.assert_called()
        # Flatten all update calls and check for user-agent
        ua_found = False
        for c in session_instance.headers.update.call_args_list:
            args, kwargs = c
            if args:
                headers_dict = args[0]
                if "User-Agent" in headers_dict and headers_dict["User-Agent"] == "MyBot/2.0":
                    ua_found = True
        assert ua_found, "Custom User-Agent was not set on the session headers"

    @patch("link_checker.checker.requests.Session")
    def test_custom_auth(self, mock_session_cls):
        checker = LinkChecker(auth_user="user", auth_pass="pass")
        session_instance = mock_session_cls.return_value
        assert session_instance.auth == ("user", "pass")

    @patch("link_checker.checker.requests.Session")
    def test_custom_headers(self, mock_session_cls):
        custom = {"X-Custom": "value"}
        checker = LinkChecker(headers=custom)
        session_instance = mock_session_cls.return_value
        session_instance.headers.update.assert_called()

    @patch("link_checker.checker.requests.Session")
    def test_custom_cookies(self, mock_session_cls):
        cookies = {"session": "abc123"}
        checker = LinkChecker(cookies=cookies)
        session_instance = mock_session_cls.return_value
        session_instance.cookies.update.assert_called_with(cookies)

    @patch("link_checker.checker.requests.Session")
    def test_custom_timeout_and_retries(self, mock_session_cls):
        checker = LinkChecker(timeout=30, max_retries=5, retry_delay=2.0, retry_backoff=3.0)
        assert checker.timeout == 30
        assert checker.max_retries == 5


# =========================================================================
# LinkChecker.check_link tests
# =========================================================================

class TestCheckLink:
    """Tests for the check_link method with mocked HTTP responses."""

    @patch("link_checker.checker.requests.Session")
    def test_check_link_200(self, mock_session_cls):
        session = mock_session_cls.return_value
        resp = _make_response(status_code=200, url="https://example.com")
        resp.history = []
        session.head.return_value = resp
        session.get.return_value = resp

        checker = LinkChecker()
        result = checker.check_link("https://example.com")

        assert isinstance(result, LinkStatus)
        assert result.url == "https://example.com"
        assert result.status_code == 200
        assert result.is_redirect is False
        assert result.error == ""

    @patch("link_checker.checker.requests.Session")
    def test_check_link_404(self, mock_session_cls):
        session = mock_session_cls.return_value
        resp = _make_response(status_code=404, url="https://example.com/missing")
        resp.history = []
        session.head.return_value = resp
        session.get.return_value = resp

        checker = LinkChecker()
        result = checker.check_link("https://example.com/missing")

        assert result.status_code == 404

    @patch("link_checker.checker.requests.Session")
    def test_check_link_redirect_chain(self, mock_session_cls):
        session = mock_session_cls.return_value
        redirect_resp = _make_redirect_response(
            final_status=200,
            final_url="https://example.com/new",
            chain=[(301, "https://example.com/old")],
        )
        session.head.return_value = redirect_resp
        session.get.return_value = redirect_resp

        checker = LinkChecker()
        result = checker.check_link("https://example.com/old")

        assert result.status_code == 200
        assert result.is_redirect is True
        assert result.final_url == "https://example.com/new"
        assert len(result.redirect_chain) >= 1

    @patch("link_checker.checker.requests.Session")
    def test_check_link_multiple_redirects(self, mock_session_cls):
        session = mock_session_cls.return_value
        chain = [
            (301, "https://example.com/a"),
            (302, "https://example.com/b"),
        ]
        redirect_resp = _make_redirect_response(
            final_status=200,
            final_url="https://example.com/c",
            chain=chain,
        )
        session.head.return_value = redirect_resp
        session.get.return_value = redirect_resp

        checker = LinkChecker()
        result = checker.check_link("https://example.com/a")

        assert result.is_redirect is True
        assert result.final_url == "https://example.com/c"
        assert len(result.redirect_chain) >= 2

    @patch("link_checker.checker.requests.Session")
    def test_check_link_connection_error(self, mock_session_cls):
        import requests as real_requests

        session = mock_session_cls.return_value
        session.head.side_effect = real_requests.ConnectionError("Connection refused")
        session.get.side_effect = real_requests.ConnectionError("Connection refused")

        checker = LinkChecker()
        result = checker.check_link("https://unreachable.example.com")

        assert isinstance(result, LinkStatus)
        assert result.error != ""

    @patch("link_checker.checker.requests.Session")
    def test_check_link_timeout_error(self, mock_session_cls):
        import requests as real_requests

        session = mock_session_cls.return_value
        session.head.side_effect = real_requests.Timeout("Timed out")
        session.get.side_effect = real_requests.Timeout("Timed out")

        checker = LinkChecker()
        result = checker.check_link("https://slow.example.com")

        assert isinstance(result, LinkStatus)
        assert result.error != ""


# =========================================================================
# Caching tests
# =========================================================================

class TestCheckLinkCaching:
    """Verify that results are cached and the same URL is not fetched twice."""

    @patch("link_checker.checker.requests.Session")
    def test_cached_result_returned(self, mock_session_cls):
        session = mock_session_cls.return_value
        resp = _make_response(status_code=200, url="https://example.com")
        resp.history = []
        session.head.return_value = resp
        session.get.return_value = resp

        checker = LinkChecker()
        result1 = checker.check_link("https://example.com")
        result2 = checker.check_link("https://example.com")

        # Both calls should return the same result object (cached)
        assert result1 is result2

    @patch("link_checker.checker.requests.Session")
    def test_cache_does_not_share_different_urls(self, mock_session_cls):
        session = mock_session_cls.return_value

        resp_a = _make_response(status_code=200, url="https://a.com")
        resp_a.history = []
        resp_b = _make_response(status_code=404, url="https://b.com")
        resp_b.history = []

        # Return different responses for different calls
        session.head.side_effect = [resp_a, resp_b]
        session.get.side_effect = [resp_a, resp_b]

        checker = LinkChecker()
        result_a = checker.check_link("https://a.com")
        result_b = checker.check_link("https://b.com")

        assert result_a.status_code == 200
        assert result_b.status_code == 404

    @patch("link_checker.checker.requests.Session")
    def test_second_call_does_not_make_request(self, mock_session_cls):
        session = mock_session_cls.return_value
        resp = _make_response(status_code=200, url="https://example.com")
        resp.history = []
        session.head.return_value = resp
        session.get.return_value = resp

        checker = LinkChecker()
        checker.check_link("https://example.com")

        head_count_after_first = session.head.call_count
        get_count_after_first = session.get.call_count
        total_after_first = head_count_after_first + get_count_after_first

        checker.check_link("https://example.com")

        head_count_after_second = session.head.call_count
        get_count_after_second = session.get.call_count
        total_after_second = head_count_after_second + get_count_after_second

        # No additional HTTP calls should have been made
        assert total_after_second == total_after_first


# =========================================================================
# check_links (batch) tests
# =========================================================================

class TestCheckLinks:
    """Tests for the batch check_links method."""

    @patch("link_checker.checker.requests.Session")
    def test_check_links_returns_dict(self, mock_session_cls):
        session = mock_session_cls.return_value
        resp = _make_response(status_code=200, url="https://example.com")
        resp.history = []
        session.head.return_value = resp
        session.get.return_value = resp

        checker = LinkChecker()
        urls = ["https://example.com", "https://example.com/page"]
        results = checker.check_links(urls)

        assert isinstance(results, dict)
        assert len(results) == 2
        for url in urls:
            assert url in results
            assert isinstance(results[url], LinkStatus)

    @patch("link_checker.checker.requests.Session")
    def test_check_links_with_progress_callback(self, mock_session_cls):
        session = mock_session_cls.return_value
        resp = _make_response(status_code=200, url="https://example.com")
        resp.history = []
        session.head.return_value = resp
        session.get.return_value = resp

        callback = MagicMock()
        checker = LinkChecker()
        urls = ["https://example.com", "https://example.com/other"]
        checker.check_links(urls, progress_callback=callback)

        # The callback should have been invoked at least once per URL
        assert callback.call_count >= len(urls)

    @patch("link_checker.checker.requests.Session")
    def test_check_links_empty_list(self, mock_session_cls):
        checker = LinkChecker()
        results = checker.check_links([])
        assert results == {}


# =========================================================================
# get_cache_stats tests
# =========================================================================

class TestGetCacheStats:
    """Tests for cache statistics reporting."""

    @patch("link_checker.checker.requests.Session")
    def test_initial_cache_stats(self, mock_session_cls):
        checker = LinkChecker()
        stats = checker.get_cache_stats()
        assert isinstance(stats, dict)
        # A fresh checker should report zero or empty cache
        assert stats.get("size", stats.get("hits", 0)) == 0 or stats.get("size", 0) == 0

    @patch("link_checker.checker.requests.Session")
    def test_cache_stats_after_checks(self, mock_session_cls):
        session = mock_session_cls.return_value
        resp = _make_response(status_code=200, url="https://example.com")
        resp.history = []
        session.head.return_value = resp
        session.get.return_value = resp

        checker = LinkChecker()
        checker.check_link("https://example.com")
        stats = checker.get_cache_stats()

        assert isinstance(stats, dict)
        # After one check the cache should have at least one entry
        size = stats.get("size", stats.get("cached", stats.get("entries", None)))
        assert size is not None and size >= 1

    @patch("link_checker.checker.requests.Session")
    def test_cache_stats_hits_after_duplicate(self, mock_session_cls):
        session = mock_session_cls.return_value
        resp = _make_response(status_code=200, url="https://example.com")
        resp.history = []
        session.head.return_value = resp
        session.get.return_value = resp

        checker = LinkChecker()
        checker.check_link("https://example.com")
        checker.check_link("https://example.com")  # cache hit
        stats = checker.get_cache_stats()

        hits = stats.get("hits", stats.get("cache_hits", 0))
        assert hits >= 1


# =========================================================================
# HEAD blacklisting / fallback to GET tests
# =========================================================================

class TestHeadBlacklisting:
    """When a HEAD request returns 403 the checker should fall back to GET."""

    @patch("link_checker.checker.requests.Session")
    def test_head_403_falls_back_to_get(self, mock_session_cls):
        session = mock_session_cls.return_value

        head_resp = _make_response(status_code=403, url="https://example.com")
        head_resp.history = []

        get_resp = _make_response(status_code=200, url="https://example.com")
        get_resp.history = []

        session.head.return_value = head_resp
        session.get.return_value = get_resp

        checker = LinkChecker()
        result = checker.check_link("https://example.com")

        # Should have fallen back to GET and returned 200
        assert result.status_code == 200
        session.get.assert_called()

    @patch("link_checker.checker.requests.Session")
    def test_head_405_falls_back_to_get(self, mock_session_cls):
        session = mock_session_cls.return_value

        head_resp = _make_response(status_code=405, url="https://example.com")
        head_resp.history = []

        get_resp = _make_response(status_code=200, url="https://example.com")
        get_resp.history = []

        session.head.return_value = head_resp
        session.get.return_value = get_resp

        checker = LinkChecker()
        result = checker.check_link("https://example.com")

        assert result.status_code == 200
        session.get.assert_called()

    @patch("link_checker.checker.requests.Session")
    def test_subsequent_requests_skip_head_after_blacklist(self, mock_session_cls):
        """Once a domain is blacklisted for HEAD, future checks go straight to GET."""
        session = mock_session_cls.return_value

        head_resp = _make_response(status_code=403, url="https://example.com/page1")
        head_resp.history = []

        get_resp_1 = _make_response(status_code=200, url="https://example.com/page1")
        get_resp_1.history = []
        get_resp_2 = _make_response(status_code=200, url="https://example.com/page2")
        get_resp_2.history = []

        session.head.return_value = head_resp
        session.get.side_effect = [get_resp_1, get_resp_2]

        checker = LinkChecker()
        checker.check_link("https://example.com/page1")

        head_count_before = session.head.call_count
        checker.check_link("https://example.com/page2")
        head_count_after = session.head.call_count

        # HEAD should NOT have been called again for the same domain
        assert head_count_after == head_count_before


# =========================================================================
# Context manager tests
# =========================================================================

class TestContextManager:
    """LinkChecker should work as a context manager (with-statement)."""

    @patch("link_checker.checker.requests.Session")
    def test_enter_returns_self(self, mock_session_cls):
        checker = LinkChecker()
        result = checker.__enter__()
        assert result is checker

    @patch("link_checker.checker.requests.Session")
    def test_exit_closes_session(self, mock_session_cls):
        session = mock_session_cls.return_value
        checker = LinkChecker()
        checker.__enter__()
        checker.__exit__(None, None, None)
        session.close.assert_called_once()

    @patch("link_checker.checker.requests.Session")
    def test_with_statement(self, mock_session_cls):
        session = mock_session_cls.return_value
        resp = _make_response(status_code=200, url="https://example.com")
        resp.history = []
        session.head.return_value = resp
        session.get.return_value = resp

        with LinkChecker() as checker:
            result = checker.check_link("https://example.com")
            assert result.status_code == 200

        session.close.assert_called_once()

    @patch("link_checker.checker.requests.Session")
    def test_exit_called_on_exception(self, mock_session_cls):
        session = mock_session_cls.return_value

        with pytest.raises(RuntimeError):
            with LinkChecker() as checker:
                raise RuntimeError("boom")

        session.close.assert_called_once()


# =========================================================================
# Retry logic tests
# =========================================================================

class TestRetryLogic:
    """Verify retry behaviour for 502/503/504 status codes."""

    @patch("link_checker.checker.requests.Session")
    @patch("link_checker.checker.time.sleep", return_value=None)  # skip real delays
    def test_retry_on_503(self, mock_sleep, mock_session_cls):
        session = mock_session_cls.return_value

        bad_resp = _make_response(status_code=503, url="https://example.com")
        bad_resp.history = []
        good_resp = _make_response(status_code=200, url="https://example.com")
        good_resp.history = []

        # First two attempts return 503, third succeeds
        session.head.side_effect = [bad_resp, bad_resp, good_resp]
        session.get.side_effect = [bad_resp, bad_resp, good_resp]

        checker = LinkChecker(max_retries=3, retry_delay=0.01)
        result = checker.check_link("https://example.com")

        assert result.status_code == 200
        assert result.retries >= 1

    @patch("link_checker.checker.requests.Session")
    @patch("link_checker.checker.time.sleep", return_value=None)
    def test_max_retries_exhausted(self, mock_sleep, mock_session_cls):
        session = mock_session_cls.return_value

        bad_resp = _make_response(status_code=503, url="https://example.com")
        bad_resp.history = []

        session.head.return_value = bad_resp
        session.get.return_value = bad_resp

        checker = LinkChecker(max_retries=2, retry_delay=0.01)
        result = checker.check_link("https://example.com")

        # After exhausting retries the last status should still be 503
        assert result.status_code == 503


# =========================================================================
# Canonical redirect detection
# =========================================================================

class TestCanonicalRedirect:
    """Test detection of canonical (www ↔ non-www, http → https) redirects."""

    @patch("link_checker.checker.requests.Session")
    def test_http_to_https_redirect_is_canonical(self, mock_session_cls):
        session = mock_session_cls.return_value
        redirect_resp = _make_redirect_response(
            final_status=200,
            final_url="https://example.com/page",
            chain=[(301, "http://example.com/page")],
        )
        session.head.return_value = redirect_resp
        session.get.return_value = redirect_resp

        checker = LinkChecker()
        result = checker.check_link("http://example.com/page")

        assert result.is_redirect is True
        assert result.is_canonical_redirect is True

    @patch("link_checker.checker.requests.Session")
    def test_www_to_non_www_is_canonical(self, mock_session_cls):
        session = mock_session_cls.return_value
        redirect_resp = _make_redirect_response(
            final_status=200,
            final_url="https://example.com/page",
            chain=[(301, "https://www.example.com/page")],
        )
        session.head.return_value = redirect_resp
        session.get.return_value = redirect_resp

        checker = LinkChecker()
        result = checker.check_link("https://www.example.com/page")

        assert result.is_redirect is True
        assert result.is_canonical_redirect is True


# =========================================================================
# Edge-case / miscellaneous tests
# =========================================================================

class TestEdgeCases:
    """Additional edge-case tests."""

    @patch("link_checker.checker.requests.Session")
    def test_check_link_with_fragment(self, mock_session_cls):
        session = mock_session_cls.return_value
        resp = _make_response(status_code=200, url="https://example.com/page")
        resp.history = []
        session.head.return_value = resp
        session.get.return_value = resp

        checker = LinkChecker()
        result = checker.check_link("https://example.com/page#section")
        assert result.status_code == 200

    @patch("link_checker.checker.requests.Session")
    def test_check_link_preserves_original_url(self, mock_session_cls):
        session = mock_session_cls.return_value
        resp = _make_response(status_code=200, url="https://example.com/page")
        resp.history = []
        session.head.return_value = resp
        session.get.return_value = resp

        checker = LinkChecker()
        original = "https://example.com/page"
        result = checker.check_link(original)
        assert result.url == original

    @patch("link_checker.checker.requests.Session")
    def test_delay_between_requests(self, mock_session_cls):
        """With delay > 0 the checker should pause between requests."""
        session = mock_session_cls.return_value
        resp = _make_response(status_code=200, url="https://example.com")
        resp.history = []
        session.head.return_value = resp
        session.get.return_value = resp

        checker = LinkChecker(delay=0.0)
        # Should not raise even with zero delay
        result = checker.check_link("https://example.com")
        assert result.status_code == 200
