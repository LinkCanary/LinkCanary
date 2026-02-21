"""Webhook notification service."""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from sqlalchemy import select

from ..models import Webhook, WebhookEvent, WebhookType
from ..config import settings


class WebhookService:
    """Service for sending webhook notifications."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def build_payload(
        self,
        event: str,
        crawl_id: str,
        sitemap_url: str,
        status: str,
        summary: dict,
        crawl_name: Optional[str] = None,
        report_url: Optional[str] = None,
    ) -> dict:
        """Build the webhook payload."""
        return {
            "event": event,
            "crawl_id": crawl_id,
            "crawl_name": crawl_name,
            "sitemap_url": sitemap_url,
            "status": status,
            "summary": summary,
            "report_url": report_url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def format_slack_payload(self, payload: dict, webhook: Webhook) -> dict:
        """Format payload for Slack incoming webhook."""
        event = payload.get("event", "").replace("_", " ").title()
        status = payload.get("status", "")
        summary = payload.get("summary", {})
        issues = summary.get("issues", {})
        total_issues = sum(issues.values())

        color = "#36a64f" if status == "completed" else "#dc3545"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"LinkCanary: {event}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Crawl:*\n{payload.get('crawl_name', 'Unnamed')}"},
                    {"type": "mrkdwn", "text": f"*Status:*\n{status.title()}"},
                    {"type": "mrkdwn", "text": f"*Pages Crawled:*\n{summary.get('pages_crawled', 0)}"},
                    {"type": "mrkdwn", "text": f"*Links Checked:*\n{summary.get('links_checked', 0)}"},
                ]
            }
        ]

        if total_issues > 0:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Issues Found:* {total_issues} (Critical: {issues.get('critical', 0)}, High: {issues.get('high', 0)}, Medium: {issues.get('medium', 0)}, Low: {issues.get('low', 0)})"
                }
            })

        if payload.get("report_url"):
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Report"},
                        "url": payload["report_url"]
                    }
                ]
            })

        return {"attachments": [{"color": color, "blocks": blocks}]}

    def format_discord_payload(self, payload: dict, webhook: Webhook) -> dict:
        """Format payload for Discord webhook."""
        event = payload.get("event", "").replace("_", " ").title()
        status = payload.get("status", "")
        summary = payload.get("summary", {})
        issues = summary.get("issues", {})
        total_issues = sum(issues.values())

        color = 3066993 if status == "completed" else 15158332

        embed = {
            "title": f"LinkCanary: {event}",
            "url": payload.get("report_url"),
            "color": color,
            "timestamp": payload.get("timestamp"),
            "fields": [
                {"name": "Crawl", "value": payload.get("crawl_name", "Unnamed"), "inline": True},
                {"name": "Status", "value": status.title(), "inline": True},
                {"name": "Pages Crawled", "value": str(summary.get("pages_crawled", 0)), "inline": True},
                {"name": "Links Checked", "value": str(summary.get("links_checked", 0)), "inline": True},
            ],
            "footer": {"text": "LinkCanary"},
        }

        if total_issues > 0:
            embed["fields"].append({
                "name": "Issues Found",
                "value": f"{total_issues} (Critical: {issues.get('critical', 0)}, High: {issues.get('high', 0)}, Medium: {issues.get('medium', 0)}, Low: {issues.get('low', 0)})",
                "inline": False
            })

        return {"embeds": [embed]}

    def sign_payload(self, payload: dict, secret: str) -> str:
        """Generate HMAC signature for payload."""
        payload_str = json.dumps(payload, separators=(",", ":"))
        signature = hmac.new(
            secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    def send_webhook(
        self,
        webhook: Webhook,
        payload: dict,
    ) -> tuple[bool, Optional[str]]:
        """Send webhook notification. Returns (success, error_message)."""
        try:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "LinkCanary-Webhook/1.0",
            }

            if webhook.type == WebhookType.SLACK:
                body = self.format_slack_payload(payload, webhook)
            elif webhook.type == WebhookType.DISCORD:
                body = self.format_discord_payload(payload, webhook)
            else:
                body = payload

            if webhook.secret:
                headers["X-LinkCanary-Signature"] = self.sign_payload(body, webhook.secret)

            response = requests.post(
                webhook.url,
                json=body,
                headers=headers,
                timeout=self.timeout,
            )

            if response.status_code >= 200 and response.status_code < 300:
                return True, None
            else:
                return False, f"HTTP {response.status_code}: {response.text[:200]}"

        except requests.Timeout:
            return False, "Request timed out"
        except requests.RequestException as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def trigger_webhooks(
        self,
        session,
        event: str,
        crawl_id: str,
        sitemap_url: str,
        status: str,
        summary: dict,
        crawl_name: Optional[str] = None,
        report_url: Optional[str] = None,
    ) -> dict[str, tuple[bool, Optional[str]]]:
        """Trigger all applicable webhooks for an event."""
        results = {}
        issue_count = sum(summary.get("issues", {}).values())

        webhooks = session.execute(
            select(Webhook).where(Webhook.enabled == True)
        ).scalars().all()

        payload = self.build_payload(
            event=event,
            crawl_id=crawl_id,
            sitemap_url=sitemap_url,
            status=status,
            summary=summary,
            crawl_name=crawl_name,
            report_url=report_url,
        )

        for webhook in webhooks:
            if not webhook.should_trigger(event, issue_count):
                continue

            success, error = self.send_webhook(webhook, payload)
            results[webhook.id] = (success, error)

            webhook.last_triggered_at = datetime.utcnow()
            webhook.last_trigger_status = "success" if success else f"failed: {error}"
            webhook.trigger_count += 1

        session.commit()
        return results


webhook_service = WebhookService(timeout=getattr(settings, 'webhook_timeout', 10))
