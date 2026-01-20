"""Crawl API endpoints."""

import csv
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Crawl, CrawlStatus, get_db
from ..models.schemas import (
    CrawlCreate,
    CrawlListResponse,
    CrawlResponse,
    ReportIssue,
    ReportResponse,
    ValidateSitemapRequest,
    ValidateSitemapResponse,
)
from ..tasks.crawl_task import run_crawl_in_background

router = APIRouter(prefix="/api/crawls", tags=["crawls"])


def extract_domain(url: str) -> str:
    """Extract domain from URL for crawl name."""
    parsed = urlparse(url)
    return parsed.netloc or url


@router.post("", response_model=CrawlResponse)
async def create_crawl(
    request: CrawlCreate,
    db: AsyncSession = Depends(get_db),
):
    """Start a new crawl."""
    name = request.name or extract_domain(request.sitemap_url)
    
    crawl = Crawl(
        name=name,
        sitemap_url=request.sitemap_url,
        status=CrawlStatus.PENDING,
        internal_only=request.settings.internal_only,
        external_only=request.settings.external_only,
        skip_ok=request.settings.skip_ok,
        expand_duplicates=request.settings.expand_duplicates,
        include_subdomains=request.settings.include_subdomains,
        delay=request.settings.delay,
        timeout=request.settings.timeout,
        max_pages=request.settings.max_pages,
        since_date=request.settings.since,
        user_agent=request.settings.user_agent,
    )
    
    db.add(crawl)
    await db.commit()
    await db.refresh(crawl)
    
    run_crawl_in_background(crawl.id)
    
    return CrawlResponse(**crawl.to_dict())


@router.get("", response_model=CrawlListResponse)
async def list_crawls(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all crawls."""
    query = select(Crawl).order_by(desc(Crawl.created_at))
    
    if status:
        try:
            status_enum = CrawlStatus(status)
            query = query.where(Crawl.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    count_result = await db.execute(select(Crawl))
    total = len(count_result.scalars().all())
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    crawls = result.scalars().all()
    
    return CrawlListResponse(
        crawls=[CrawlResponse(**c.to_dict()) for c in crawls],
        total=total,
    )


@router.get("/{crawl_id}", response_model=CrawlResponse)
async def get_crawl(
    crawl_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get crawl details."""
    result = await db.execute(select(Crawl).where(Crawl.id == crawl_id))
    crawl = result.scalar_one_or_none()
    
    if not crawl:
        raise HTTPException(status_code=404, detail="Crawl not found")
    
    return CrawlResponse(**crawl.to_dict())


@router.delete("/{crawl_id}")
async def delete_crawl(
    crawl_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a crawl and its reports."""
    result = await db.execute(select(Crawl).where(Crawl.id == crawl_id))
    crawl = result.scalar_one_or_none()
    
    if not crawl:
        raise HTTPException(status_code=404, detail="Crawl not found")
    
    await db.delete(crawl)
    await db.commit()
    
    return {"message": "Crawl deleted"}


@router.post("/{crawl_id}/stop")
async def stop_crawl(
    crawl_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Stop a running crawl."""
    result = await db.execute(select(Crawl).where(Crawl.id == crawl_id))
    crawl = result.scalar_one_or_none()
    
    if not crawl:
        raise HTTPException(status_code=404, detail="Crawl not found")
    
    if crawl.status != CrawlStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Crawl is not running")
    
    crawl.status = CrawlStatus.CANCELLED
    crawl.completed_at = datetime.utcnow()
    await db.commit()
    
    return {"message": "Crawl stopped"}


@router.post("/{crawl_id}/rerun", response_model=CrawlResponse)
async def rerun_crawl(
    crawl_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Re-run a crawl with the same settings."""
    result = await db.execute(select(Crawl).where(Crawl.id == crawl_id))
    original = result.scalar_one_or_none()
    
    if not original:
        raise HTTPException(status_code=404, detail="Crawl not found")
    
    crawl = Crawl(
        name=f"{original.name} (re-run)",
        sitemap_url=original.sitemap_url,
        status=CrawlStatus.PENDING,
        internal_only=original.internal_only,
        external_only=original.external_only,
        skip_ok=original.skip_ok,
        expand_duplicates=original.expand_duplicates,
        include_subdomains=original.include_subdomains,
        delay=original.delay,
        timeout=original.timeout,
        max_pages=original.max_pages,
        since_date=original.since_date,
        user_agent=original.user_agent,
    )
    
    db.add(crawl)
    await db.commit()
    await db.refresh(crawl)
    
    run_crawl_in_background(crawl.id)
    
    return CrawlResponse(**crawl.to_dict())


@router.get("/{crawl_id}/report", response_model=ReportResponse)
async def get_report(
    crawl_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get report data as JSON."""
    result = await db.execute(select(Crawl).where(Crawl.id == crawl_id))
    crawl = result.scalar_one_or_none()
    
    if not crawl:
        raise HTTPException(status_code=404, detail="Crawl not found")
    
    if not crawl.report_csv_path:
        raise HTTPException(status_code=404, detail="Report not available")
    
    issues = []
    try:
        with open(crawl.report_csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                example_pages = row.get('example_pages', '')
                issues.append(ReportIssue(
                    source_page=row.get('source_page', ''),
                    occurrence_count=int(row.get('occurrence_count', 1)),
                    example_pages=example_pages.split('|') if example_pages else [],
                    link_url=row.get('link_url', ''),
                    link_text=row.get('link_text', ''),
                    link_type=row.get('link_type', ''),
                    status_code=int(row.get('status_code', 0)),
                    issue_type=row.get('issue_type', ''),
                    priority=row.get('priority', ''),
                    redirect_chain=row.get('redirect_chain') or None,
                    final_url=row.get('final_url') or None,
                    recommended_fix=row.get('recommended_fix', ''),
                ))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Report file not found")
    
    return ReportResponse(
        crawl_id=crawl_id,
        issues=issues,
        total=len(issues),
    )


@router.post("/validate-sitemap", response_model=ValidateSitemapResponse)
async def validate_sitemap(request: ValidateSitemapRequest):
    """Validate that a sitemap URL is accessible."""
    import requests
    
    try:
        response = requests.head(
            request.url,
            timeout=10,
            headers={"User-Agent": "LinkCanary/1.0"},
            allow_redirects=True,
        )
        
        if response.status_code != 200:
            return ValidateSitemapResponse(
                valid=False,
                error=f"HTTP {response.status_code}",
            )
        
        response = requests.get(
            request.url,
            timeout=15,
            headers={"User-Agent": "LinkCanary/1.0"},
        )
        
        from link_checker.sitemap import SitemapParser
        parser = SitemapParser()
        try:
            urls = parser.parse_sitemap(request.url)
            return ValidateSitemapResponse(
                valid=True,
                page_count=len(urls),
            )
        except Exception as e:
            return ValidateSitemapResponse(
                valid=False,
                error=f"Failed to parse sitemap: {str(e)}",
            )
        finally:
            parser.close()
    
    except requests.RequestException as e:
        return ValidateSitemapResponse(
            valid=False,
            error=str(e),
        )
