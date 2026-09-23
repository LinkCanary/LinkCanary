"""Crawl API endpoints."""

import csv
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps.auth import RequestContext, get_current_user
from ..deps.usage import check_crawl_allowed, increment_usage
from ..models import Crawl, CrawlStatus, get_db
from ..models.schemas import (
    CrawlCreate,
    CrawlListResponse,
    CrawlResponse,
    CrawlTransparencyResponse,
    DiffCounts,
    DiffResponse,
    DiffSection,
    ReportIssue,
    ReportResponse,
    ShareResponse,
    ValidateSitemapRequest,
    ValidateSitemapResponse,
)
from ..services.diff import diff_issues
from ..services.projects import resolve_or_create_project
from ..services.reports import load_issues_from_path
from ..storage import get_storage
from ..tasks.crawl_task import run_crawl_in_background

router = APIRouter(prefix="/api/crawls", tags=["crawls"])


async def _get_org_crawl(db: AsyncSession, crawl_id: str, org_id: str) -> Crawl:
    """Fetch a crawl scoped to the org, or 404 (don't leak existence)."""
    result = await db.execute(
        select(Crawl).where(Crawl.id == crawl_id, Crawl.org_id == org_id)
    )
    crawl = result.scalar_one_or_none()
    if not crawl:
        raise HTTPException(status_code=404, detail="Crawl not found")
    return crawl


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
    ctx: RequestContext = Depends(get_current_user),
):
    """Start a new crawl. Enforces plan limits before proceeding."""
    await check_crawl_allowed(ctx.org, request.settings.max_pages, db)

    sitemap_url = normalize_sitemap_url(request.sitemap_url)
    name = request.name or extract_domain(sitemap_url)

    project = await resolve_or_create_project(db, ctx.org_id, sitemap_url)

    crawl = Crawl(
        name=name,
        sitemap_url=sitemap_url,
        org_id=ctx.org_id,
        project_id=project.id,
        status=CrawlStatus.PENDING,
        internal_only=request.settings.internal_only,
        external_only=request.settings.external_only,
        skip_ok=request.settings.skip_ok,
        expand_duplicates=request.settings.expand_duplicates,
        include_subdomains=request.settings.include_subdomains,
        check_core_web_vitals=request.settings.check_core_web_vitals,
        delay=request.settings.delay,
        timeout=request.settings.timeout,
        max_pages=request.settings.max_pages,
        since_date=request.settings.since,
        user_agent=request.settings.user_agent,
    )

    db.add(crawl)
    await db.commit()
    await db.refresh(crawl)

    await increment_usage(ctx.org_id, "crawls", 1, db)
    run_crawl_in_background(crawl.id)

    return CrawlResponse(**crawl.to_dict())


@router.get("", response_model=CrawlListResponse)
async def list_crawls(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_user),
):
    """List crawls scoped to the authenticated org."""
    query = select(Crawl).where(Crawl.org_id == ctx.org_id).order_by(desc(Crawl.created_at))
    
    if status:
        try:
            status_enum = CrawlStatus(status)
            query = query.where(Crawl.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if project_id:
        query = query.where(Crawl.project_id == project_id)
    
    count_result = await db.execute(select(Crawl).where(Crawl.org_id == ctx.org_id))
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
    ctx: RequestContext = Depends(get_current_user),
):
    """Get crawl details."""
    crawl = await _get_org_crawl(db, crawl_id, ctx.org_id)
    return CrawlResponse(**crawl.to_dict())


@router.delete("/{crawl_id}")
async def delete_crawl(
    crawl_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_user),
):
    """Delete a crawl and its reports."""
    crawl = await _get_org_crawl(db, crawl_id, ctx.org_id)
    
    await db.delete(crawl)
    await db.commit()
    
    return {"message": "Crawl deleted"}


