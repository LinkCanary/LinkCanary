"""JWT verification dependency — validates Better Auth sessions.

Usage:
    @router.get("/api/protected")
    async def protected(ctx: RequestContext = Depends(get_current_user)):
        return {"org_id": ctx.org_id, "role": ctx.role}
"""

import httpx
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.database import get_db
from ..models.auth import Membership, MemberRole, Organization


@dataclass
class RequestContext:
    user_id: str
    email: str
    org_id: str
    role: MemberRole
    org: Organization


@lru_cache(maxsize=1)
def _jwks_cache() -> dict:
    """Fetch JWKS from Better Auth. Cached until process restart."""
    # In production, use a TTL cache. For v1, lru_cache is fine —
    # restart the API container if you rotate signing keys.
    return {}


async def _fetch_jwks() -> dict:
    """Fetch JWKS from the Better Auth service."""
    cached = _jwks_cache()
    if cached:
        return cached

    jwks_url = f"{settings.auth_url}/jwks"
    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_url, timeout=5)
        resp.raise_for_status()
        jwks = resp.json()

    _jwks_cache.cache_clear()
    # Python's lru_cache doesn't support TTL, so we store on the function
    _jwks_cache.__wrapped__ = jwks  # type: ignore[attr-defined]
    return jwks


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RequestContext:
    """Extract and validate the Better Auth session cookie, resolve org context."""
    # Better Auth sets a cookie named "better-auth.session_token"
    token = request.cookies.get("better-auth.session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        jwks = await _fetch_jwks()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid session: {e}")

    user_id: Optional[str] = payload.get("sub")
    email: Optional[str] = payload.get("email")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: no user ID")

    # Resolve org from membership
    result = await db.execute(
        select(Membership, Organization)
        .join(Organization, Membership.org_id == Organization.id)
        .where(Membership.user_id == user_id)
        .order_by(Membership.created_at)
        .limit(1)
    )
    row = result.first()
    if not row:
        # User exists in Better Auth but has no org yet (post-signup race).
        # Return a minimal context — the post-signup hook will create the org.
        raise HTTPException(status_code=403, detail="No organization found. Please complete signup.")

    membership, org = row

    return RequestContext(
        user_id=user_id,
        email=email or "",
        org_id=org.id,
        role=membership.role,
        org=org,
    )


def require_role(*allowed_roles: MemberRole):
    """Dependency factory: require the user to have one of the given roles."""
    async def _check(ctx: RequestContext = Depends(get_current_user)) -> RequestContext:
        if ctx.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Requires role {[r.value for r in allowed_roles]}, you have {ctx.role.value}",
            )
        return ctx
    return _check
