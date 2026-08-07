# LinkCanary Signup & Monetization Spec

> Focused implementation guide for user signup, account creation, and pricing.
> Builds on the decisions locked in `SAAS_MIGRATION_SPEC.md` (Better Auth, Stripe, Postgres, single EC2 box).

---

## 1. Pricing Tiers

Three tiers. Free gets people in the door; paid tiers monetize the real value — recurring monitoring and team features.

| | **Hatchling** (free) | **Songbird** ($19/mo) | **Flock** ($49/mo) |
|---|---|---|---|
| **Crawls / month** | 5 | 50 | Unlimited |
| **Max pages per crawl** | 500 | 5,000 | 50,000 |
| **Report retention** | 7 days | 90 days | 1 year |
| **Export formats** | CSV | CSV, HTML, PDF, Excel | All + Google Sheets |
| **Semantic analysis** | — | — | Included |
| **Projects** | 1 | 10 | Unlimited |
| **Seats** | 1 | 3 | 15 |
| **API access** | — | — | Yes |
| **Webhooks** | — | Slack, Discord | Slack, Discord, Jira, Asana |
| **Email support** | — | Standard | Priority |
| **Staging auth** | — | Basic Auth | Basic Auth + Bearer + Cookies |
| **Annual price** | — | $190/yr (save ~17%) | $490/yr (save ~17%) |

**Why these numbers:**
- $19/mo is low enough for a solo SEO freelancer to expense without thinking. Competitors (Screaming Frog) charge £149/yr for a desktop-only tool with a 500-URL free cap.
- $49/mo targets agencies and small teams who need volume, API access, and integrations.
- Free tier is generous enough to demonstrate value (5 crawls, 500 pages each = 2,500 pages/month) but limited enough that power users will hit the wall fast.

---

## 2. Signup Flow

### 2.1 User journey

```
Landing page CTA ("Start free")
  → /signup
    → Email + password  OR  Google/GitHub OAuth
    → Email verification (magic link)
    → Create org (name auto-generated from email, editable later)
    → Redirect to /dashboard (empty state with "Run your first crawl" prompt)
```

No credit card required for Hatchling. Paid upgrade prompts appear contextually (when limits are hit, not before).

### 2.2 Signup page UI

**Single page, no wizard.** Keep it fast.

```
┌─────────────────────────────────────────────┐
│                                             │
│         🐤  Create your account             │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │  [G]  Continue with Google          │    │
│  │  [O]  Continue with GitHub          │    │
│  └─────────────────────────────────────┘    │
│                                             │
│         ─── or sign up with email ───       │
│                                             │
│  Email       ________________________       │
│  Password    ________________________       │
│                                             │
│  [  Create account  ]                       │
│                                             │
│  Already have an account? Log in            │
│                                             │
│  By signing up you agree to our             │
│  Terms of Service and Privacy Policy        │
│                                             │
└─────────────────────────────────────────────┘
```

Design notes:
- OAuth buttons first (lower friction, fewer abandoned signups).
- Password field: minimum 8 characters, show/hide toggle. No forced complexity rules.
- No "confirm password" field — modern auth flows rely on password reset, not double-entry.
- Brand styling: canary yellow `#F5B800` primary button, slate charcoal `#2B3A4A` text, both light/dark modes.
- Hand-drawn sketch style illustrations (castle, umbrella, snail) can frame the signup form — match the existing LinkCanary brand.

### 2.3 Email verification

- Better Auth sends a magic link to the provided email.
- Link expires after 24 hours.
- User can still access the dashboard during verification but cannot start a crawl until verified (prevents spam/abuse).
- Resend verification link available from a banner on the dashboard.

### 2.4 OAuth flow

- **Google:** standard OAuth2 consent screen. Request `openid`, `email`, `profile` scopes.
- **GitHub:** standard OAuth2. Request `user:email` scope.
- On first OAuth login: auto-create user + org, skip email verification (provider already verified the email).
- Link existing account: if an OAuth email matches an existing email/password account, prompt to link (not duplicate).

---

## 3. Account & Organization Model

### 3.1 Auto-provisioned org

Every signup creates an **organization** automatically:

