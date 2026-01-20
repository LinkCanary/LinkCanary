"""Statistics API endpoints."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Crawl, CrawlStatus, get_db
from ..models.schemas import StatsResponse

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics."""
    result = await db.execute(select(Crawl))
    crawls = result.scalars().all()
    
    total_crawls = len(crawls)
    total_issues = sum(c.total_issues for c in crawls)
    
    week_ago = datetime.utcnow() - timedelta(days=7)
    crawls_this_week = sum(1 for c in crawls if c.created_at >= week_ago)
    
    issues_by_type = {
        "critical": sum(c.issues_critical for c in crawls),
        "high": sum(c.issues_high for c in crawls),
        "medium": sum(c.issues_medium for c in crawls),
        "low": sum(c.issues_low for c in crawls),
    }
    
    return StatsResponse(
        total_crawls=total_crawls,
        total_issues=total_issues,
        crawls_this_week=crawls_this_week,
        issues_by_type=issues_by_type,
    )
