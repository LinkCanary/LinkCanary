"""Webhook model."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class WebhookType(str, enum.Enum):
    """Webhook type enum."""
    SLACK = "slack"
    DISCORD = "discord"
    GENERIC = "generic"
    JIRA = "jira"
    ASANA = "asana"


class WebhookEvent(str, enum.Enum):
    """Webhook trigger events."""
    CRAWL_COMPLETED = "crawl_completed"
    CRAWL_FAILED = "crawl_failed"
    ISSUES_FOUND = "issues_found"


class Webhook(Base):
    """Webhook configuration model."""

    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[WebhookType] = mapped_column(
        Enum(WebhookType),
        default=WebhookType.GENERIC,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    trigger_events: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default="crawl_completed,crawl_failed",
    )
    filters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Jira configuration
    jira_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    jira_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    jira_api_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    jira_project_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    jira_issue_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="Task")

    # Asana configuration
    asana_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    asana_workspace_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    asana_project_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    last_trigger_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    trigger_count: Mapped[int] = mapped_column(default=0)

    @property
    def events_list(self) -> list[str]:
        """Get trigger events as a list."""
        if not self.trigger_events:
            return []
        return [e.strip() for e in self.trigger_events.split(",") if e.strip()]

    def should_trigger(self, event: str, issue_count: int = 0) -> bool:
        """Check if webhook should trigger for given event."""
        if not self.enabled:
            return False
        if event not in self.events_list:
            return False
        if self.filters and "min_issues" in self.filters:
            if issue_count < self.filters["min_issues"]:
                return False
        return True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "url": self.url,
            "secret": "***" if self.secret else None,
            "enabled": self.enabled,
            "trigger_events": self.events_list,
            "filters": self.filters,
            "jira_url": self.jira_url,
            "jira_email": self.jira_email,
            "jira_api_token": "***" if self.jira_api_token else None,
            "jira_project_key": self.jira_project_key,
            "jira_issue_type": self.jira_issue_type,
            "asana_token": "***" if self.asana_token else None,
            "asana_workspace_id": self.asana_workspace_id,
            "asana_project_id": self.asana_project_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            "last_trigger_status": self.last_trigger_status,
            "trigger_count": self.trigger_count,
        }
