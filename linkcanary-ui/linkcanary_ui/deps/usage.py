"""Usage enforcement — check plan limits before starting a crawl."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.auth import Organization, Plan, UsageCounter

PLAN_LIMITS = {
    Plan.HATCHLING: {"crawls_per_month": 5, "max_pages_per_crawl": 500},
    Plan.SONGBIRD: {"crawls_per_month": 50, "max_pages_per_crawl": 5000},
    Plan.FLOCK: {"crawls_per_month": None, "max_pages_per_crawl": 50000},
}


async def check_crawl_allowed(
    org: Organization,
    estimated_pages: int | None,
    db: AsyncSession,
) -> None:
    """Raise 402 if the org has exceeded its crawl or page limits."""
    limits = PLAN_LIMITS[org.plan]
    period = datetime.utcnow().strftime("%Y-%m")

    # Check crawl count
    crawl_limit = limits["crawls_per_month"]
    if crawl_limit is not None:
        result = await db.execute(
            select(UsageCounter).where(
                UsageCounter.org_id == org.id,
                UsageCounter.period == period,
                UsageCounter.metric == "crawls",
            )
        )
        counter = result.scalar_one_or_none()
        current = counter.count if counter else 0
        if current >= crawl_limit:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "usage_limit_exceeded",
                    "metric": "crawls",
                    "limit": crawl_limit,
                    "current": current,
                    "plan": org.plan.value,
                    "message": f"You've used all {crawl_limit} crawls this month. Upgrade for more.",
                },
            )

    # Check page limit for this crawl
    page_limit = limits["max_pages_per_crawl"]
    if estimated_pages is not None and page_limit is not None and estimated_pages > page_limit:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "page_limit_exceeded",
                "metric": "pages",
                "limit": page_limit,
                "estimated": estimated_pages,
                "plan": org.plan.value,
                "message": f"This site has ~{estimated_pages} pages. Your plan supports {page_limit} per crawl.",
            },
        )


async def increment_usage(
    org_id: str,
    metric: str,
    amount: int,
    db: AsyncSession,
) -> None:
    """Increment a usage counter for the current billing period."""
    period = datetime.utcnow().strftime("%Y-%m")
    result = await db.execute(
        select(UsageCounter).where(
            UsageCounter.org_id == org_id,
            UsageCounter.period == period,
            UsageCounter.metric == metric,
        )
    )
    counter = result.scalar_one_or_none()
    if counter:
        counter.count += amount
    else:
        counter = UsageCounter(org_id=org_id, period=period, metric=metric, count=amount)
        db.add(counter)
    await db.commit()
