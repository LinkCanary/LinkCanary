"""Reports API endpoints."""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Crawl, CrawlStatus, get_db
from ..storage import get_storage

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{crawl_id}/download/csv")
async def download_csv(
    crawl_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Download report as CSV."""
    result = await db.execute(select(Crawl).where(Crawl.id == crawl_id))
    crawl = result.scalar_one_or_none()
    
    if not crawl:
        raise HTTPException(status_code=404, detail="Crawl not found")
    
    storage = get_storage()
    if not crawl.report_csv_path or not storage.exists(crawl.report_csv_path):
        raise HTTPException(status_code=404, detail="CSV report not available")
    
    filename = f"linkcanary_report_{crawl.name}_{crawl.created_at.strftime('%Y%m%d')}.csv"
    
    return FileResponse(
        storage.localize(crawl.report_csv_path),
        media_type="text/csv",
        filename=filename,
    )


@router.get("/{crawl_id}/download/html")
async def download_html(
    crawl_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Download report as HTML."""
    result = await db.execute(select(Crawl).where(Crawl.id == crawl_id))
    crawl = result.scalar_one_or_none()
    
    if not crawl:
        raise HTTPException(status_code=404, detail="Crawl not found")
    
    storage = get_storage()
    if not crawl.report_html_path or not storage.exists(crawl.report_html_path):
        if crawl.report_csv_path and storage.exists(crawl.report_csv_path):
            from link_checker.html_reporter import HTMLReportGenerator
            import tempfile

            local_csv = storage.localize(crawl.report_csv_path)
            fd, local_html = tempfile.mkstemp(suffix=".html")
            os.close(fd)
            reporter = HTMLReportGenerator()
            reporter.load_csv(local_csv)
            reporter.generate_html(local_html)

            html_key = f"{crawl_id}/report.html"
            storage.put_file(html_key, local_html)
            crawl.report_html_path = html_key
            await db.commit()
        else:
            raise HTTPException(status_code=404, detail="Report not available")
    
    filename = f"linkcanary_report_{crawl.name}_{crawl.created_at.strftime('%Y%m%d')}.html"
    
    return FileResponse(
        storage.localize(crawl.report_html_path),
        media_type="text/html",
        filename=filename,
    )
