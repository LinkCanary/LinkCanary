"""Link status checking and redirect tracing module."""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

from .utils import format_redirect_chain, get_domain, is_canonical_redirect

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 10


@dataclass
class LinkStatus:
    """Result of checking a single link."""
    url: str
    status_code: int
    is_redirect: bool = False
    redirect_chain: list[tuple[int, str]] = field(default_factory=list)
    final_url: str = ''
    is_loop: bool = False
    is_canonical_redirect: bool = False
    error: str = ''
    retries: int = 0  # Number of retries needed for transient errors
    
    @property
    def redirect_chain_formatted(self) -> str:
        """Get the redirect chain as a formatted string."""
        return format_redirect_chain(self.redirect_chain)


class LinkChecker:
    """Checks link status and traces redirect chains."""
    
    # Status codes that trigger retry
    RETRY_STATUS_CODES = {502, 503, 504}
    # Default retry settings
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0  # seconds
    DEFAULT_RETRY_BACKOFF = 2.0  # multiplier
    
    def __init__(
        self,
        user_agent: str = 'LinkCanary/1.0',
        timeout: int = 10,
        delay: float = 0.1,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        retry_backoff: float = 2.0,
        auth_user: Optional[str] = None,
        auth_pass: Optional[str] = None,
        headers: Optional[dict] = None,
        cookies: Optional[dict] = None,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.delay = delay
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff
        self.auth_user = auth_user
        self.auth_pass = auth_pass
        self.custom_headers = headers or {}
        self.cookies = cookies
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': '*/*',
        })
        
        # Add custom headers
        if self.custom_headers:
            self.session.headers.update(self.custom_headers)
        
        # Add basic auth
        if self.auth_user and self.auth_pass:
            self.session.auth = (self.auth_user, self.auth_pass)
        
        # Add cookies
        if self.cookies:
            self.session.cookies.update(self.cookies)
        
        self._cache: dict[str, LinkStatus] = {}
        self._head_blacklist: set[str] = set()
        self._host_delays: dict[str, float] = {}
        self._last_request_time: dict[str, float] = {}
        self._retry_stats: dict[str, int] = {}  # Track retry counts per URL
    
    def _get_host_delay(self, url: str) -> float:
        """Get the current delay for a host."""
        host = get_domain(url)
        return self._host_delays.get(host, self.delay)
    
    def _increase_host_delay(self, url: str):
        """Double the delay for a host (rate limit backoff)."""
        host = get_domain(url)
        current = self._host_delays.get(host, self.delay)
        self._host_delays[host] = min(current * 2, 30.0)
        logger.info(f"Increased delay for {host} to {self._host_delays[host]}s")
    
    def _rate_limit(self, url: str):
        """Apply rate limiting for a specific host."""
        host = get_domain(url)
        last_time = self._last_request_time.get(host, 0)
        delay = self._get_host_delay(url)
        
        elapsed = time.time() - last_time
        if elapsed < delay:
            time.sleep(delay - elapsed)
        
        self._last_request_time[host] = time.time()
    
    def _should_use_get(self, url: str) -> bool:
        """Check if we should skip HEAD and use GET directly."""
        host = get_domain(url)
        return host in self._head_blacklist
    
    def _add_to_head_blacklist(self, url: str):
        """Add a host to the HEAD request blacklist."""
        host = get_domain(url)
        if host not in self._head_blacklist:
            self._head_blacklist.add(host)
            logger.debug(f"Added {host} to HEAD blacklist")
    
    def _make_request(
        self,
        url: str,
        method: str = 'HEAD',
        allow_redirects: bool = False,
    ) -> Optional[requests.Response]:
        """Make an HTTP request with error handling."""
        self._rate_limit(url)
        
        try:
            if method == 'HEAD':
                response = self.session.head(
                    url,
                    timeout=self.timeout,
                    allow_redirects=allow_redirects,
                )
            else:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=allow_redirects,
                    stream=True,
                )
            return response
        except requests.Timeout:
            return None
        except requests.RequestException:
            return None
    
    def _make_request_with_retry(
        self,
        url: str,
        method: str = 'HEAD',
        allow_redirects: bool = False,
    ) -> tuple[Optional[requests.Response], int]:
        """
        Make an HTTP request with retry logic for transient errors.
        
        Retries on:
        - 502 Bad Gateway
        - 503 Service Unavailable
        - 504 Gateway Timeout
        
        Uses exponential backoff between retries.
        
        Returns:
            Tuple of (response, retry_count)
        """
        retry_count = 0
        current_delay = self.retry_delay
        
        while retry_count <= self.max_retries:
            response = self._make_request(url, method, allow_redirects)
            
            # No response (timeout/connection error) - might be transient
            if response is None:
                if retry_count < self.max_retries:
                    retry_count += 1
                    logger.debug(f"Retrying {url} (attempt {retry_count}/{self.max_retries}) - no response")
                    time.sleep(current_delay)
                    current_delay *= self.retry_backoff
                    continue
                return None, retry_count
            
            # Success or non-retryable status
            if response.status_code not in self.RETRY_STATUS_CODES:
                return response, retry_count
            
            # Retryable server error (502/503/504)
            if retry_count < self.max_retries:
                retry_count += 1
                logger.debug(
                    f"Retrying {url} (attempt {retry_count}/{self.max_retries}) - "
                    f"status {response.status_code}"
                )
                time.sleep(current_delay)
                current_delay *= self.retry_backoff
            else:
                # Max retries reached, return the error response
                return response, retry_count
        
        return response, retry_count
    
    def _check_single_url(self, url: str) -> tuple[int, str, Optional[str], int]:
        """
        Check a single URL's status without following redirects.
        
        Returns:
            Tuple of (status_code, redirect_location or '', error_message or None, retry_count)
        """
        use_get = self._should_use_get(url)
        retry_count = 0
        
        if not use_get:
            response, retry_count = self._make_request_with_retry(url, 'HEAD', allow_redirects=False)
            
            if response is not None:
                if response.status_code in (403, 405, 501):
                    self._add_to_head_blacklist(url)
                    use_get = True
                else:
                    location = response.headers.get('Location', '')
                    return response.status_code, location, None, retry_count
        
        if use_get or response is None:
            response, retry_count = self._make_request_with_retry(url, 'GET', allow_redirects=False)
        
        if response is None:
            return 0, '', 'Request failed (timeout or connection error)', retry_count
        
        if response.status_code == 429:
            self._increase_host_delay(url)
            time.sleep(self._get_host_delay(url))
            response, retry_count = self._make_request_with_retry(url, 'GET', allow_redirects=False)
            
            if response is None or response.status_code == 429:
                self._increase_host_delay(url)
                time.sleep(self._get_host_delay(url))
                response, retry_count = self._make_request_with_retry(url, 'GET', allow_redirects=False)
                
                if response is None or response.status_code == 429:
                    return 429, '', 'Rate limited after retries', retry_count
        
        location = response.headers.get('Location', '')
        return response.status_code, location, None, retry_count
    
    def check_link(self, url: str) -> LinkStatus:
        """
        Check a link's status, following redirects and detecting issues.
        
        Args:
            url: The URL to check
        
        Returns:
            LinkStatus object with all details
        """
        if url in self._cache:
            return self._cache[url]
        
        chain: list[tuple[int, str]] = []
        visited: set[str] = set()
        current_url = url
        is_loop = False
        error = ''
        total_retries = 0
        
        for _ in range(MAX_REDIRECTS + 1):
            if current_url in visited:
                is_loop = True
                break
            
            visited.add(current_url)
            status_code, location, req_error, retry_count = self._check_single_url(current_url)
            total_retries += retry_count
            
            if req_error:
                error = req_error
                chain.append((0, current_url))
                break
            
            chain.append((status_code, current_url))
            
            if status_code < 300 or status_code >= 400:
                break
            
            if not location:
                break
            
            if not location.startswith('http'):
                from urllib.parse import urljoin
                location = urljoin(current_url, location)
            
            current_url = location
        
        if chain:
            final_status = chain[-1][0]
            final_url = chain[-1][1]
        else:
            final_status = 0
            final_url = url
        
        is_redirect = len(chain) > 1
        
        is_canonical = False
        if is_redirect and len(chain) == 2 and not is_loop:
            is_canonical = is_canonical_redirect(url, final_url)
        
        result = LinkStatus(
            url=url,
            status_code=final_status,
            is_redirect=is_redirect,
            redirect_chain=chain,
            final_url=final_url,
            is_loop=is_loop,
            is_canonical_redirect=is_canonical,
            error=error,
            retries=total_retries,
        )
        
        self._cache[url] = result
        return result
    
    def check_links(
        self,
        urls: list[str],
        progress_callback=None,
    ) -> dict[str, LinkStatus]:
        """
        Check multiple links.
        
        Args:
            urls: List of URLs to check
            progress_callback: Optional callback for progress updates
        
        Returns:
            Dictionary mapping URL to LinkStatus
        """
        results = {}
        
        for i, url in enumerate(urls):
            status = self.check_link(url)
            results[url] = status
            
            if progress_callback:
                progress_callback(i + 1, len(urls), url, status)
        
        return results
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        total_retries = sum(status.retries for status in self._cache.values())
        urls_with_retries = sum(1 for status in self._cache.values() if status.retries > 0)
        
        return {
            'cached_urls': len(self._cache),
            'head_blacklisted_hosts': len(self._head_blacklist),
            'hosts_with_custom_delay': len(self._host_delays),
            'total_retries': total_retries,
            'urls_with_retries': urls_with_retries,
        }
    
    def close(self):
        """Close the session."""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
