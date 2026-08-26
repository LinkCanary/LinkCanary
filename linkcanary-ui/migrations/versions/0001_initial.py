"""Initial baseline schema (crawls, webhooks).

Explicitly creates the two tables that existed when Alembic was introduced, so
later migrations (0002 auth tables, 0003 projects + crawl scoping) can build on
a stable baseline. Previously this used ``Base.metadata.create_all``, which
reflects the *current* model and therefore collides with later migrations.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crawls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sitemap_url", sa.Text, nullable=False),
        sa.Column("status", sa.Enum("pending", "in_progress", "completed", "failed", "cancelled", name="crawlstatus"), nullable=False, server_default="pending"),
        sa.Column("internal_only", sa.Boolean, server_default="false"),
        sa.Column("external_only", sa.Boolean, server_default="false"),
        sa.Column("skip_ok", sa.Boolean, server_default="true"),
        sa.Column("expand_duplicates", sa.Boolean, server_default="false"),
        sa.Column("include_subdomains", sa.Boolean, server_default="false"),
        sa.Column("delay", sa.Float, server_default="0.5"),
        sa.Column("timeout", sa.Integer, server_default="10"),
        sa.Column("max_pages", sa.Integer, nullable=True),
        sa.Column("since_date", sa.String(10), nullable=True),
        sa.Column("user_agent", sa.String(255), server_default="LinkCanary/1.0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("pages_crawled", sa.Integer, server_default="0"),
        sa.Column("total_pages", sa.Integer, server_default="0"),
        sa.Column("links_checked", sa.Integer, server_default="0"),
        sa.Column("issues_critical", sa.Integer, server_default="0"),
        sa.Column("issues_high", sa.Integer, server_default="0"),
        sa.Column("issues_medium", sa.Integer, server_default="0"),
        sa.Column("issues_low", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("report_csv_path", sa.Text, nullable=True),
        sa.Column("report_html_path", sa.Text, nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("share_token", sa.String(36), nullable=True, unique=True),
    )

    op.create_table(
        "webhooks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.Enum("slack", "discord", "generic", "jira", "asana", "ntfy", "gotify", name="webhooktype"), nullable=False, server_default="generic"),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("secret", sa.String(255), nullable=True),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("trigger_events", sa.Text, nullable=True, server_default="crawl_completed,crawl_failed"),
        sa.Column("filters", sa.JSON, nullable=True),
        sa.Column("jira_url", sa.Text, nullable=True),
        sa.Column("jira_email", sa.String(255), nullable=True),
        sa.Column("jira_api_token", sa.String(255), nullable=True),
        sa.Column("jira_project_key", sa.String(50), nullable=True),
        sa.Column("jira_issue_type", sa.String(50), nullable=True, server_default="Task"),
        sa.Column("asana_token", sa.String(255), nullable=True),
        sa.Column("asana_workspace_id", sa.String(50), nullable=True),
        sa.Column("asana_project_id", sa.String(50), nullable=True),
        sa.Column("ntfy_server", sa.Text, nullable=True, server_default="https://ntfy.sh"),
        sa.Column("ntfy_topic", sa.String(255), nullable=True),
        sa.Column("ntfy_token", sa.String(255), nullable=True),
        sa.Column("ntfy_priority", sa.String(20), nullable=True, server_default="default"),
        sa.Column("gotify_url", sa.Text, nullable=True),
        sa.Column("gotify_token", sa.String(255), nullable=True),
        sa.Column("gotify_priority", sa.Integer, server_default="5"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("last_triggered_at", sa.DateTime, nullable=True),
        sa.Column("last_trigger_status", sa.String(50), nullable=True),
        sa.Column("trigger_count", sa.Integer, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("webhooks")
    op.drop_table("crawls")
    op.execute("DROP TYPE IF EXISTS webhooktype")
    op.execute("DROP TYPE IF EXISTS crawlstatus")
