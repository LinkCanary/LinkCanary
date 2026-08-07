"""Stripe billing routes: webhook (plan sync) + customer portal.

Checkout is handled by Stripe Payment Links (hosted by Stripe, no backend needed).
The frontend redirects users directly to the Payment Link URL.
Stripe fires webhooks here when payments succeed/fail.
"""

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..deps.auth import RequestContext, get_current_user
from ..models.database import get_db
from ..models.auth import Organization, Plan, Subscription, SubscriptionStatus

router = APIRouter(prefix="/api/billing", tags=["billing"])

# Maps Stripe price IDs → LinkCanary plans.
# Fill these in after creating products in Stripe:
#   stripe price list --product prod_xxx
PRICE_TO_PLAN: dict[str, Plan] = {
    # "price_xxx": Plan.SONGBIRD,  # Songbird monthly
    # "price_yyy": Plan.SONGBIRD,  # Songbird yearly
    # "price_zzz": Plan.FLOCK,     # Flock monthly
    # "price_www": Plan.FLOCK,     # Flock yearly
}


def _stripe():
    if not settings.stripe_secret_key:
        raise HTTPException(500, "Stripe not configured")
    stripe.api_key = settings.stripe_secret_key
    return stripe


@router.post("/portal")
async def create_portal(
    ctx: RequestContext = Depends(get_current_user),
):
    """Create a Stripe Customer Portal session for self-serve subscription management."""
    s = _stripe()
    if not ctx.org.stripe_customer_id:
        raise HTTPException(400, "No billing account found")

    base_url = settings.auth_url.rsplit("/auth", 1)[0]
    session = s.billing_portal.Session.create(
        customer=ctx.org.stripe_customer_id,
        return_url=f"{base_url}/account/billing",
    )
    return {"portal_url": session.url}


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhook events. Verified by Stripe signature — no auth cookie needed."""
    s = _stripe()
    if not settings.stripe_webhook_secret:
        raise HTTPException(500, "Stripe webhook secret not configured")

    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    if not sig:
        raise HTTPException(400, "Missing stripe-signature header")

    try:
        event = s.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except (s.error.SignatureVerificationError, ValueError) as e:
        raise HTTPException(400, f"Invalid signature: {e}")

    data = event["data"]["object"]

    if event["type"] == "checkout.session.completed":
        # Payment Link checkout completed — sync org + subscription
        org_id = data.get("client_reference_id") or data.get("metadata", {}).get("org_id")
        if not org_id:
            return {"received": True, "skipped": "no org_id"}

        # Get or create Stripe customer on the org
        customer_id = data.get("customer")
        org = await db.get(Organization, org_id)
        if org and customer_id:
            org.stripe_customer_id = customer_id

        # Sync subscription
        sub_id = data.get("subscription")
        if sub_id:
            sub = s.Subscription.retrieve(sub_id)
            await _upsert_subscription(db, org_id, sub)

    elif event["type"] == "customer.subscription.updated":
        sub = data
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub["id"])
        )
        db_sub = result.scalar_one_or_none()
        if db_sub:
            db_sub.status = SubscriptionStatus(sub["status"])
            db_sub.current_period_end = sub["current_period_end"]
            db_sub.cancel_at_period_end = sub.get("cancel_at_period_end", False)
            price_id = sub["items"]["data"][0]["price"]["id"]
            org = await db.get(Organization, db_sub.org_id)
            if org:
                org.plan = PRICE_TO_PLAN.get(price_id, org.plan)
            await db.commit()

    elif event["type"] == "customer.subscription.deleted":
        sub = data
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub["id"])
        )
        db_sub = result.scalar_one_or_none()
        if db_sub:
            db_sub.status = SubscriptionStatus.CANCELED
            org = await db.get(Organization, db_sub.org_id)
            if org:
                org.plan = Plan.HATCHLING
            await db.commit()

    elif event["type"] == "invoice.payment_failed":
        # TODO: send email notification, start 7-day grace period
        pass

    return {"received": True}


async def _upsert_subscription(db: AsyncSession, org_id: str, stripe_sub: dict):
    """Create or update a subscription from Stripe data."""
    price_id = stripe_sub["items"]["data"][0]["price"]["id"]
    plan = PRICE_TO_PLAN.get(price_id, Plan.HATCHLING)

    result = await db.execute(
        select(Subscription).where(Subscription.org_id == org_id)
    )
    db_sub = result.scalar_one_or_none()

    if db_sub:
        db_sub.stripe_subscription_id = stripe_sub["id"]
        db_sub.stripe_price_id = price_id
        db_sub.status = SubscriptionStatus(stripe_sub["status"])
        db_sub.current_period_end = stripe_sub["current_period_end"]
    else:
        db_sub = Subscription(
            org_id=org_id,
            stripe_subscription_id=stripe_sub["id"],
            stripe_price_id=price_id,
            status=SubscriptionStatus(stripe_sub["status"]),
            current_period_end=stripe_sub["current_period_end"],
        )
        db.add(db_sub)

    org = await db.get(Organization, org_id)
    if org:
        org.plan = plan

    await db.commit()
