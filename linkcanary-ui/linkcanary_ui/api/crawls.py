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
    CrawlTransparencyResponse,
    ReportIssue,
    ReportResponse,
    ShareResponse,
    ValidateSitemapRequest,
    ValidateSitemapResponse,
)
from ..storage import get_storage
from ..tasks.crawl_task import run_crawl_in_background

router = APIRouter(prefix="/api/crawls", tags=["crawls"])


def extract_domain(url: str) -> str:
    """Extract domain from URL for crawl name."""
    parsed = urlparse(url)
    return parsed.netloc or url


def normalize_sitemap_url(url: str) -> str:
    """Ensure URL points to sitemap.xml."""
    url = url.strip().rstrip('/')
    if not url.endswith('.xml'):
        if not url.endswith('/sitemap'):
            url = f"{url}/sitemap.xml"
        else:
            url = f"{url}.xml"
    return url


@router.post("", response_model=CrawlResponse)
async def create_crawl(
    request: CrawlCreate,
    db: AsyncSession = Depends(get_db),
):
    """Start a new crawl."""
    sitemap_url = normalize_sitemap_url(request.sitemap_url)
    name = request.name or extract_domain(sitemap_url)
    
    crawl = Crawl(
        name=name,
        sitemap_url=sitemap_url,
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
        with open(get_storage().localize(crawl.report_csv_path), newline='', encoding='utf-8') as f:
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
                    element_type=row.get('element_type', 'a'),
                    status_code=int(row.get('status_code', 0)),
                    issue_type=row.get('issue_type', ''),
                    priority=row.get('priority', ''),
                    redirect_chain=row.get('redirect_chain') or None,
                    final_url=row.get('final_url') or None,
                    recommended_fix=row.get('recommended_fix', ''),
                    response_time_ms=float(row['response_time_ms']) if row.get('response_time_ms') else None,
                    anchor_quality=row.get('anchor_quality', ''),
                ))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Report file not found")
    
    return ReportResponse(
        crawl_id=crawl_id,
        issues=issues,
        total=len(issues),
    )

@router.get("/{crawl_id}/transparency", response_model=CrawlTransparencyResponse)
async def get_transparency(
    crawl_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get crawl transparency summary — what was scanned and how."""
    result = await db.execute(select(Crawl).where(Crawl.id == crawl_id))
    crawl = result.scalar_one_or_none()

    if not crawl:
        raise HTTPException(status_code=404, detail="Crawl not found")

    status_dist: dict[str, int] = {}
    link_types: dict[str, int] = {"internal": 0, "external": 0}
    issue_types: dict[str, int] = {}
    response_times: list[float] = []

    if crawl.report_csv_path:
        try:
            with open(get_storage().localize(crawl.report_csv_path), newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get('status_code', '0')
                    status_dist[code] = status_dist.get(code, 0) + 1
                    lt = row.get('link_type', '')
                    if lt in link_types:
                        link_types[lt] += 1
                    it = row.get('issue_type', '')
                    if it:
                        issue_types[it] = issue_types.get(it, 0) + 1
                    rt = row.get('response_time_ms', '')
                    if rt:
                        try:
                            response_times.append(float(rt))
                        except ValueError:
                            pass
        except FileNotFoundError:
            pass

    page_cap = bool(crawl.max_pages and crawl.total_pages > crawl.pages_crawled)
    if crawl.internal_only:
        scope = "internal_only"
    elif crawl.external_only:
        scope = "external_only"
    else:
        scope = "all"

    skipped_reason = None
    if page_cap:
        skipped_reason = f"Page limit of {crawl.max_pages} applied — {crawl.total_pages - crawl.pages_crawled} pages not crawled"

    return CrawlTransparencyResponse(
        crawl_id=crawl_id,
        sitemap_url=crawl.sitemap_url,
        pages_in_sitemap=crawl.total_pages,
        pages_crawled=crawl.pages_crawled,
        page_cap_applied=page_cap,
        links_checked=crawl.links_checked,
        scope=scope,
        robots_txt_respected=True,
        delay_seconds=crawl.delay,
        timeout_seconds=crawl.timeout,
        user_agent=crawl.user_agent,
        duration_seconds=crawl.duration_seconds,
        started_at=crawl.started_at,
        completed_at=crawl.completed_at,
        status_code_distribution=status_dist,
        avg_response_time_ms=round(sum(response_times) / len(response_times), 1) if response_times else None,
        link_type_breakdown=link_types,
        issue_type_breakdown=issue_types,
        skipped_reason=skipped_reason,
    )


@router.post("/{crawl_id}/share", response_model=ShareResponse)
async def share_crawl(
    crawl_id: str,
    db: AsyncSession = Depends(get_db),
    request: None = None,
):
    """Generate a shareable public link for a crawl report."""
    import uuid as uuid_lib
    from fastapi import Request

    result = await db.execute(select(Crawl).where(Crawl.id == crawl_id))
    crawl = result.scalar_one_or_none()

    if not crawl:
        raise HTTPException(status_code=404, detail="Crawl not found")

    if crawl.status not in (CrawlStatus.COMPLETED,):
        raise HTTPException(status_code=400, detail="Crawl must be completed before sharing")

    if not crawl.share_token:
        crawl.share_token = str(uuid_lib.uuid4())
        await db.commit()

    return ShareResponse(
        share_token=crawl.share_token,
        share_url=f"/share/{crawl.share_token}",
    )


@router.get("/shared/{token}", response_model=ReportResponse)
async def get_shared_report(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — retrieve a report by share token (no auth required)."""
    result = await db.execute(select(Crawl).where(Crawl.share_token == token))
    crawl = result.scalar_one_or_none()

    if not crawl:
        raise HTTPException(status_code=404, detail="Shared report not found")

    if not crawl.report_csv_path:
        raise HTTPException(status_code=404, detail="Report not available")

    issues = []
    try:
        with open(get_storage().localize(crawl.report_csv_path), newline='', encoding='utf-8') as f:
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
                    element_type=row.get('element_type', 'a'),
                    status_code=int(row.get('status_code', 0)),
                    issue_type=row.get('issue_type', ''),
                    priority=row.get('priority', ''),
                    redirect_chain=row.get('redirect_chain') or None,
                    final_url=row.get('final_url') or None,
                    recommended_fix=row.get('recommended_fix', ''),
                    response_time_ms=float(row['response_time_ms']) if row.get('response_time_ms') else None,
                    anchor_quality=row.get('anchor_quality', ''),
                ))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Report file not found")

    return ReportResponse(crawl_id=crawl.id, issues=issues, total=len(issues))


@router.post("/validate-sitemap", response_model=ValidateSitemapResponse)
async def validate_sitemap(request: ValidateSitemapRequest):
    """Validate that a sitemap URL is accessible."""
    import requests
    
    url = normalize_sitemap_url(request.url)
    
    try:
        response = requests.head(
            url,
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
            url,
            timeout=15,
            headers={"User-Agent": "LinkCanary/1.0"},
        )
        
        from link_checker.sitemap import SitemapParser
        parser = SitemapParser()
        try:
            urls = parser.parse_sitemap(url)
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
