"""Backlink checker API endpoints."""

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from requests import RequestException

from ..models.schemas import (
    BacklinkCheckRequest,
    BacklinkCheckResponse,
    BacklinkSource,
)
from link_checker.sitemap import SitemapParser
from link_checker.utils import normalize_url

router = APIRouter(prefix="/api/backlinks", tags=["backlinks"])


def _normalize_for_comparison(url: str) -> str:
    """Normalize URL for backlink comparison (adds scheme if missing)."""
    url = url.strip()
    if url.startswith('//'):
        url = 'https:' + url
    elif not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return normalize_url(url)


def contains_link(
    html: str,
    target_url: str,
    source_url: str | None = None,
) -> tuple[bool, str | None]:
    """Check if HTML contains a link to target URL and extract link text.
    
    Uses BeautifulSoup for robust HTML parsing and respects <base href>
    tags for resolving relative URLs (important for WordPress/blog
    subdirectory sites).
    
    Args:
        html: The HTML content to search
        target_url: The URL to look for in links
        source_url: The URL of the page (used to resolve relative links)
    """
    target_normalized = _normalize_for_comparison(target_url)
    
    try:
        soup = BeautifulSoup(html, 'lxml')
    except Exception:
        return False, None
    
    effective_base = source_url
    if source_url:
        base_tag = soup.find('base', href=True)
        if base_tag:
            base_href = base_tag['href'].strip()
            if base_href:
                effective_base = urljoin(source_url, base_href)
    
    for anchor in soup.find_all('a', href=True):
        href = anchor.get('href', '').strip()
        if not href:
            continue
        
        link_text = anchor.get_text(separator=' ', strip=True)
        
        try:
            parsed_link = urlparse(href)
            if not parsed_link.scheme:
                if effective_base is None:
                    continue
                link_url = urljoin(effective_base, href)
                parsed_link = urlparse(link_url)
                if not parsed_link.scheme:
                    continue
            else:
                link_url = href
            
            link_normalized = _normalize_for_comparison(link_url)
            
            if link_normalized == target_normalized:
                return True, link_text
            
            target_path = urlparse(target_normalized).path
            link_path = urlparse(link_normalized).path
            
            if target_path.rstrip('/') == link_path.rstrip('/'):
                target_domain = urlparse(target_normalized).netloc
                link_domain = urlparse(link_normalized).netloc
                if target_domain == link_domain:
                    return True, link_text
                    
        except Exception:
            continue
    
    return False, None


@router.post("/check", response_model=BacklinkCheckResponse)
async def check_backlinks(request: BacklinkCheckRequest):
    """Check for backlinks to a target URL from pages in a sitemap."""
    sitemap_parser = SitemapParser(
        user_agent=request.user_agent,
        timeout=request.timeout,
    )
    
    sources = []
    target_url = _normalize_for_comparison(request.target_url)
    sitemap_url = _normalize_for_comparison(request.sitemap_url)
    
    try:
        # Parse the sitemap to get pages to check
        page_urls = sitemap_parser.parse_sitemap(sitemap_url)
    except Exception as e:
        sitemap_parser.close()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse sitemap: {str(e)}"
        )
    finally:
        sitemap_parser.close()
    
    if not page_urls:
        raise HTTPException(
            status_code=404,
            detail="No pages found in sitemap"
        )
    
    import requests
    
    backlinks_found = 0
    checked_count = 0
    
    # Check each page for backlinks
    for page_url in page_urls:
        checked_count += 1
        
        try:
            response = requests.get(
                page_url,
                timeout=request.timeout,
                headers={"User-Agent": request.user_agent},
            )
            
            if response.status_code == 200:
                found, link_text = contains_link(
                    response.text, target_url, source_url=page_url,
                )
                backlinks_found += 1 if found else 0
                
                sources.append(BacklinkSource(
                    source_url=page_url,
                    found=found,
                    link_text=link_text if found else None,
                    error=None,
                ))
            else:
                sources.append(BacklinkSource(
                    source_url=page_url,
                    found=False,
                    link_text=None,
                    error=f"HTTP {response.status_code}",
                ))
        except RequestException as e:
            sources.append(BacklinkSource(
                source_url=page_url,
                found=False,
                link_text=None,
                error=str(e),
            ))
    
    return BacklinkCheckResponse(
        target_url=target_url,
        sitemap_url=sitemap_url,
        pages_checked=checked_count,
        backlinks_found=backlinks_found,
        sources=sources,
        total_pages=len(page_urls),
    )
