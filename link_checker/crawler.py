"""Page crawler and link extraction module."""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .utils import (
    is_internal_link,
    is_valid_http_url,
    resolve_relative_url,
    should_skip_link,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractedLink:
    """Represents a link extracted from a page."""
    source_url: str
    link_url: str
    link_text: str
    is_internal: bool
    element_type: str = field(default='a')
    is_mixed_content: bool = False


class PageCrawler:
    """Crawls pages and extracts links."""
    
    def __init__(
        self,
        base_url: str,
        user_agent: str = 'LinkCanary/1.0',
        timeout: int = 10,
        delay: float = 0.5,
        include_subdomains: bool = False,
    ):
        self.base_url = base_url
        self.user_agent = user_agent
        self.timeout = timeout
        self.delay = delay
        self.include_subdomains = include_subdomains
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        
        self._last_request_time = 0.0
    
    def _rate_limit(self):
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()
    
    def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch a page and return its HTML content.
        
        Returns None if the fetch fails.
        """
        self._rate_limit()
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                logger.debug(f"Skipping non-HTML content at {url}: {content_type}")
                return None
            
            return response.text
        except requests.Timeout:
            logger.warning(f"Timeout fetching {url}")
            return None
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None
    
    def _resolve_and_append(
        self,
        links: list,
        page_url: str,
        base_url: str,
        href: str,
        link_text: str,
        element_type: str,
    ):
        """Resolve a URL and append it to the links list if valid."""
        if should_skip_link(href):
            return
        
        absolute_url = resolve_relative_url(base_url, href)
        
        if not absolute_url or not is_valid_http_url(absolute_url):
            return
        
        is_internal = is_internal_link(
            absolute_url,
            self.base_url,
            self.include_subdomains,
        )

        # Detect mixed content: HTTP resource loaded on an HTTPS page.
        # Only applies to passive/active resource elements (img, script, link,
        # iframe), NOT to <a> navigation links which browsers allow freely.
        is_mixed_content = (
            element_type != 'a'
            and page_url.startswith('https://')
            and absolute_url.startswith('http://')
        )

        links.append(ExtractedLink(
            source_url=page_url,
            link_url=absolute_url,
            link_text=link_text,
            is_internal=is_internal,
            element_type=element_type,
            is_mixed_content=is_mixed_content,
        ))
    
    def extract_links(self, page_url: str, html: str) -> list[ExtractedLink]:
        """
        Extract all links from HTML content.
        
        Extracts links from <a href>, <img src>, <link href>,
        and <script src> tags.
        
        Args:
            page_url: The URL of the page (for resolving relative URLs)
            html: The HTML content
        
        Returns:
            List of ExtractedLink objects
        """
        links = []
        
        try:
            soup = BeautifulSoup(html, 'lxml')
        except Exception as e:
            logger.warning(f"Failed to parse HTML from {page_url}: {e}")
            return links
        
        base_url = page_url
        base_tag = soup.find('base', href=True)
        if base_tag:
            base_href = base_tag.get('href', '').strip()
            if base_href and is_valid_http_url(base_href):
                base_url = base_href
            elif base_href:
                resolved_base = resolve_relative_url(page_url, base_href)
                if resolved_base and is_valid_http_url(resolved_base):
                    base_url = resolved_base
        
        for anchor in soup.find_all('a', href=True):
            href = anchor.get('href', '').strip()
            link_text = anchor.get_text(strip=True)[:200]
            self._resolve_and_append(links, page_url, base_url, href, link_text, 'a')
        
        for img in soup.find_all('img', src=True):
            src = img.get('src', '').strip()
            alt_text = img.get('alt', '')[:200]
            self._resolve_and_append(links, page_url, base_url, src, alt_text, 'img')
        
        for link_tag in soup.find_all('link', href=True):
            href = link_tag.get('href', '').strip()
            rel = link_tag.get('rel', [])
            rel_text = ' '.join(rel) if isinstance(rel, list) else str(rel)
            self._resolve_and_append(links, page_url, base_url, href, rel_text[:200], 'link')
        
        for script in soup.find_all('script', src=True):
            src = script.get('src', '').strip()
            self._resolve_and_append(links, page_url, base_url, src, '', 'script')
        
        return links
    
    def crawl_page(self, url: str) -> list[ExtractedLink]:
        """
        Crawl a single page and extract all links.
        
        Args:
            url: The page URL to crawl
        
        Returns:
            List of ExtractedLink objects
        """
        html = self.fetch_page(url)
        if html is None:
            return []
        
        return self.extract_links(url, html)
    
    def crawl_pages(
        self,
        urls: list[str],
        progress_callback=None,
    ) -> list[ExtractedLink]:
        """
        Crawl multiple pages and extract all links.
        
        Args:
            urls: List of page URLs to crawl
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of all ExtractedLink objects from all pages
        """
        all_links = []
        
        for i, url in enumerate(urls):
            links = self.crawl_page(url)
            all_links.extend(links)
            
            if progress_callback:
                progress_callback(i + 1, len(urls), url, len(links))
        
        return all_links
    
    def close(self):
        """Close the session."""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
