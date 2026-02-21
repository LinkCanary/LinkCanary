"""Webhook API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Webhook, WebhookType, WebhookEvent, get_db
from ..models.schemas import (
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookListResponse,
    WebhookTestRequest,
)
from ..services.webhooks import webhook_service

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def validate_webhook_type(webhook_type: str) -> WebhookType:
    """Validate and convert webhook type string."""
    try:
        return WebhookType(webhook_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid webhook type: {webhook_type}. Must be one of: slack, discord, generic, jira, asana"
        )


def validate_events(events: list[str]) -> list[str]:
    """Validate trigger events."""
    valid_events = [e.value for e in WebhookEvent]
    for event in events:
        if event not in valid_events:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid event: {event}. Must be one of: {', '.join(valid_events)}"
            )
    return events


@router.post("", response_model=WebhookResponse)
async def create_webhook(
    request: WebhookCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new webhook."""
    webhook_type = validate_webhook_type(request.type)
    events = validate_events(request.trigger_events)

    webhook = Webhook(
        name=request.name,
        type=webhook_type,
        url=request.url,
        secret=request.secret,
        enabled=request.enabled,
        trigger_events=",".join(events),
        filters=request.filters,
        # Jira configuration
        jira_url=request.jira_url,
        jira_email=request.jira_email,
        jira_api_token=request.jira_api_token,
        jira_project_key=request.jira_project_key,
        jira_issue_type=request.jira_issue_type,
        # Asana configuration
        asana_token=request.asana_token,
        asana_workspace_id=request.asana_workspace_id,
        asana_project_id=request.asana_project_id,
    )

    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    return WebhookResponse(**webhook.to_dict())


@router.get("", response_model=WebhookListResponse)
async def list_webhooks(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    enabled: Optional[bool] = None,
    type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all webhooks."""
    query = select(Webhook).order_by(desc(Webhook.created_at))

    if enabled is not None:
        query = query.where(Webhook.enabled == enabled)

    if type:
        try:
            webhook_type = WebhookType(type.lower())
            query = query.where(Webhook.type == webhook_type)
        except ValueError:
            pass

    count_result = await db.execute(select(Webhook))
    total = len(count_result.scalars().all())

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    webhooks = result.scalars().all()

    return WebhookListResponse(
        webhooks=[WebhookResponse(**w.to_dict()) for w in webhooks],
        total=total,
    )


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get webhook details."""
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return WebhookResponse(**webhook.to_dict())


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    request: WebhookUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a webhook."""
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if request.name is not None:
        webhook.name = request.name
    if request.url is not None:
        webhook.url = request.url
    if request.secret is not None:
        webhook.secret = request.secret
    if request.enabled is not None:
        webhook.enabled = request.enabled
    if request.trigger_events is not None:
        events = validate_events(request.trigger_events)
        webhook.trigger_events = ",".join(events)
    if request.filters is not None:
        webhook.filters = request.filters
    # Jira configuration updates
    if request.jira_url is not None:
        webhook.jira_url = request.jira_url
    if request.jira_email is not None:
        webhook.jira_email = request.jira_email
    if request.jira_api_token is not None:
        webhook.jira_api_token = request.jira_api_token
    if request.jira_project_key is not None:
        webhook.jira_project_key = request.jira_project_key
    if request.jira_issue_type is not None:
        webhook.jira_issue_type = request.jira_issue_type
    # Asana configuration updates
    if request.asana_token is not None:
        webhook.asana_token = request.asana_token
    if request.asana_workspace_id is not None:
        webhook.asana_workspace_id = request.asana_workspace_id
    if request.asana_project_id is not None:
        webhook.asana_project_id = request.asana_project_id

    await db.commit()
    await db.refresh(webhook)

    return WebhookResponse(**webhook.to_dict())


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook."""
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    await db.delete(webhook)
    await db.commit()

    return {"message": "Webhook deleted"}


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Test a webhook by sending a test payload."""
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    test_payload = webhook_service.build_payload(
        event="crawl_completed",
        crawl_id="test-crawl-id",
        sitemap_url="https://example.com/sitemap.xml",
        status="completed",
        summary={
            "pages_crawled": 10,
            "links_checked": 50,
            "issues": {"critical": 2, "high": 5, "medium": 3, "low": 1},
        },
        crawl_name="Test Crawl",
        report_url="http://localhost:3000/crawls/test-crawl-id",
    )

    success, error = webhook_service.send_webhook(webhook, test_payload)

    webhook.last_triggered_at = datetime.utcnow()
    webhook.last_trigger_status = "success" if success else f"failed: {error}"
    webhook.trigger_count += 1
    await db.commit()

    if success:
        return {"status": "success", "message": "Test webhook sent successfully"}
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Webhook test failed: {error}"
        )


@router.post("/test-all")
async def test_all_webhooks(
    db: AsyncSession = Depends(get_db),
):
    """Test all enabled webhooks."""
    result = await db.execute(select(Webhook).where(Webhook.enabled == True))
    webhooks = result.scalars().all()

    if not webhooks:
        return {"message": "No enabled webhooks to test", "results": {}}

    test_payload = webhook_service.build_payload(
        event="crawl_completed",
        crawl_id="test-crawl-id",
        sitemap_url="https://example.com/sitemap.xml",
        status="completed",
        summary={
            "pages_crawled": 10,
            "links_checked": 50,
            "issues": {"critical": 2, "high": 5, "medium": 3, "low": 1},
        },
        crawl_name="Test Crawl",
        report_url="http://localhost:3000/crawls/test-crawl-id",
    )

    results = {}
    for webhook in webhooks:
        success, error = webhook_service.send_webhook(webhook, test_payload)
        results[webhook.name] = {
            "success": success,
            "error": error,
        }

        webhook.last_triggered_at = datetime.utcnow()
        webhook.last_trigger_status = "success" if success else f"failed: {error}"
        webhook.trigger_count += 1

    await db.commit()

    return {
        "message": f"Tested {len(webhooks)} webhooks",
        "results": results,
    }