@router.post("/{crawl_id}/stop")
async def stop_crawl(
    crawl_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_user),
):
    """Stop a running crawl."""
    crawl = await _get_org_crawl(db, crawl_id, ctx.org_id)
    
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
    ctx: RequestContext = Depends(get_current_user),
):
    """Re-run a crawl with the same settings. Enforces plan limits."""
    original = await _get_org_crawl(db, crawl_id, ctx.org_id)

    await check_crawl_allowed(ctx.org, original.max_pages, db)

    crawl = Crawl(
        name=f"{original.name} (re-run)",
        sitemap_url=original.sitemap_url,
        org_id=ctx.org_id,
        project_id=original.project_id,
        status=CrawlStatus.PENDING,
        internal_only=original.internal_only,
        external_only=original.external_only,
        skip_ok=original.skip_ok,
        expand_duplicates=original.expand_duplicates,
        include_subdomains=original.include_subdomains,
        check_core_web_vitals=original.check_core_web_vitals,
        delay=original.delay,
        timeout=original.timeout,
        max_pages=original.max_pages,
        since_date=original.since_date,
        user_agent=original.user_agent,
    )

    db.add(crawl)
    await db.commit()
    await db.refresh(crawl)

    await increment_usage(ctx.org_id, "crawls", 1, db)
    run_crawl_in_background(crawl.id)

    return CrawlResponse(**crawl.to_dict())


@router.get("/{crawl_id}/report", response_model=ReportResponse)
async def get_report(
    crawl_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_user),
):
    """Get report data as JSON."""
    crawl = await _get_org_crawl(db, crawl_id, ctx.org_id)
    
    if not crawl.report_csv_path:
        raise HTTPException(status_code=404, detail="Report not available")
    
    try:
        issues = load_issues_from_path(get_storage().localize(crawl.report_csv_path))
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
    ctx: RequestContext = Depends(get_current_user),
):
    """Get crawl transparency summary — what was scanned and how."""
    crawl = await _get_org_crawl(db, crawl_id, ctx.org_id)

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
    ctx: RequestContext = Depends(get_current_user),
    request: None = None,
):
    """Generate a shareable public link for a crawl report."""
    import uuid as uuid_lib
    from fastapi import Request

    crawl = await _get_org_crawl(db, crawl_id, ctx.org_id)

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

    try:
        issues = load_issues_from_path(get_storage().localize(crawl.report_csv_path))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Report file not found")

    return ReportResponse(crawl_id=crawl.id, issues=issues, total=len(issues))


async def _find_prior_crawl(
    db: AsyncSession, crawl: Crawl, org_id: str
) -> Optional[Crawl]:
    """Return the most recent completed prior crawl in the same project (or site)."""
    query = (
        select(Crawl)
        .where(
            Crawl.org_id == org_id,
            Crawl.status == CrawlStatus.COMPLETED,
            Crawl.id != crawl.id,
            Crawl.created_at < crawl.created_at,
        )
        .order_by(desc(Crawl.created_at))
        .limit(1)
    )
    if crawl.project_id:
        query = query.where(Crawl.project_id == crawl.project_id)
    else:
        query = query.where(Crawl.sitemap_url == crawl.sitemap_url)
    result = await db.execute(query)
    return result.scalar_one_or_none()


def _load_crawl_issues(crawl: Crawl) -> list[ReportIssue]:
    """Load a crawl's per-issue rows, tolerating a missing report."""
    if not crawl.report_csv_path:
        return []
    try:
        return load_issues_from_path(get_storage().localize(crawl.report_csv_path))
    except FileNotFoundError:
        return []


def _to_section(bucket) -> DiffSection:
    return DiffSection(
        counts=DiffCounts(**bucket.counts()),
        issues=bucket.by_priority(),
    )


@router.get("/{crawl_id}/diff", response_model=DiffResponse)
async def diff_crawl(
    crawl_id: str,
    against: Optional[str] = Query(
        None, description="Crawl ID to diff against, or 'latest' (default) for the prior crawl"
    ),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_user),
):
    """Diff this crawl against a prior one: new / resolved / persistent issues."""
    crawl = await _get_org_crawl(db, crawl_id, ctx.org_id)

    if against and against != "latest":
        prior = await _get_org_crawl(db, against, ctx.org_id)
    else:
        prior = await _find_prior_crawl(db, crawl, ctx.org_id)

    if prior is None:
        raise HTTPException(status_code=404, detail="No prior crawl to diff against")

    diff = diff_issues(_load_crawl_issues(crawl), _load_crawl_issues(prior))

    return DiffResponse(
        crawl_id=crawl.id,
        against_crawl_id=prior.id,
        new=_to_section(diff.new),
        resolved=_to_section(diff.resolved),
        persistent=_to_section(diff.persistent),
    )


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
