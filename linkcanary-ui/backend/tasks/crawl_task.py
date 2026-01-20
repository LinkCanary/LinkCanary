"""Background crawl task."""

import os
from datetime import datetime

from celery import current_task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from link_checker.checker import LinkChecker
from link_checker.crawler import PageCrawler
from link_checker.html_reporter import HTMLReportGenerator
from link_checker.reporter import ReportGenerator
from link_checker.sitemap import SitemapParser

from ..config import settings
from ..models import Crawl, CrawlStatus
from ..models.database import Base
from .celery_app import celery_app

sync_db_url = settings.db_url.replace("+aiosqlite", "")
sync_engine = create_engine(sync_db_url)


def get_sync_session():
    """Get synchronous database session for Celery tasks."""
    return Session(sync_engine)


@celery_app.task(bind=True)
def run_crawl_task(self, crawl_id: str):
    """Execute a crawl in the background."""
    session = get_sync_session()
    
    try:
        crawl = session.execute(
            select(Crawl).where(Crawl.id == crawl_id)
        ).scalar_one_or_none()
        
        if not crawl:
            return {"error": "Crawl not found"}
        
        crawl.status = CrawlStatus.IN_PROGRESS
        crawl.started_at = datetime.utcnow()
        session.commit()
        
        crawl_dir = settings.crawls_dir / crawl_id
        crawl_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = crawl_dir / "report.csv"
        html_path = crawl_dir / "report.html"
        
        sitemap_parser = SitemapParser(
            user_agent=crawl.user_agent,
            timeout=crawl.timeout,
        )
        
        try:
            since = None
            if crawl.since_date:
                since = datetime.strptime(crawl.since_date, '%Y-%m-%d')
            
            page_urls = sitemap_parser.parse_sitemap(crawl.sitemap_url, since=since)
        except Exception as e:
            crawl.status = CrawlStatus.FAILED
            crawl.error_message = f"Failed to parse sitemap: {str(e)}"
            crawl.completed_at = datetime.utcnow()
            session.commit()
            return {"error": crawl.error_message}
        finally:
            sitemap_parser.close()
        
        if not page_urls:
            crawl.status = CrawlStatus.FAILED
            crawl.error_message = "No pages found in sitemap"
            crawl.completed_at = datetime.utcnow()
            session.commit()
            return {"error": crawl.error_message}
        
        if crawl.max_pages:
            page_urls = page_urls[:crawl.max_pages]
        
        crawl.total_pages = len(page_urls)
        session.commit()
        
        crawler = PageCrawler(
            base_url=crawl.sitemap_url,
            user_agent=crawl.user_agent,
            timeout=crawl.timeout,
            delay=crawl.delay,
            include_subdomains=crawl.include_subdomains,
        )
        
        all_links = []
        
        try:
            for i, url in enumerate(page_urls):
                crawl_check = session.execute(
                    select(Crawl).where(Crawl.id == crawl_id)
                ).scalar_one_or_none()
                
                if crawl_check and crawl_check.status == CrawlStatus.CANCELLED:
                    break
                
                links = crawler.crawl_page(url)
                all_links.extend(links)
                
                crawl.pages_crawled = i + 1
                session.commit()
        finally:
            crawler.close()
        
        crawl_check = session.execute(
            select(Crawl).where(Crawl.id == crawl_id)
        ).scalar_one_or_none()
        
        if crawl_check and crawl_check.status == CrawlStatus.CANCELLED:
            return {"status": "cancelled"}
        
        if crawl.internal_only:
            all_links = [link for link in all_links if link.is_internal]
        elif crawl.external_only:
            all_links = [link for link in all_links if not link.is_internal]
        
        unique_urls = list(set(link.link_url for link in all_links))
        
        if not unique_urls:
            crawl.status = CrawlStatus.COMPLETED
            crawl.completed_at = datetime.utcnow()
            session.commit()
            return {"status": "completed", "links_checked": 0}
        
        checker = LinkChecker(
            user_agent=crawl.user_agent,
            timeout=crawl.timeout,
            delay=crawl.delay / 2,
        )
        
        link_statuses = {}
        
        try:
            for i, url in enumerate(unique_urls):
                crawl_check = session.execute(
                    select(Crawl).where(Crawl.id == crawl_id)
                ).scalar_one_or_none()
                
                if crawl_check and crawl_check.status == CrawlStatus.CANCELLED:
                    break
                
                status = checker.check_link(url)
                link_statuses[url] = status
                
                crawl.links_checked = i + 1
                session.commit()
        finally:
            checker.close()
        
        crawl_check = session.execute(
            select(Crawl).where(Crawl.id == crawl_id)
        ).scalar_one_or_none()
        
        if crawl_check and crawl_check.status == CrawlStatus.CANCELLED:
            return {"status": "cancelled"}
        
        reporter = ReportGenerator(
            expand_duplicates=crawl.expand_duplicates,
            skip_ok=crawl.skip_ok,
        )
        
        df = reporter.generate_report(all_links, link_statuses)
        reporter.save_report(df, str(csv_path))
        
        summary = reporter.get_summary(df)
        
        html_reporter = HTMLReportGenerator()
        html_reporter.load_csv(str(csv_path))
        html_reporter.generate_html(str(html_path))
        
        crawl.report_csv_path = str(csv_path)
        crawl.report_html_path = str(html_path)
        crawl.issues_critical = summary.get('critical', 0)
        crawl.issues_high = summary.get('high', 0)
        crawl.issues_medium = summary.get('medium', 0)
        crawl.issues_low = summary.get('low', 0)
        crawl.status = CrawlStatus.COMPLETED
        crawl.completed_at = datetime.utcnow()
        session.commit()
        
        return {
            "status": "completed",
            "pages_crawled": crawl.pages_crawled,
            "links_checked": crawl.links_checked,
            "issues": crawl.total_issues,
        }
    
    except Exception as e:
        crawl = session.execute(
            select(Crawl).where(Crawl.id == crawl_id)
        ).scalar_one_or_none()
        
        if crawl:
            crawl.status = CrawlStatus.FAILED
            crawl.error_message = str(e)
            crawl.completed_at = datetime.utcnow()
            session.commit()
        
        raise
    
    finally:
        session.close()
