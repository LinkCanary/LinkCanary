"""Tests for sitemap XML parsing."""

import pytest
from datetime import datetime
from xml.etree import ElementTree as ET
from unittest.mock import patch, MagicMock

from link_checker.sitemap import SitemapParser, SITEMAP_NS


class TestParseUrlset:

    def setup_method(self):
        self.parser = SitemapParser()

    def test_namespaced_urlset(self):
        xml = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/page1</loc></url>
          <url><loc>https://example.com/page2</loc></url>
        </urlset>'''
        root = ET.fromstring(xml)
        urls = self.parser._parse_urlset(root)
        assert urls == ["https://example.com/page1", "https://example.com/page2"]

    def test_non_namespaced_urlset(self):
        xml = '''<?xml version="1.0"?>
        <urlset>
          <url><loc>https://example.com/page1</loc></url>
        </urlset>'''
        root = ET.fromstring(xml)
        urls = self.parser._parse_urlset(root)
        assert urls == ["https://example.com/page1"]

    def test_empty_urlset(self):
        xml = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        </urlset>'''
        root = ET.fromstring(xml)
        urls = self.parser._parse_urlset(root)
        assert urls == []

    def test_urlset_with_lastmod(self):
        xml = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url>
            <loc>https://example.com/new</loc>
            <lastmod>2024-06-01</lastmod>
          </url>
          <url>
            <loc>https://example.com/old</loc>
            <lastmod>2020-01-01</lastmod>
          </url>
        </urlset>'''
        root = ET.fromstring(xml)
        since = datetime(2023, 1, 1)
        urls = self.parser._parse_urlset(root, since=since)
        assert "https://example.com/new" in urls
        assert "https://example.com/old" not in urls

    def test_whitespace_in_loc(self):
        xml = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>  https://example.com/page  </loc></url>
        </urlset>'''
        root = ET.fromstring(xml)
        urls = self.parser._parse_urlset(root)
        assert urls == ["https://example.com/page"]


class TestParseLastmod:

    def setup_method(self):
        self.parser = SitemapParser()

    def test_date_only(self):
        result = self.parser._parse_lastmod("2024-01-15")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_iso_with_z(self):
        result = self.parser._parse_lastmod("2024-01-15T10:30:00Z")
        assert result is not None

    def test_iso_with_offset(self):
        result = self.parser._parse_lastmod("2024-01-15T10:30:00+00:00")
        assert result is not None

    def test_iso_without_timezone(self):
        result = self.parser._parse_lastmod("2024-01-15T10:30:00")
        assert result is not None

    def test_invalid_format(self):
        result = self.parser._parse_lastmod("not-a-date")
        assert result is None

    def test_empty_string(self):
        result = self.parser._parse_lastmod("")
        assert result is None


class TestShouldInclude:

    def setup_method(self):
        self.parser = SitemapParser()

    def test_no_since_filter(self):
        assert self.parser._should_include(None, None)

    def test_no_lastmod_with_since(self):
        assert self.parser._should_include(None, datetime(2024, 1, 1))

    def test_after_since(self):
        assert self.parser._should_include(
            datetime(2024, 6, 1), datetime(2024, 1, 1),
        )

    def test_before_since(self):
        assert not self.parser._should_include(
            datetime(2023, 1, 1), datetime(2024, 1, 1),
        )

    def test_equal_to_since(self):
        dt = datetime(2024, 1, 1)
        assert self.parser._should_include(dt, dt)


class TestParseUrlElement:

    def setup_method(self):
        self.parser = SitemapParser()

    def test_with_loc_namespaced(self):
        xml = '<url xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><loc>https://example.com/page</loc></url>'
        elem = ET.fromstring(xml)
        result = self.parser._parse_url_element(elem, SITEMAP_NS)
        assert result is not None
        assert result[0] == "https://example.com/page"

    def test_with_loc_non_namespaced(self):
        xml = '<url><loc>https://example.com/page</loc></url>'
        elem = ET.fromstring(xml)
        result = self.parser._parse_url_element(elem, {})
        assert result is not None
        assert result[0] == "https://example.com/page"

    def test_missing_loc(self):
        xml = '<url><lastmod>2024-01-01</lastmod></url>'
        elem = ET.fromstring(xml)
        result = self.parser._parse_url_element(elem, {})
        assert result is None

    def test_empty_loc(self):
        xml = '<url><loc></loc></url>'
        elem = ET.fromstring(xml)
        result = self.parser._parse_url_element(elem, {})
        assert result is None

    def test_with_lastmod(self):
        xml = '<url><loc>https://example.com/page</loc><lastmod>2024-01-15</lastmod></url>'
        elem = ET.fromstring(xml)
        result = self.parser._parse_url_element(elem, {})
        assert result is not None
        assert result[1] is not None
        assert result[1].year == 2024


class TestSitemapParserInit:

    def test_defaults(self):
        parser = SitemapParser()
        assert parser.user_agent == "LinkCanary/1.0"
        assert parser.timeout == 30

    def test_custom_values(self):
        parser = SitemapParser(user_agent="TestBot/2.0", timeout=60)
        assert parser.user_agent == "TestBot/2.0"
        assert parser.timeout == 60

    def test_context_manager(self):
        with SitemapParser() as parser:
            assert parser is not None


class TestSitemapNS:

    def test_namespace_value(self):
        assert "sm" in SITEMAP_NS
        assert SITEMAP_NS["sm"] == "http://www.sitemaps.org/schemas/sitemap/0.9"
