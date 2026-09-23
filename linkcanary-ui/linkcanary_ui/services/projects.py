"""Project resolution — map a crawl's sitemap URL to a canonical project.

Hybrid grouping model: projects are auto-resolved by a normalized domain (so a
manual crawl and a CI crawl of the same site land in the same project) but carry
an editable ``name`` for display. This module exposes the normalization rule and
the resolve-or-create operation.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Project


def normalize_domain(url: str) -> str:
    """Return a canonical domain key for grouping crawls of the same site.

    Lowercases the host, strips a leading ``www.`` and any port, so
    ``https://www.Example.com:443/sitemap.xml`` and ``https://example.com/sitemap.xml``
    both normalize to ``example.com``. Subdomains (``blog.example.com``) are kept
    distinct from the apex so separately-audited sites don't merge.
    """
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        host = ""
    if not host and url:
        # No scheme (e.g. "example.com/sitemap.xml") → urlparse treats it as a
        # path. Retry with a leading "//" so the host parses out correctly.
        host = urlparse("//" + str(url).lstrip("/")).netloc.lower()
    if not host:
        # Last resort: fall back to the raw string so callers always get a
        # non-empty key.
        host = url.lower()
    host = host.split(":", 1)[0]  # strip port
    if host.startswith("www."):
        host = host[4:]
    return host or url.lower()


async def resolve_or_create_project(
    db: AsyncSession,
    org_id: str,
    sitemap_url: str,
) -> Project:
    """Find the org's project for ``sitemap_url``, creating it if needed.

    The project name defaults to the normalized domain and can be edited later.
    """
    domain = normalize_domain(sitemap_url)

    result = await db.execute(
        select(Project).where(Project.org_id == org_id, Project.domain == domain)
    )
    project = result.scalar_one_or_none()
    if project is not None:
        return project

    project = Project(
        org_id=org_id,
        domain=domain,
        name=domain,
        sitemap_url=sitemap_url,
    )
    db.add(project)
    await db.flush()
    return project
