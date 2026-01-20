"""Crawl model."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class CrawlStatus(str, enum.Enum):
    """Crawl status enum."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Crawl(Base):
    """Crawl database model."""
    
    __tablename__ = "crawls"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sitemap_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CrawlStatus] = mapped_column(
        Enum(CrawlStatus),
        default=CrawlStatus.PENDING,
        nullable=False,
    )
    
    internal_only: Mapped[bool] = mapped_column(default=False)
    external_only: Mapped[bool] = mapped_column(default=False)
    skip_ok: Mapped[bool] = mapped_column(default=True)
    expand_duplicates: Mapped[bool] = mapped_column(default=False)
    include_subdomains: Mapped[bool] = mapped_column(default=False)
    delay: Mapped[float] = mapped_column(Float, default=0.5)
    timeout: Mapped[int] = mapped_column(Integer, default=10)
    max_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    since_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    user_agent: Mapped[str] = mapped_column(String(255), default="LinkCanary/1.0")
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    links_checked: Mapped[int] = mapped_column(Integer, default=0)
    
    issues_critical: Mapped[int] = mapped_column(Integer, default=0)
    issues_high: Mapped[int] = mapped_column(Integer, default=0)
    issues_medium: Mapped[int] = mapped_column(Integer, default=0)
    issues_low: Mapped[int] = mapped_column(Integer, default=0)
    
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    report_csv_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_html_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate crawl duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def total_issues(self) -> int:
        """Get total issue count."""
        return (
            self.issues_critical +
            self.issues_high +
            self.issues_medium +
            self.issues_low
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "sitemap_url": self.sitemap_url,
            "status": self.status.value,
            "settings": {
                "internal_only": self.internal_only,
                "external_only": self.external_only,
                "skip_ok": self.skip_ok,
                "expand_duplicates": self.expand_duplicates,
                "include_subdomains": self.include_subdomains,
                "delay": self.delay,
                "timeout": self.timeout,
                "max_pages": self.max_pages,
                "since": self.since_date,
                "user_agent": self.user_agent,
            },
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "pages_crawled": self.pages_crawled,
            "total_pages": self.total_pages,
            "links_checked": self.links_checked,
            "issues": {
                "critical": self.issues_critical,
                "high": self.issues_high,
                "medium": self.issues_medium,
                "low": self.issues_low,
                "total": self.total_issues,
            },
            "error_message": self.error_message,
            "report_csv_path": self.report_csv_path,
            "report_html_path": self.report_html_path,
        }
