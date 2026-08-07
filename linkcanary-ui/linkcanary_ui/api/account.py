"""Account routes: org info, usage, members, post-signup webhook."""

import re
import uuid as uuid_lib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..deps.auth import RequestContext, get_current_user, require_role
from ..models.database import get_db
from ..models.auth import (
    Membership, MemberRole, Organization, Plan, UsageCounter,
)
from ..models.auth import Subscription

router = APIRouter(prefix="/api/account", tags=["account"])

PLAN_LIMITS = {
    Plan.HATCHLING: {"crawls_per_month": 5, "max_pages_per_crawl": 500, "projects": 1, "seats": 1, "report_retention_days": 7},
    Plan.SONGBIRD: {"crawls_per_month": 50, "max_pages_per_crawl": 5000, "projects": 10, "seats": 3, "report_retention_days": 90},
    Plan.FLOCK: {"crawls_per_month": None, "max_pages_per_crawl": 50000, "projects": None, "seats": 15, "report_retention_days": 365},
}


class OrgUpdate(BaseModel):
    name: str | None = None


class InviteMember(BaseModel):
    email: str
    role: MemberRole = MemberRole.MEMBER


@router.get("/me")
async def get_me(ctx: RequestContext = Depends(get_current_user)):
    """Return current user's org context."""
    return {
        "user_id": ctx.user_id,
        "email": ctx.email,
        "org_id": ctx.org_id,
        "org_name": ctx.org.name,
        "org_slug": ctx.org.slug,
        "plan": ctx.org.plan.value,
        "role": ctx.role.value,
    }


@router.get("/org")
async def get_org(ctx: RequestContext = Depends(get_current_user)):
    """Return organization details."""
    return {
        "id": ctx.org.id,
        "name": ctx.org.name,
        "slug": ctx.org.slug,
        "plan": ctx.org.plan.value,
        "created_at": ctx.org.created_at.isoformat(),
    }


@router.put("/org")
async def update_org(
    body: OrgUpdate,
    ctx: RequestContext = Depends(require_role(MemberRole.OWNER, MemberRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Update organization name."""
    if body.name:
        ctx.org.name = body.name
        await db.commit()
    return {"ok": True}


@router.get("/usage")
async def get_usage(
    ctx: RequestContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current period usage and plan limits."""
    period = datetime.utcnow().strftime("%Y-%m")
    limits = PLAN_LIMITS[ctx.org.plan]

    result = await db.execute(
        select(UsageCounter).where(
            UsageCounter.org_id == ctx.org_id,
            UsageCounter.period == period,
        )
    )
    counters = {c.metric: c.count for c in result.scalars()}

    return {
        "period": period,
        "plan": ctx.org.plan.value,
        "limits": limits,
        "usage": {
            "crawls": counters.get("crawls", 0),
            "pages": counters.get("pages", 0),
        },
    }


@router.get("/members")
async def list_members(
    ctx: RequestContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List organization members."""
    result = await db.execute(
        select(Membership).where(Membership.org_id == ctx.org_id)
    )
    members = result.scalars().all()
    return [
        {
            "id": m.id,
            "user_id": m.user_id,
            "role": m.role.value,
            "created_at": m.created_at.isoformat(),
        }
        for m in members
    ]


@router.get("/subscription")
async def get_subscription(
    ctx: RequestContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return subscription details."""
    result = await db.execute(
        select(Subscription).where(Subscription.org_id == ctx.org_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return {"plan": ctx.org.plan.value, "status": "free", "subscription": None}

    return {
        "plan": ctx.org.plan.value,
        "status": sub.status.value,
        "current_period_end": sub.current_period_end.isoformat(),
        "cancel_at_period_end": sub.cancel_at_period_end,
    }


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:50] or "workspace"


class SignupWebhookPayload(BaseModel):
    user_id: str
    email: str
    name: str | None = None


@router.post("/on-signup")
async def on_signup(
    payload: SignupWebhookPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Called by Better Auth after user creation. Auto-provisions org + membership.

    Secured by a shared secret header from the auth service.
    """
    secret = request.headers.get("x-webhook-secret")
    if not settings.auth_webhook_secret or secret != settings.auth_webhook_secret:
        raise HTTPException(403, "Forbidden")

    # Check if user already has a membership (idempotent)
    existing = await db.execute(
        select(Membership).where(Membership.user_id == payload.user_id)
    )
    if existing.scalar_one_or_none():
        return {"ok": True, "skipped": "already has org"}

    display_name = payload.name or payload.email.split("@")[0]
    base_slug = _slugify(display_name)

    # Ensure unique slug
    slug = base_slug
    for _ in range(5):
        collision = await db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        if not collision.scalar_one_or_none():
            break
        slug = f"{base_slug}-{uuid_lib.uuid4().hex[:6]}"

    org = Organization(
        name=f"{display_name}'s Workspace",
        slug=slug,
        plan=Plan.HATCHLING,
    )
    db.add(org)
    await db.flush()

    membership = Membership(
        org_id=org.id,
        user_id=payload.user_id,
        role=MemberRole.OWNER,
    )
    db.add(membership)
    await db.commit()

    return {"ok": True, "org_id": org.id, "slug": slug}
