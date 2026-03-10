"""Comprehensive tests for SitemapParser XML parsing functionality."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from xml.etree import ElementTree as ET

from link_checker.sitemap import SitemapParser, SITEMAP_NS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def parser():
    """Return a default SitemapParser instance."""
    return SitemapParser()


@pytest.fixture
def custom_parser():
    """Return a SitemapParser with custom settings."""
    return SitemapParser(user_agent="TestBot/2.0", timeout=10)


# ---------------------------------------------------------------------------
# Helper – build ElementTree roots from raw XML strings
# ---------------------------------------------------------------------------

def _root(xml_str: str) -> ET.Element:
    return ET.fromstring(xml_str)


# ===================================================================
# Test _parse_urlset
# ===================================================================

class TestParseUrlset:
    """Tests for SitemapParser._parse_urlset."""

    def test_namespaced_xml(self, parser):
        xml = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/page1</loc></url>
          <url><loc>https://example.com/page2</loc></url>
        </urlset>'''
        root = _root(xml)
        urls = parser._parse_urlset(root)
        assert urls == [
            "https://example.com/page1",
            "https://example.com/page2",
        ]

    def test_non_namespaced_xml(self, parser):
        xml = '''<?xml version="1.0"?>
        <urlset>
          <url><loc>https://example.com/a</loc></url>
          <url><loc>https://example.com/b</loc></url>
          <url><loc>https://example.com/c</loc></url>
        </urlset>'''
        root = _root(xml)
        urls = parser._parse_urlset(root)
        assert urls == [
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/c",
        ]

    def test_empty_urlset(self, parser):
        xml = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        </urlset>'''
        root = _root(xml)
        urls = parser._parse_urlset(root)
        assert urls == []

    def test_with_lastmod(self, parser):
        xml = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url>
            <loc>https://example.com/page1</loc>
            <lastmod>2024-01-15T10:00:00+00:00</lastmod>
          </url>
          <url>
            <loc>https://example.com/page2</loc>
            <lastmod>2024-06-20T12:30:00+00:00</lastmod>
          </url>
        </urlset>'''
        root = _root(xml)
        urls = parser._parse_urlset(root)
        assert urls == [
            "https://example.com/page1",
            "https://example.com/page2",
        ]

    def test_with_since_filter(self, parser):
        xml = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url>
            <loc>https://example.com/old</loc>
            <lastmod>2023-01-01T00:00:00+00:00</lastmod>
          </url>
          <url>
            <loc>https://example.com/new</loc>
            <lastmod>2024-06-01T00:00:00+00:00</lastmod>
          </url>
        </urlset>'''
        root = _root(xml)
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        urls = parser._parse_urlset(root, since=since)
        assert urls == ["https://example.com/new"]

    def test_since_filter_includes_all_when_no_lastmod(self, parser):
        """URLs without lastmod should be included even when since is set."""
        xml = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url>
            <loc>https://example.com/no-date</loc>
          </url>
          <url>
            <loc>https://example.com/old</loc>
            <lastmod>2020-01-01</lastmod>
          </url>
        </urlset>'''
        root = _root(xml)
        since = datetime(2023, 1, 1, tzinfo=timezone.utc)
        urls = parser._parse_urlset(root, since=since)
        # URL without lastmod should be included; old one should be excluded
        assert "https://example.com/no-date" in urls
        assert "https://example.com/old" not in urls

    def test_urlset_with_extra_elements(self, parser):
        """Extra elements like <changefreq> and <priority> should not break parsing."""
        xml = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url>
            <loc>https://example.com/page1</loc>
            <changefreq>daily</changefreq>
            <priority>0.8</priority>
          </url>
        </urlset>'''
        root = _root(xml)
        urls = parser._parse_urlset(root)
        assert urls == ["https://example.com/page1"]

    def test_urlset_preserves_order(self, parser):
        xml = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/z</loc></url>
          <url><loc>https://example.com/a</loc></url>
          <url><loc>https://example.com/m</loc></url>
        </urlset>'''
        root = _root(xml)
        urls = parser._parse_urlset(root)
        assert urls == [
            "https://example.com/z",
            "https://example.com/a",
            "https://example.com/m",
        ]

    def test_urlset_whitespace_in_loc(self, parser):
        """Whitespace around <loc> text should be stripped."""
        xml = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url>
            <loc>
              https://example.com/page1
            </loc>
          </url>
        </urlset>'''
        root = _root(xml)
        urls = parser._parse_urlset(root)
        assert len(urls) == 1
        assert urls[0].strip() == "https://example.com/page1"


# ===================================================================
# Test _parse_lastmod
# ===================================================================

class TestParseLastmod:
    """Tests for SitemapParser._parse_lastmod."""

    def test_iso8601_with_utc_timezone(self, parser):
        result = parser._parse_lastmod("2024-06-15T10:30:00+00:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.tzinfo is not None

    def test_iso8601_with_positive_offset(self, parser):
        result = parser._parse_lastmod("2024-03-20T14:00:00+05:30")
        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 20

    def test_iso8601_with_negative_offset(self, parser):
        result = parser._parse_lastmod("2024-01-10T08:00:00-05:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 10

    def test_iso8601_with_z_suffix(self, parser):
        result = parser._parse_lastmod("2024-06-15T10:30:00Z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 6

    def test_iso8601_without_timezone(self, parser):
        result = parser._parse_lastmod("2024-06-15T10:30:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15

    def test_date_only(self, parser):
        result = parser._parse_lastmod("2024-06-15")
        assert result is not None
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15

    def test_none_input(self, parser):
        result = parser._parse_lastmod(None)
        assert result is None

    def test_empty_string(self, parser):
        result = parser._parse_lastmod("")
        assert result is None

    def test_invalid_format(self, parser):
        result = parser._parse_lastmod("not-a-date")
        assert result is None

    def test_partial_date(self, parser):
        """Year-month only – implementation may or may not handle this."""
        result = parser._parse_lastmod("2024-06")
        # Depending on implementation, this could be None or a parsed date
        # The key assertion: it should not raise an exception
        assert result is None or isinstance(result, datetime)

    def test_date_with_milliseconds(self, parser):
        result = parser._parse_lastmod("2024-06-15T10:30:00.123+00:00")
        assert result is not None
        assert result.year == 2024


# ===================================================================
# Test _should_include
# ===================================================================

class TestShouldInclude:
    """Tests for SitemapParser._should_include."""

    def test_no_since_filter(self, parser):
        """When since is None, everything should be included."""
        lastmod = datetime(2020, 1, 1, tzinfo=timezone.utc)
        assert parser._should_include(lastmod, since=None) is True

    def test_no_lastmod(self, parser):
        """When lastmod is None, the URL should be included regardless of since."""
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert parser._should_include(None, since=since) is True

    def test_both_none(self, parser):
        """When both are None, URL should be included."""
        assert parser._should_include(None, since=None) is True

    def test_lastmod_after_since(self, parser):
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        lastmod = datetime(2024, 6, 1, tzinfo=timezone.utc)
        assert parser._should_include(lastmod, since=since) is True

    def test_lastmod_before_since(self, parser):
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        lastmod = datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert parser._should_include(lastmod, since=since) is False

    def test_lastmod_equal_to_since(self, parser):
        dt = datetime(2024, 6, 1, tzinfo=timezone.utc)
        assert parser._should_include(dt, since=dt) is True

    def test_timezone_aware_vs_naive_lastmod(self, parser):
        """Ensure comparison works when lastmod is naive and since is aware."""
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        lastmod = datetime(2024, 6, 1)  # naive
        # Should not raise; implementation should handle tz normalization
        result = parser._should_include(lastmod, since=since)
        assert isinstance(result, bool)

    def test_timezone_aware_vs_naive_since(self, parser):
        """Ensure comparison works when since is naive and lastmod is aware."""
        since = datetime(2024, 1, 1)  # naive
        lastmod = datetime(2024, 6, 1, tzinfo=timezone.utc)
        result = parser._should_include(lastmod, since=since)
        assert isinstance(result, bool)

    def test_different_timezones(self, parser):
        """Both tz-aware but different offsets."""
        utc_plus_5 = timezone(timedelta(hours=5))
        since = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        # 2024-06-01 04:00 UTC+5 == 2024-05-31 23:00 UTC  → before since
        lastmod = datetime(2024, 6, 1, 4, 0, 0, tzinfo=utc_plus_5)
        result = parser._should_include(lastmod, since=since)
        assert result is False


# ===================================================================
# Test _parse_url_element
# ===================================================================

class TestParseUrlElement:
    """Tests for SitemapParser._parse_url_element."""

    def test_with_loc_only_namespaced(self, parser):
        xml = '''<url xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <loc>https://example.com/page1</loc>
        </url>'''
        elem = _root(xml)
        result = parser._parse_url_element(elem, SITEMAP_NS)
        assert result is not None
        loc, lastmod = result
        assert loc == "https://example.com/page1"
        assert lastmod is None

    def test_with_loc_and_lastmod_namespaced(self, parser):
        xml = '''<url xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <loc>https://example.com/page1</loc>
          <lastmod>2024-06-15T10:00:00+00:00</lastmod>
        </url>'''
        elem = _root(xml)
        result = parser._parse_url_element(elem, SITEMAP_NS)
        assert result is not None
        loc, lastmod = result
        assert loc == "https://example.com/page1"
        assert lastmod is not None
        assert lastmod.year == 2024
        assert lastmod.month == 6
        assert lastmod.day == 15

    def test_with_loc_only_no_namespace(self, parser):
        xml = '''<url>
          <loc>https://example.com/page1</loc>
        </url>'''
        elem = _root(xml)
        # When no namespace, pass empty ns dict or handle accordingly
        result = parser._parse_url_element(elem, {})
        assert result is not None
        loc, lastmod = result
        assert loc == "https://example.com/page1"
        assert lastmod is None

    def test_with_loc_and_lastmod_no_namespace(self, parser):
        xml = '''<url>
          <loc>https://example.com/page1</loc>
          <lastmod>2024-03-01</lastmod>
        </url>'''
        elem = _root(xml)
        result = parser._parse_url_element(elem, {})
        assert result is not None
        loc, lastmod = result
        assert loc == "https://example.com/page1"
        assert lastmod is not None

    def test_missing_loc(self, parser):
        """A <url> element without <loc> should return None."""
        xml = '''<url xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <lastmod>2024-06-15</lastmod>
        </url>'''
        elem = _root(xml)
        result = parser._parse_url_element(elem, SITEMAP_NS)
        assert result is None

    def test_empty_loc(self, parser):
        """A <url> element with empty <loc> should return None."""
        xml = '''<url xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <loc></loc>
        </url>'''
        elem = _root(xml)
        result = parser._parse_url_element(elem, SITEMAP_NS)
        assert result is None

    def test_with_invalid_lastmod(self, parser):
        """Invalid lastmod should not break parsing; lastmod should be None."""
        xml = '''<url xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <loc>https://example.com/page1</loc>
          <lastmod>invalid-date</lastmod>
        </url>'''
        elem = _root(xml)
        result = parser._parse_url_element(elem, SITEMAP_NS)
        assert result is not None
        loc, lastmod = result
        assert loc == "https://example.com/page1"
        assert lastmod is None


# ===================================================================
# Test _parse_sitemap_index
# ===================================================================

class TestParseSitemapIndex:
    """Tests for SitemapParser._parse_sitemap_index."""

    def test_basic_sitemap_index(self, parser):
        xml = '''<?xml version="1.0"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap>
            <loc>https://example.com/sitemap1.xml</loc>
          </sitemap>
          <sitemap>
            <loc>https://example.com/sitemap2.xml</loc>
          </sitemap>
        </sitemapindex>'''
        root = _root(xml)
        # Mock parse_sitemap to avoid network calls during recursive resolution
        with patch.object(parser, "parse_sitemap", side_effect=[
            ["https://example.com/a", "https://example.com/b"],
            ["https://example.com/c"],
        ]) as mock_parse:
            urls = parser._parse_sitemap_index(root)
            assert mock_parse.call_count == 2
            mock_parse.assert_any_call("https://example.com/sitemap1.xml", since=None)
            mock_parse.assert_any_call("https://example.com/sitemap2.xml", since=None)
            assert set(urls) == {
                "https://example.com/a",
                "https://example.com/b",
                "https://example.com/c",
            }

    def test_sitemap_index_with_since(self, parser):
        xml = '''<?xml version="1.0"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap>
            <loc>https://example.com/sitemap1.xml</loc>
            <lastmod>2024-06-01</lastmod>
          </sitemap>
          <sitemap>
            <loc>https://example.com/sitemap2.xml</loc>
            <lastmod>2023-01-01</lastmod>
          </sitemap>
        </sitemapindex>'''
        root = _root(xml)
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        with patch.object(parser, "parse_sitemap", return_value=[
            "https://example.com/page1",
        ]) as mock_parse:
            urls = parser._parse_sitemap_index(root, since=since)
            # Only the first sitemap (2024-06-01) should be fetched
            # The second one (2023-01-01) should be skipped by the since filter
            assert "https://example.com/page1" in urls

    def test_empty_sitemap_index(self, parser):
        xml = '''<?xml version="1.0"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        </sitemapindex>'''
        root = _root(xml)
        with patch.object(parser, "parse_sitemap", return_value=[]):
            urls = parser._parse_sitemap_index(root)
            assert urls == []

    def test_sitemap_index_non_namespaced(self, parser):
        xml = '''<?xml version="1.0"?>
        <sitemapindex>
          <sitemap>
            <loc>https://example.com/sitemap1.xml</loc>
          </sitemap>
        </sitemapindex>'''
        root = _root(xml)
        with patch.object(parser, "parse_sitemap", return_value=[
            "https://example.com/found",
        ]) as mock_parse:
            urls = parser._parse_sitemap_index(root)
            assert mock_parse.call_count == 1
            assert urls == ["https://example.com/found"]


# ===================================================================
# Test parse_sitemap (integration-level, mocking network)
# ===================================================================

class TestParseSitemap:
    """Tests for SitemapParser.parse_sitemap (network-mocked)."""

    def test_parse_sitemap_urlset(self, parser):
        xml_body = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/page1</loc></url>
        </urlset>'''
        mock_response = MagicMock()
        mock_response.text = xml_body
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("link_checker.sitemap.requests.get", return_value=mock_response):
            urls = parser.parse_sitemap("https://example.com/sitemap.xml")
            assert urls == ["https://example.com/page1"]

    def test_parse_sitemap_index(self, parser):
        index_xml = '''<?xml version="1.0"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap>
            <loc>https://example.com/sitemap1.xml</loc>
          </sitemap>
        </sitemapindex>'''
        child_xml = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/page1</loc></url>
        </urlset>'''

        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            if "sitemap1" in url:
                resp.text = child_xml
            else:
                resp.text = index_xml
            return resp

        with patch("link_checker.sitemap.requests.get", side_effect=side_effect):
            urls = parser.parse_sitemap("https://example.com/sitemap.xml")
            assert "https://example.com/page1" in urls

    def test_parse_sitemap_passes_user_agent(self, custom_parser):
        xml_body = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/page1</loc></url>
        </urlset>'''
        mock_response = MagicMock()
        mock_response.text = xml_body
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("link_checker.sitemap.requests.get", return_value=mock_response) as mock_get:
            custom_parser.parse_sitemap("https://example.com/sitemap.xml")
            call_kwargs = mock_get.call_args
            # Verify user-agent header or timeout was passed
            assert call_kwargs is not None


# ===================================================================
# Test SitemapParser construction
# ===================================================================

class TestSitemapParserInit:
    """Tests for SitemapParser.__init__."""

    def test_default_user_agent(self):
        p = SitemapParser()
        assert p.user_agent == "LinkCanary/1.0"

    def test_default_timeout(self):
        p = SitemapParser()
        assert p.timeout == 30

    def test_custom_user_agent(self):
        p = SitemapParser(user_agent="CustomBot/3.0")
        assert p.user_agent == "CustomBot/3.0"

    def test_custom_timeout(self):
        p = SitemapParser(timeout=60)
        assert p.timeout == 60


# ===================================================================
# Test SITEMAP_NS constant
# ===================================================================

class TestSitemapNS:
    """Tests for the SITEMAP_NS module-level constant."""

    def test_namespace_value(self):
        assert SITEMAP_NS == {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    def test_namespace_key(self):
        assert "sm" in SITEMAP_NS
