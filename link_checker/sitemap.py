"""Sitemap parsing module."""

import gzip
import logging
from datetime import datetime
from io import BytesIO
from typing import Optional
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger(__name__)

SITEMAP_NS = {
    'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
}


class SitemapParser:
    """Parser for XML sitemaps and sitemap indexes."""
    
    def __init__(
        self,
        user_agent: str = 'LinkCanary/1.0',
        timeout: int = 30,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'application/xml, text/xml, */*',
        })
    
    def fetch_sitemap(self, url: str) -> Optional[bytes]:
        """Fetch sitemap content from URL."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            if url.endswith('.gz') or response.headers.get('Content-Encoding') == 'gzip':
                try:
                    return gzip.decompress(response.content)
                except gzip.BadGzipFile:
                    return response.content
            
            return response.content
        except requests.RequestException as e:
            logger.error(f"Failed to fetch sitemap {url}: {e}")
            return None
    
    def parse_sitemap(
        self,
        url: str,
        since: Optional[datetime] = None,
    ) -> list[str]:
        """
        Parse a sitemap and return list of page URLs.
        
        Handles both regular sitemaps and sitemap indexes.
        
        Args:
            url: URL to the sitemap
            since: Optional datetime to filter pages by lastmod
        
        Returns:
            List of page URLs
        """
        content = self.fetch_sitemap(url)
        if not content:
            return []
        
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            logger.error(f"Failed to parse sitemap XML from {url}: {e}")
            return []
        
        tag_name = root.tag.split('}')[-1] if '}' in root.tag else root.tag
        
        if tag_name == 'sitemapindex':
            return self._parse_sitemap_index(root, since)
        elif tag_name == 'urlset':
            return self._parse_urlset(root, since)
        else:
            logger.warning(f"Unknown sitemap root element: {tag_name}")
            return []
    
    def _parse_sitemap_index(
        self,
        root: ET.Element,
        since: Optional[datetime] = None,
    ) -> list[str]:
        """Parse a sitemap index and recursively fetch all referenced sitemaps."""
        urls = []
        
        for sitemap in root.findall('sm:sitemap', SITEMAP_NS):
            loc = sitemap.find('sm:loc', SITEMAP_NS)
            if loc is not None and loc.text:
                sitemap_url = loc.text.strip()
                logger.info(f"Found nested sitemap: {sitemap_url}")
                nested_urls = self.parse_sitemap(sitemap_url, since)
                urls.extend(nested_urls)
        
        for sitemap in root.findall('sitemap'):
            loc = sitemap.find('loc')
            if loc is not None and loc.text:
                sitemap_url = loc.text.strip()
                logger.info(f"Found nested sitemap: {sitemap_url}")
                nested_urls = self.parse_sitemap(sitemap_url, since)
                urls.extend(nested_urls)
        
        return urls
    
    def _parse_urlset(
        self,
        root: ET.Element,
        since: Optional[datetime] = None,
    ) -> list[str]:
        """Parse a urlset and extract page URLs."""
        urls = []
        
        for url_elem in root.findall('sm:url', SITEMAP_NS):
            url_data = self._parse_url_element(url_elem, SITEMAP_NS)
            if url_data:
                loc, lastmod = url_data
                if self._should_include(lastmod, since):
                    urls.append(loc)
        
        for url_elem in root.findall('url'):
            url_data = self._parse_url_element(url_elem, {})
            if url_data:
                loc, lastmod = url_data
                if self._should_include(lastmod, since):
                    urls.append(loc)
        
        return urls
    
    def _parse_url_element(
        self,
        url_elem: ET.Element,
        ns: dict,
    ) -> Optional[tuple[str, Optional[datetime]]]:
        """Parse a single URL element."""
        if ns:
            loc_elem = url_elem.find('sm:loc', ns)
            lastmod_elem = url_elem.find('sm:lastmod', ns)
        else:
            loc_elem = url_elem.find('loc')
            lastmod_elem = url_elem.find('lastmod')
        
        if loc_elem is None or not loc_elem.text:
            return None
        
        loc = loc_elem.text.strip()
        lastmod = None
        
        if lastmod_elem is not None and lastmod_elem.text:
            lastmod = self._parse_lastmod(lastmod_elem.text.strip())
        
        return loc, lastmod
    
    def _parse_lastmod(self, lastmod_str: str) -> Optional[datetime]:
        """Parse a lastmod date string."""
        formats = [
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S.%f%z',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d',
        ]
        
        lastmod_str = lastmod_str.replace('+00:00', 'Z').replace('Z', '+0000')
        
        for fmt in formats:
            try:
                return datetime.strptime(lastmod_str, fmt)
            except ValueError:
                continue
        
        logger.debug(f"Could not parse lastmod date: {lastmod_str}")
        return None
    
    def _should_include(
        self,
        lastmod: Optional[datetime],
        since: Optional[datetime],
    ) -> bool:
        """Check if a URL should be included based on lastmod filter."""
        if since is None:
            return True
        
        if lastmod is None:
            return True
        
        if lastmod.tzinfo is not None and since.tzinfo is None:
            lastmod = lastmod.replace(tzinfo=None)
        elif lastmod.tzinfo is None and since.tzinfo is not None:
            since = since.replace(tzinfo=None)
        
        return lastmod >= since
    
    def close(self):
        """Close the session."""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
