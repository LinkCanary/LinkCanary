"""Backlink checker API endpoints."""

import re
from urllib.parse import urljoin, urlparse

from fastapi import APIRouter, HTTPException
from requests import RequestException

from ..models.schemas import (
    BacklinkCheckRequest,
    BacklinkCheckResponse,
    BacklinkSource,
)
from link_checker.sitemap import SitemapParser

router = APIRouter(prefix="/api/backlinks", tags=["backlinks"])


def normalize_url(url: str) -> str:
    """Normalize URL for comparison."""
    url = url.strip()
    if url.startswith('//'):
        url = 'https:' + url
    elif not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url.rstrip('/')


def contains_link(html: str, target_url: str) -> tuple[bool, str | None]:
    """Check if HTML contains a link to target URL and extract link text."""
    target_normalized = normalize_url(target_url)
    
    # Match href attributes with the target URL
    # Look for both exact matches and partial matches (path variations)
    href_pattern = r'<a\b[^>]*\bhref\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>'
    matches = re.finditer(href_pattern, html, re.IGNORECASE | re.DOTALL)
    
    for match in matches:
        link_url = match.group(1)
        link_text = match.group(2).strip()
        
        try:
            # Resolve relative URLs and compare
            parsed_link = urlparse(link_url)
            if not parsed_link.scheme:
                # This is a relative URL, we'd need the base URL to resolve it
                # For now, skip relative URLs as we can't determine the target without context
                continue
            
            link_normalized = normalize_url(link_url)
            
            # Check if the URLs match (either exact or path-only match)
            if link_normalized == target_normalized:
                return True, link_text
            
            # Also check for path-only match (ignoring trailing slashes)
            target_path = urlparse(target_normalized).path
            link_path = urlparse(link_normalized).path
            
            if target_path.rstrip('/') == link_path.rstrip('/'):
                # Verify the domain matches the target
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
    target_url = normalize_url(request.target_url)
    sitemap_url = normalize_url(request.sitemap_url)
    
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
                found, link_text = contains_link(response.text, target_url)
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
