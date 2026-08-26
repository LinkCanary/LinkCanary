"""End-to-end validation of the crawl diff endpoint and project resolution.

Exercises the real HTTP route through the diff service and report loader against
a temp SQLite DB, with auth + DB dependencies overridden. Complements the pure
unit tests in ``test_diff.py``.
"""

import csv

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from linkcanary_ui.api import crawls
from linkcanary_ui.deps.auth import RequestContext, get_current_user
from linkcanary_ui.models import Base, Crawl, CrawlStatus, MemberRole, Organization
from linkcanary_ui.models.database import get_db
from linkcanary_ui.services.projects import resolve_or_create_project


def _make_app() -> FastAPI:
    # Minimal app with just the crawls router, so the test doesn't depend on
    # main.py (which imports unrelated routers with heavier dependencies).
    app = FastAPI()
    app.include_router(crawls.router)
    return app

_REPORT_COLUMNS = [
    "source_page", "occurrence_count", "example_pages", "link_url", "link_text",
    "link_type", "element_type", "status_code", "issue_type", "priority",
    "redirect_chain", "final_url", "recommended_fix", "response_time_ms",
    "anchor_quality",
]


def _write_report(path, issues):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_REPORT_COLUMNS)
        writer.writeheader()
        for i in issues:
            row = {c: "" for c in _REPORT_COLUMNS}
            row.update(i)
            writer.writerow(row)


def _issue(url, source_page="page", priority="high", issue_type="broken_404"):
    return {
        "source_page": source_page,
        "occurrence_count": 1,
        "example_pages": "",
        "link_url": url,
        "link_text": "",
        "link_type": "internal",
        "element_type": "a",
        "status_code": 404,
        "issue_type": issue_type,
        "priority": priority,
        "redirect_chain": "",
        "final_url": "",
        "recommended_fix": "",
        "response_time_ms": "",
        "anchor_quality": "",
    }


@pytest_asyncio.fixture
async def harness(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as s:
        org = Organization(name="Test Org", slug="test-org")
        s.add(org)
        await s.commit()
        await s.refresh(org)
        org_id = org.id

    async def override_db():
        async with Session() as s:
            yield s

    async def override_auth():
        return RequestContext(
            user_id="u1", email="u@test.com", org_id=org_id,
            role=MemberRole.OWNER, org=org,
        )

    app = _make_app()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_auth

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, Session, org_id, tmp_path

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_diff_endpoint_new_resolved_persistent(harness):
    client, Session, org_id, tmp_path = harness

    # Current report: a (persistent), b (new)
    cur_csv = tmp_path / "current.csv"
    _write_report(cur_csv, [
        _issue("https://x.com/a"),
        _issue("https://x.com/b", priority="medium"),
    ])
    # Prior report: a (persistent), d (resolved)
    prior_csv = tmp_path / "prior.csv"
    _write_report(prior_csv, [
        _issue("https://x.com/a"),
        _issue("https://x.com/d", priority="critical"),
    ])

    async with Session() as s:
        project = await resolve_or_create_project(s, org_id, "https://x.com/sitemap.xml")
        prior = Crawl(
            name="prior", sitemap_url="https://x.com/sitemap.xml", org_id=org_id,
            project_id=project.id, status=CrawlStatus.COMPLETED,
            report_csv_path=str(prior_csv),
        )
        current = Crawl(
            name="current", sitemap_url="https://x.com/sitemap.xml", org_id=org_id,
            project_id=project.id, status=CrawlStatus.COMPLETED,
            report_csv_path=str(cur_csv),
        )
        s.add_all([prior, current])
        await s.commit()
        await s.refresh(prior)
        await s.refresh(current)
        prior_id, current_id = prior.id, current.id

    resp = await client.get(f"/api/crawls/{current_id}/diff")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["crawl_id"] == current_id
    assert data["against_crawl_id"] == prior_id

    new_urls = [i["link_url"] for i in data["new"]["issues"]["medium"]]
    resolved_urls = [i["link_url"] for i in data["resolved"]["issues"]["critical"]]
    persistent_urls = [i["link_url"] for i in data["persistent"]["issues"]["high"]]

    assert new_urls == ["https://x.com/b"]
    assert resolved_urls == ["https://x.com/d"]
    assert persistent_urls == ["https://x.com/a"]
    assert data["new"]["counts"]["total"] == 1
    assert data["resolved"]["counts"]["critical"] == 1


@pytest.mark.asyncio
async def test_diff_endpoint_no_prior_returns_404(harness):
    client, Session, org_id, tmp_path = harness
    async with Session() as s:
        project = await resolve_or_create_project(s, org_id, "https://x.com/sitemap.xml")
        crawl = Crawl(
            name="solo", sitemap_url="https://x.com/sitemap.xml", org_id=org_id,
            project_id=project.id, status=CrawlStatus.COMPLETED,
        )
        s.add(crawl)
        await s.commit()
        await s.refresh(crawl)
        crawl_id = crawl.id

    resp = await client.get(f"/api/crawls/{crawl_id}/diff")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_diff_endpoint_org_isolation(harness):
    client, Session, org_id, tmp_path = harness
    async with Session() as s:
        other = Organization(name="Other", slug="other")
        s.add(other)
        await s.commit()
        await s.refresh(other)
        crawl = Crawl(
            name="foreign", sitemap_url="https://foreign.com/sitemap.xml",
            org_id=other.id, status=CrawlStatus.COMPLETED,
        )
        s.add(crawl)
        await s.commit()
        await s.refresh(crawl)
        crawl_id = crawl.id

    resp = await client.get(f"/api/crawls/{crawl_id}/diff")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resolve_or_create_project_same_domain_groups(harness):
    client, Session, org_id, tmp_path = harness
    async with Session() as s:
        p1 = await resolve_or_create_project(s, org_id, "https://www.Example.com/sitemap.xml")
        p2 = await resolve_or_create_project(s, org_id, "https://example.com/sitemap.xml")
        p3 = await resolve_or_create_project(s, org_id, "https://blog.example.com/sitemap.xml")
        assert p1.id == p2.id
        assert p1.id != p3.id