```python
# On user creation (Better Auth hook or post-signup API call)
org = Organization(
    name=f"{user.name or user.email.split('@')[0]}'s Workspace",
    slug=slugify(name),  # unique, URL-safe
    plan="hatchling",
    stripe_customer_id=None,
    created_by=user.id,
)
Membership(user_id=user.id, org_id=org.id, role="owner")
```

- Single-user orgs don't need to think about "organizations" — it just works.
- Multi-seat users rename the org and invite members from the Account page.

### 3.2 Org slug

Used in URLs: `app.linkcanary.io/org/{slug}/dashboard`. Generated from the user's display name or email prefix. Unique constraint enforced; collision appends a random suffix.

---

## 4. Technical Implementation

### 4.1 Better Auth setup

```typescript
// auth-service/src/auth.ts
import { betterAuth } from "better-auth";
import { Pool } from "pg";

export const auth = betterAuth({
  database: new Pool({ connectionString: process.env.DATABASE_URL }),
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: true,
    minPasswordLength: 8,
  },
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    },
    github: {
      clientId: process.env.GITHUB_CLIENT_ID!,
      clientSecret: process.env.GITHUB_CLIENT_SECRET!,
    },
  },
  session: {
    expiresIn: 60 * 60 * 24 * 7,  // 7 days
    updateAge: 60 * 60 * 24,       // refresh daily
  },
  plugins: [
    jwt({ jwks: { keyPairConfig: { ... } } }),
    organization({
      allowUserToCreateOrganization: true,
      organizationLimit: 1,
      membershipLimit: 50,
    }),
  ],
});
```

### 4.2 FastAPI JWT verification

```python
# backend/deps/auth.py
from fastapi import Depends, HTTPException, Request
from jose import jwt
import httpx

JWKS_URL = "http://auth:3000/auth/jwks"

async def get_current_user(request: Request) -> RequestContext:
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(401, "Not authenticated")

    # Fetch JWKS (cache with TTL in production)
    async with httpx.AsyncClient() as client:
        jwks = (await client.get(JWKS_URL)).json()

    payload = jwt.decode(token, jwks, algorithms=["RS256"])
    user_id = payload["sub"]

    # Load user + active org + role
    async with get_db() as db:
        user = await db.get(User, user_id)
        membership = await db.execute(
            select(Membership).where(Membership.user_id == user_id)
            .order_by(Membership.created_at).limit(1)
        )
        org = await db.get(Organization, membership.org_id)

    return RequestContext(user=user, org_id=org.id, role=membership.role)
```

### 4.3 Post-signup hook (create org + default project)

```python
# backend/hooks/on_signup.py
async def on_user_created(user_id: str, email: str, name: str | None):
    """Called by Better Auth webhook or post-signup callback."""
    display_name = name or email.split("@")[0]
    org = Organization(
        name=f"{display_name}'s Workspace",
        slug=generate_unique_slug(display_name),
        plan="hatchling",
    )
    async with get_db() as db:
        db.add(org)
        await db.flush()
        db.add(Membership(user_id=user_id, org_id=org.id, role="owner"))
        db.add(Project(org_id=org.id, name="My Website", is_default=True))
        await db.commit()
```

### 4.4 Signup API route (Better Auth handles this)

Better Auth exposes `/api/auth/sign-up/email`, `/api/auth/sign-in/social/google`, etc. No custom signup API needed — the React frontend calls Better Auth's client SDK:

```typescript
// frontend/src/lib/auth-client.ts
import { createAuthClient } from "better-auth/react";

export const authClient = createAuthClient({
  baseURL: import.meta.env.VITE_AUTH_URL, // http://localhost:3000/auth
});

// Usage in signup page
const handleEmailSignup = async (email: string, password: string) => {
  const { data, error } = await authClient.signUp.email({
    email,
    password,
    name: email.split("@")[0], // default display name
    callbackURL: "/dashboard",
  });
  if (error) toast.error(error.message);
  else router.push("/dashboard");
};

const handleGoogleSignup = () => {
  authClient.signIn.social({
    provider: "google",
    callbackURL: "/dashboard",
  });
};
```

### 4.5 Post-signup redirect flow

```
1. User submits signup form
2. Better Auth creates user in Postgres
3. Better Auth fires "user.created" webhook → FastAPI calls on_user_created()
4. Better Auth sets httpOnly session cookie on app.linkcanary.io
5. React redirects to /dashboard
6. Dashboard checks org context → shows empty state
```

