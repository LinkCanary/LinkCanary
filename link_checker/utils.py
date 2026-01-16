"""URL normalization and utility functions."""

import re
from urllib.parse import urlparse, urlunparse, unquote, urlencode, parse_qsl


def normalize_url(url: str) -> str:
    """
    Normalize a URL for consistent comparison and deduplication.
    
    Rules applied:
    1. Convert scheme and host to lowercase
    2. Remove default ports (:80 for http, :443 for https)
    3. Decode unnecessary percent-encoding
    4. Remove empty query strings
    5. Remove fragments
    6. Sort query parameters alphabetically
    """
    if not url:
        return url
    
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    if netloc.endswith(':80') and scheme == 'http':
        netloc = netloc[:-3]
    elif netloc.endswith(':443') and scheme == 'https':
        netloc = netloc[:-4]
    
    path = unquote(parsed.path)
    path = re.sub(r'%([0-9A-Fa-f]{2})', lambda m: chr(int(m.group(1), 16)), path)
    
    if parsed.query:
        query_params = parse_qsl(parsed.query, keep_blank_values=True)
        query_params.sort(key=lambda x: x[0])
        query = urlencode(query_params)
    else:
        query = ''
    
    normalized = urlunparse((scheme, netloc, path, '', query, ''))
    
    return normalized


def is_canonical_redirect(source_url: str, dest_url: str) -> bool:
    """
    Check if a redirect is a canonical redirect (trailing slash, case, or protocol only).
    
    Returns True if the only difference between URLs is:
    - Trailing slash (/page vs /page/)
    - Case difference (/Page vs /page)
    - Protocol (http vs https)
    """
    if not source_url or not dest_url:
        return False
    
    try:
        source = urlparse(source_url)
        dest = urlparse(dest_url)
    except Exception:
        return False
    
    source_host = source.netloc.lower().rstrip(':80').rstrip(':443')
    dest_host = dest.netloc.lower().rstrip(':80').rstrip(':443')
    
    if source_host != dest_host:
        return False
    
    source_path = source.path.lower()
    dest_path = dest.path.lower()
    
    source_path_stripped = source_path.rstrip('/')
    dest_path_stripped = dest_path.rstrip('/')
    
    if source_path_stripped != dest_path_stripped:
        return False
    
    source_query = source.query
    dest_query = dest.query
    
    if source_query != dest_query:
        return False
    
    return True


def get_domain(url: str) -> str:
    """Extract the domain (netloc) from a URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ''


def get_root_domain(url: str) -> str:
    """
    Extract the root domain from a URL.
    
    Examples:
    - blog.example.com -> example.com
    - www.example.co.uk -> example.co.uk
    """
    domain = get_domain(url)
    if not domain:
        return ''
    
    domain = domain.split(':')[0]
    
    parts = domain.split('.')
    
    if len(parts) <= 2:
        return domain
    
    common_tlds = {'co.uk', 'com.au', 'co.nz', 'co.za', 'com.br', 'co.jp', 'co.kr'}
    
    if len(parts) >= 3:
        potential_tld = '.'.join(parts[-2:])
        if potential_tld in common_tlds:
            return '.'.join(parts[-3:])
    
    return '.'.join(parts[-2:])


def is_internal_link(link_url: str, base_url: str, include_subdomains: bool = False) -> bool:
    """
    Determine if a link is internal to the base URL's domain.
    
    Args:
        link_url: The URL to check
        base_url: The base URL (sitemap URL)
        include_subdomains: If True, subdomains are considered internal
    """
    if not link_url or not base_url:
        return False
    
    link_domain = get_domain(link_url)
    base_domain = get_domain(base_url)
    
    if not link_domain or not base_domain:
        return False
    
    link_domain = link_domain.split(':')[0]
    base_domain = base_domain.split(':')[0]
    
    if link_domain == base_domain:
        return True
    
    if include_subdomains:
        link_root = get_root_domain(link_url)
        base_root = get_root_domain(base_url)
        return link_root == base_root
    
    return False


def is_valid_http_url(url: str) -> bool:
    """Check if a URL is a valid HTTP/HTTPS URL."""
    if not url:
        return False
    
    try:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except Exception:
        return False


def should_skip_link(href: str) -> bool:
    """
    Determine if a link should be skipped (non-HTTP links).
    
    Skips: mailto:, tel:, javascript:, #anchors, data:, file:
    """
    if not href:
        return True
    
    href = href.strip()
    
    if href.startswith('#'):
        return True
    
    skip_schemes = ('mailto:', 'tel:', 'javascript:', 'data:', 'file:', 'ftp:', 'ssh:')
    href_lower = href.lower()
    
    for scheme in skip_schemes:
        if href_lower.startswith(scheme):
            return True
    
    return False


def resolve_relative_url(base_url: str, relative_url: str) -> str:
    """
    Resolve a relative URL against a base URL.
    """
    from urllib.parse import urljoin
    
    if not relative_url:
        return ''
    
    relative_url = relative_url.strip()
    
    if should_skip_link(relative_url):
        return ''
    
    try:
        absolute = urljoin(base_url, relative_url)
        
        if '#' in absolute:
            absolute = absolute.split('#')[0]
        
        return absolute
    except Exception:
        return ''


def format_redirect_chain(chain: list[tuple[int, str]]) -> str:
    """
    Format a redirect chain with status codes.
    
    Args:
        chain: List of (status_code, url) tuples
    
    Returns:
        Formatted string like "301:url1 → 302:url2 → 200:url3"
    """
    if not chain:
        return ''
    
    parts = [f"{status}:{url}" for status, url in chain]
    return ' → '.join(parts)


def truncate_string(s: str, max_length: int = 100) -> str:
    """Truncate a string to a maximum length, adding ellipsis if needed."""
    if not s or len(s) <= max_length:
        return s
    return s[:max_length - 3] + '...'
