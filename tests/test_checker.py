"""Tests for the LinkChecker and LinkStatus classes."""

import pytest
from unittest.mock import patch, MagicMock

from link_checker.checker import LinkChecker, LinkStatus


def _make_response(status_code=200, headers=None, url="https://example.com"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.url = url
    return resp


class TestLinkStatus:

    def test_basic_creation(self):
        status = LinkStatus(url="https://example.com", status_code=200)
        assert status.url == "https://example.com"
        assert status.status_code == 200

    def test_default_values(self):
        status = LinkStatus(url="https://example.com", status_code=200)
        assert status.is_redirect is False
        assert status.redirect_chain == []
        assert status.final_url == ""
        assert status.is_loop is False
        assert status.error == ""
        assert status.retries == 0

    def test_redirect_chain_formatted_empty(self):
        status = LinkStatus(url="https://example.com", status_code=200)
        assert status.redirect_chain_formatted == ""

    def test_redirect_chain_formatted_with_chain(self):
        status = LinkStatus(
            url="https://example.com",
            status_code=200,
            redirect_chain=[(301, "https://example.com"), (200, "https://www.example.com")],
        )
        formatted = status.redirect_chain_formatted
        assert "301" in formatted
        assert "200" in formatted

    def test_independent_redirect_chains(self):
        s1 = LinkStatus(url="a", status_code=200)
        s2 = LinkStatus(url="b", status_code=200)
        s1.redirect_chain.append((301, "a"))
        assert len(s2.redirect_chain) == 0


class TestLinkCheckerInit:

    def test_default_init(self):
        checker = LinkChecker()
        assert checker.user_agent == "LinkCanary/1.0"
        assert checker.timeout == 10
        checker.close()

    def test_custom_user_agent(self):
        checker = LinkChecker(user_agent="TestBot/1.0")
        assert checker.user_agent == "TestBot/1.0"
        checker.close()

    def test_auth_configured(self):
        checker = LinkChecker(auth_user="user", auth_pass="pass")
        assert checker.session.auth == ("user", "pass")
        checker.close()

    def test_custom_headers(self):
        checker = LinkChecker(headers={"X-Custom": "value"})
        assert "X-Custom" in checker.session.headers
        checker.close()

    def test_cookies_configured(self):
        checker = LinkChecker(cookies={"session": "abc123"})
        assert "session" in checker.session.cookies
        checker.close()


class TestCheckLink:

    @patch("link_checker.checker.requests.Session")
    def test_200_response(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.head.return_value = _make_response(200)
        mock_session.headers = {}
        mock_session.cookies = MagicMock()
        mock_session_cls.return_value = mock_session

        checker = LinkChecker(delay=0)
        result = checker.check_link("https://example.com")
        assert result.status_code == 200
        assert result.is_redirect is False
        checker.close()

    @patch("link_checker.checker.requests.Session")
    def test_404_response(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.head.return_value = _make_response(404)
        mock_session.headers = {}
        mock_session.cookies = MagicMock()
        mock_session_cls.return_value = mock_session

        checker = LinkChecker(delay=0)
        result = checker.check_link("https://example.com/missing")
        assert result.status_code == 404
        checker.close()


class TestCheckLinkCaching:

    @patch("link_checker.checker.requests.Session")
    def test_cached_result(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.head.return_value = _make_response(200)
        mock_session.headers = {}
        mock_session.cookies = MagicMock()
        mock_session_cls.return_value = mock_session

        checker = LinkChecker(delay=0)
        result1 = checker.check_link("https://example.com")
        result2 = checker.check_link("https://example.com")
        assert result1 is result2
        checker.close()


class TestCheckLinks:

    @patch("link_checker.checker.requests.Session")
    def test_check_multiple(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.head.return_value = _make_response(200)
        mock_session.headers = {}
        mock_session.cookies = MagicMock()
        mock_session_cls.return_value = mock_session

        checker = LinkChecker(delay=0)
        results = checker.check_links([
            "https://example.com/a",
            "https://example.com/b",
        ])
        assert len(results) == 2
        checker.close()

    @patch("link_checker.checker.requests.Session")
    def test_empty_list(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.headers = {}
        mock_session.cookies = MagicMock()
        mock_session_cls.return_value = mock_session

        checker = LinkChecker(delay=0)
        results = checker.check_links([])
        assert results == {}
        checker.close()


class TestGetCacheStats:

    def test_initial_stats(self):
        checker = LinkChecker()
        stats = checker.get_cache_stats()
        assert stats["cached_urls"] == 0
        assert stats["total_retries"] == 0
        checker.close()


class TestContextManager:

    def test_enter_returns_self(self):
        checker = LinkChecker()
        assert checker.__enter__() is checker
        checker.close()

    def test_with_statement(self):
        with LinkChecker() as checker:
            assert isinstance(checker, LinkChecker)