---

## 5. Login Flow

Same page as signup (tab or toggle). Existing users land here:

```
┌─────────────────────────────────────────────┐
│                                             │
│         🐤  Welcome back                    │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │  [G]  Continue with Google          │    │
│  │  [O]  Continue with GitHub          │    │
│  └─────────────────────────────────────┘    │
│                                             │
│         ─── or log in with email ───        │
│                                             │
│  Email       ________________________       │
│  Password    ________________________       │
│                                             │
│  [  Log in  ]          Forgot password?     │
│                                             │
│  Don't have an account? Sign up             │
│                                             │
└─────────────────────────────────────────────┘
```

### 5.1 Password reset

- "Forgot password?" → enter email → magic link sent → click → set new password → redirect to dashboard.
- Better Auth handles the token generation and email sending.

### 5.2 Session management

- httpOnly cookie on `app.linkcanary.io` (not accessible to JS — XSS safe).
- 7-day expiry, refreshed daily on activity.
- Logout clears cookie server-side + client-side redirect to `/login`.

---

## 6. Monetization Hooks (Where Upgrade Prompts Appear)

Don't block the experience — prompt at the moment of need.

| Trigger | Message | Action |
|---|---|---|
| 5th crawl started (monthly limit) | "You've used all 5 free crawls this month. Upgrade to Songbird for 50 crawls/month." | Stripe Checkout |
| Crawl exceeds 500 pages | "This site has 1,247 pages. Hatchling supports 500. Upgrade to crawl the full site." | Stripe Checkout |
| Trying to export PDF/Excel | "PDF export is available on Songbird and above." | Stripe Checkout |
| Trying to add a 2nd project | "Multiple projects require Songbird or above." | Stripe Checkout |
| Report older than 7 days | "This report has expired. Upgrade to keep reports for 90 days." | Stripe Checkout |
| Trying to invite a team member | "Team seats are available on Songbird and above." | Stripe Checkout |
| Trying to use API keys | "API access is available on Flock." | Stripe Checkout |

**Pattern:** modal overlay with clear pricing, not a redirect. One click to Stripe Checkout, one click back.

---

## 7. Stripe Integration (Payment Links)

Uses **Stripe Payment Links** — the simplest possible integration. Stripe hosts the entire checkout page; the frontend just redirects there. No backend checkout session creation needed.

### 7.1 Setup (Stripe dashboard)

1. Go to https://dashboard.stripe.com/payment-links
2. Create 4 Payment Links:
   - Songbird monthly ($19/mo)
   - Songbird yearly ($190/yr)
   - Flock monthly ($49/mo)
   - Flock yearly ($490/yr)
3. For each link, set:
   - **Success URL:** `https://app.linkcanary.io/account/billing?upgraded=true`
   - **Metadata:** collect `client_reference_id` (the org ID)
4. Copy each Payment Link URL into `frontend/src/pages/Billing.jsx` → `PAYMENT_LINKS`

### 7.2 Frontend redirect

```javascript
// The user clicks "Upgrade to Songbird" → opens Stripe Payment Link
const url = 'https://buy.stripe.com/xxx';
window.open(`${url}?client_reference_id=${orgId}`, '_blank');
```

Stripe handles: card input, Apple Pay, Google Pay, receipt emails, subscription creation.

### 7.3 Webhook handler (plan sync)

The backend only needs a webhook to sync the plan state when Stripe confirms payment:

```python
@router.post("/api/billing/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)

    if event["type"] == "checkout.session.completed":
        org_id = event["data"]["object"]["client_reference_id"]
        sub = stripe.Subscription.retrieve(event["data"]["object"]["subscription"])
        await upsert_subscription(db, org_id, sub)

    elif event["type"] == "customer.subscription.deleted":
        # Downgrade to free
        ...

    return {"received": True}
```

### 7.4 Customer Portal (self-serve)

```python
@router.post("/api/billing/portal")
async def create_portal(ctx: RequestContext = Depends(get_current_user)):
    session = stripe.billing_portal.Session.create(
        customer=ctx.org.stripe_customer_id,
        return_url="https://app.linkcanary.io/account/billing",
    )
    return {"portal_url": session.url}
```

