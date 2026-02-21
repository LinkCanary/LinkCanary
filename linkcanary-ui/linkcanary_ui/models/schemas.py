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


class BacklinkCheckRequest(BaseModel):
    """Request to check for backlinks."""
    target_url: str = Field(..., description="URL to check for backlinks to")
    sitemap_url: str = Field(..., description="Sitemap URL containing pages to check")
    user_agent: str = Field(default="LinkCanary/1.0", description="User agent for requests")
    timeout: int = Field(default=10, ge=5, le=60, description="Request timeout in seconds")


class BacklinkSource(BaseModel):
    """Single backlink source."""
    source_url: str
    found: bool
    link_text: Optional[str] = None
    error: Optional[str] = None


class BacklinkCheckResponse(BaseModel):
    """Response from backlink check."""
    target_url: str
    sitemap_url: str
    pages_checked: int
    backlinks_found: int
    sources: list[BacklinkSource]
    total_pages: int


class WebhookCreate(BaseModel):
    """Request to create a webhook."""
    name: str
    type: str = Field(description="Webhook type: slack, discord, or generic")
    url: str
    secret: Optional[str] = None
    enabled: bool = True
    trigger_events: list[str] = Field(
        default=["crawl_completed"],
        description="Events: crawl_completed, crawl_failed, issues_found"
    )
    filters: Optional[dict] = Field(
        default=None,
        description="Optional filters like {'min_issues': 5}"
    )


class WebhookUpdate(BaseModel):
    """Request to update a webhook."""
    name: Optional[str] = None
    url: Optional[str] = None
    secret: Optional[str] = None
    enabled: Optional[bool] = None
    trigger_events: Optional[list[str]] = None
    filters: Optional[dict] = None


class WebhookResponse(BaseModel):
    """Webhook response schema."""
    id: str
    name: str
    type: str
    url: str
    secret: Optional[str]
    enabled: bool
    trigger_events: list[str]
    filters: Optional[dict]
    created_at: Optional[datetime]
    last_triggered_at: Optional[datetime]
    last_trigger_status: Optional[str]
    trigger_count: int

    class Config:
        from_attributes = True


class WebhookListResponse(BaseModel):
    """List of webhooks response."""
    webhooks: list[WebhookResponse]
    total: int


class WebhookTestRequest(BaseModel):
    """Request to test a webhook."""
    webhook_id: Optional[str] = None
    event: str = "crawl_completed"


class WebhookPayload(BaseModel):
    """Webhook payload structure."""
    event: str
    crawl_id: str
    crawl_name: Optional[str] = None
    sitemap_url: str
    status: str
    summary: dict
    report_url: Optional[str] = None
    timestamp: str
