"""Standalone Google tool endpoints: Core Web Vitals + Search Console.

These expose the ``link_checker.core_web_vitals`` and ``link_checker.gsc``
clients as authenticated HTTP tools. GSC auth currently uses a configured
access token (``google_access_token``) and will be swapped to the Better Auth
OAuth token source once that plumbing lands.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from link_checker.core_web_vitals import (
    PageSpeedInsightsClient,
    generate_cwv_findings,
)
from link_checker.gsc import SearchConsoleClient, detect_declining_pages

from ..config import settings
from ..deps.auth import RequestContext, get_current_user

router = APIRouter(prefix="/api/tools", tags=["tools"])


class CoreWebVitalsRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, max_length=20)


class SearchAnalyticsRequest(BaseModel):
    site_url: str
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    dimensions: list[str] = Field(default=["query"])
    row_limit: int = Field(default=100, ge=1, le=25000)


class DecliningPagesRequest(BaseModel):
    site_url: str
    current_start: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    current_end: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    previous_start: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    previous_end: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    click_drop_pct: float = Field(default=30.0, ge=0.0, le=100.0)
    min_clicks: int = Field(default=10, ge=0)


@router.post("/core-web-vitals")
async def core_web_vitals(
    request: CoreWebVitalsRequest,
    ctx: RequestContext = Depends(get_current_user),
):
    """Fetch Core Web Vitals (LCP/INP/CLS) for a set of URLs."""
    if not settings.google_api_key:
        raise HTTPException(status_code=400, detail="GOOGLE_API_KEY is not configured")

    client = PageSpeedInsightsClient(settings.google_api_key)
    try:
        results = [client.core_web_vitals(url) for url in request.urls]
    finally:
        client.close()

    findings = generate_cwv_findings(results)
    return {
        "results": [
            {
                "url": r.url,
                "lcp_ms": r.lcp_ms,
                "inp_ms": r.inp_ms,
                "cls": r.cls,
                "source": r.source,
                "error": r.error,
            }
            for r in results
        ],
        "findings": [
            {
                "link_url": f.link_url,
                "issue_type": f.issue_type,
                "priority": f.priority,
                "recommended_fix": f.recommended_fix,
            }
            for f in findings
        ],
    }


@router.post("/gsc/search-analytics")
async def gsc_search_analytics(
    request: SearchAnalyticsRequest,
    ctx: RequestContext = Depends(get_current_user),
):
    """Run a Google Search Console search-analytics query."""
    client = _gsc_client()
    try:
        rows = client.search_analytics(
            request.site_url,
            request.start_date,
            request.end_date,
            dimensions=request.dimensions,
            row_limit=request.row_limit,
        )
    finally:
        client.close()
    return {"rows": rows}


@router.post("/gsc/declining-pages")
async def gsc_declining_pages(
    request: DecliningPagesRequest,
    ctx: RequestContext = Depends(get_current_user),
):
    """Flag pages whose clicks are declining (outdated-content signal)."""
    client = _gsc_client()
    try:
        current = client.top_pages(request.site_url, request.current_start, request.current_end)
        previous = client.top_pages(request.site_url, request.previous_start, request.previous_end)
    finally:
        client.close()

    declining = detect_declining_pages(
        current, previous,
        click_drop_pct=request.click_drop_pct,
        min_clicks=request.min_clicks,
    )
    return {
        "declining_pages": [
            {
                "page": page,
                "current": current.get(page),
                "previous": previous.get(page),
            }
            for page in declining
        ]
    }


def _gsc_client() -> SearchConsoleClient:
    if not settings.google_access_token:
        raise HTTPException(status_code=400, detail="google_access_token is not configured")
    return SearchConsoleClient(lambda: settings.google_access_token)