Users manage their subscription (cancel, update card, download invoices) through Stripe's hosted portal.

---

## 8. Usage Enforcement

```python
# backend/deps/usage.py
async def check_usage_limit(ctx: RequestContext, metric: str) -> None:
    """Call before starting a crawl. Raises 402 if limit exceeded."""
    plan = PLANS[ctx.org.plan]
    limit = plan.limits.get(metric)
    if limit is None:  # unlimited
        return

    current = await get_usage_counter(ctx.org.id, current_period(), metric)
    if current >= limit:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "usage_limit_exceeded",
                "metric": metric,
                "limit": limit,
                "current": current,
                "upgrade_url": "/account/billing",
                "message": f"You've reached your {metric} limit for this period. Upgrade for more.",
            },
        )
```

---

## 9. Routes Summary

| Route | Auth? | Description |
|---|---|---|
| `/signup` | No | Signup page |
| `/login` | No | Login page |
| `/forgot-password` | No | Password reset request |
| `/reset-password` | No | Password reset form (token in URL) |
| `/verify-email` | No | Email verification callback |
| `/dashboard` | Yes | Main dashboard (org-scoped) |
| `/account` | Yes | Account settings |
| `/account/billing` | Yes | Plan, usage, upgrade/manage |
| `/account/team` | Yes | Invite/manage members |
| `/account/api-keys` | Yes (Flock) | Manage API keys |
| `/auth/*` | — | Better Auth routes (proxied by Caddy) |
| `/api/billing/checkout` | Yes | Create Stripe checkout session |
| `/api/billing/portal` | Yes | Create Stripe portal session |
| `/api/billing/webhook` | No | Stripe webhook receiver |

---

## 10. Implementation Order

1. **Stand up Better Auth service** — Docker container, Postgres adapter, email/password + Google OAuth, JWT plugin, JWKS endpoint.
2. **Wire FastAPI JWT verification** — `get_current_user` dependency, org/role resolution.
3. **Post-signup hook** — auto-create org + default project.
4. **React auth pages** — signup, login, forgot password, email verification. Better Auth React client SDK.
5. **Route guards** — redirect unauthenticated users to `/login`.
6. **Stripe products** — create in Stripe dashboard (or script).
7. **Billing routes** — checkout, portal, webhook.
8. **Usage enforcement** — `check_usage_limit` dependency on crawl start.
9. **Upgrade prompts** — frontend modals at limit triggers.
10. **Account pages** — billing, team, usage dashboard.

Steps 1-5 get you a working signup system. Steps 6-10 get you monetization. Ship 1-5 first, iterate on pricing with real user data.

---

## 11. Environment Variables

```bash
# Better Auth
BETTER_AUTH_SECRET=<random 32+ char string>
BETTER_AUTH_URL=https://app.linkcanary.io/auth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...

# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/linkcanary

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PUBLISHABLE_KEY=pk_live_...

# Email (for verification emails)
SMTP_HOST=smtp.resend.com
SMTP_PORT=465
SMTP_USER=resend
SMTP_PASS=re_...
EMAIL_FROM=noreply@linkcanary.io
```

Use Resend for transactional email (simple API, $0 for first 3,000 emails/month). Or any SMTP provider.

---

## 12. Anti-Abuse Measures (Minimal for v1)

- **Email verification required before crawling** — prevents disposable-email spam.
- **Rate limit signups** — 3 per IP per hour (Redis counter).
- **Rate limit API** — per-org, configurable per plan (Redis sliding window).
- **Graceful degradation** — if Stripe webhook is delayed, allow a 24-hour grace period before downgrading.
- **No free-tier abuse** — if a user creates multiple free accounts, the 500-page-per-crawl limit makes it pointless compared to just upgrading.

---

## Appendix — What This Doc Does NOT Cover

- **Continuous monitoring** (v2 per SAAS_MIGRATION_SPEC.md)
- **Team permissions / RBAC beyond owner/admin/member** — keep it simple for v1
- **Mobile app** — not applicable
- **Self-hosted / on-premise licensing** — MIT license stays; SaaS is the hosted offering
- **Affiliate / referral program** — consider post-launch if organic growth is slow
