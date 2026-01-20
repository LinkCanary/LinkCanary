"""Pydantic schemas for API requests/responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class CrawlSettings(BaseModel):
    """Crawl settings schema."""
    internal_only: bool = False
    external_only: bool = False
    skip_ok: bool = True
    expand_duplicates: bool = False
    include_subdomains: bool = False
    delay: float = Field(default=0.5, ge=0.1, le=5.0)
    timeout: int = Field(default=10, ge=5, le=60)
    max_pages: Optional[int] = Field(default=None, ge=1)
    since: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    user_agent: str = "LinkCanary/1.0"


class CrawlCreate(BaseModel):
    """Request to create a new crawl."""
    sitemap_url: str
    name: Optional[str] = None
    settings: CrawlSettings = Field(default_factory=CrawlSettings)


class CrawlIssues(BaseModel):
    """Issue counts."""
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    total: int = 0


class CrawlResponse(BaseModel):
    """Crawl response schema."""
    id: str
    name: str
    sitemap_url: str
    status: str
    settings: CrawlSettings
    created_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    pages_crawled: int
    total_pages: int
    links_checked: int
    issues: CrawlIssues
    error_message: Optional[str]
    report_csv_path: Optional[str]
    report_html_path: Optional[str]
    
    class Config:
        from_attributes = True


class CrawlListResponse(BaseModel):
    """List of crawls response."""
    crawls: list[CrawlResponse]
    total: int


class CrawlProgress(BaseModel):
    """Real-time crawl progress."""
    crawl_id: str
    status: str
    pages_crawled: int
    total_pages: int
    links_checked: int
    issues_found: int
    current_page: Optional[str]
    elapsed_seconds: float


class ValidateSitemapRequest(BaseModel):
    """Request to validate a sitemap URL."""
    url: str


class ValidateSitemapResponse(BaseModel):
    """Response from sitemap validation."""
    valid: bool
    page_count: Optional[int]
    error: Optional[str]


class StatsResponse(BaseModel):
    """Dashboard statistics."""
    total_crawls: int
    total_issues: int
    crawls_this_week: int
    issues_by_type: dict[str, int]


class ReportIssue(BaseModel):
    """Single issue in a report."""
    source_page: str
    occurrence_count: int
    example_pages: list[str]
    link_url: str
    link_text: str
    link_type: str
    status_code: int
    issue_type: str
    priority: str
    redirect_chain: Optional[str]
    final_url: Optional[str]
    recommended_fix: str


class ReportResponse(BaseModel):
    """Report data response."""
    crawl_id: str
    issues: list[ReportIssue]
    total: int


class SettingsSchema(BaseModel):
    """Application settings schema."""
    default_delay: float = 0.5
    default_timeout: int = 10
    default_skip_ok: bool = True
    default_internal_only: bool = False
    report_retention_days: int = 90
    max_storage_mb: int = 1000
