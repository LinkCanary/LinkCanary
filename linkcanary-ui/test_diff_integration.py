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
from sqlalchemy import select
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


@pytest.mark.asyncio
async def test_create_crawl_groups_by_domain_and_sets_org(harness, monkeypatch):
    client, Session, org_id, tmp_path = harness
    monkeypatch.setattr(crawls, "run_crawl_in_background", lambda *a, **k: None)

    r1 = await client.post("/api/crawls", json={"sitemap_url": "https://x.com"})
    assert r1.status_code == 200, r1.text
    pid1 = r1.json()["project_id"]
    assert pid1

    # Same domain (www stripped) → same project
    r2 = await client.post("/api/crawls", json={"sitemap_url": "https://www.x.com/sitemap.xml"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["project_id"] == pid1

    # Different domain → different project
    r3 = await client.post("/api/crawls", json={"sitemap_url": "https://y.com"})
    assert r3.status_code == 200, r3.text
    assert r3.json()["project_id"] != pid1

    async with Session() as s:
        rows = (await s.execute(select(Crawl))).scalars().all()
        assert len(rows) == 3
        assert all(c.org_id == org_id for c in rows)


@pytest.mark.asyncio
async def test_rerun_preserves_project(harness, monkeypatch):
    client, Session, org_id, tmp_path = harness
    monkeypatch.setattr(crawls, "run_crawl_in_background", lambda *a, **k: None)

    r1 = await client.post("/api/crawls", json={"sitemap_url": "https://x.com"})
    crawl_id = r1.json()["id"]
    pid = r1.json()["project_id"]

    r2 = await client.post(f"/api/crawls/{crawl_id}/rerun")
    assert r2.status_code == 200, r2.text
    assert r2.json()["project_id"] == pid
    assert r2.json()["id"] != crawl_id


@pytest.mark.asyncio
async def test_list_crawls_scoped_to_org(harness):
    client, Session, org_id, tmp_path = harness
    async with Session() as s:
        other = Organization(name="Other", slug="other")
        s.add(other)
        await s.commit()
        await s.refresh(other)
        s.add_all([
            Crawl(name="mine", sitemap_url="https://x.com/sitemap.xml", org_id=org_id,
                  status=CrawlStatus.COMPLETED),
            Crawl(name="foreign", sitemap_url="https://z.com/sitemap.xml", org_id=other.id,
                  status=CrawlStatus.COMPLETED),
        ])
        await s.commit()

    r = await client.get("/api/crawls")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 1
    assert data["crawls"][0]["name"] == "mine"


@pytest.mark.asyncio
async def test_get_report_parses_all_fields(harness):
    """Regression guard for the shared report-loader refactor."""
    client, Session, org_id, tmp_path = harness
    csv_path = tmp_path / "report.csv"
    _write_report(csv_path, [{
        "source_page": "multiple",
        "occurrence_count": 3,
        "example_pages": "https://x.com/p1|https://x.com/p2",
        "link_url": "https://x.com/broken",
        "link_text": "click here",
        "link_type": "internal",
        "element_type": "a",
        "status_code": 404,
        "issue_type": "broken_404",
        "priority": "high",
        "redirect_chain": "301: https://x.com/a",
        "final_url": "https://x.com/final",
        "recommended_fix": "Fix it",
        "response_time_ms": "123.5",
        "anchor_quality": "weak",
    }])

    async with Session() as s:
        crawl = Crawl(name="c", sitemap_url="https://x.com/sitemap.xml", org_id=org_id,
                      status=CrawlStatus.COMPLETED, report_csv_path=str(csv_path))
        s.add(crawl)
        await s.commit()
        await s.refresh(crawl)
        crawl_id = crawl.id

    r = await client.get(f"/api/crawls/{crawl_id}/report")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 1
    i = data["issues"][0]
    assert i["link_url"] == "https://x.com/broken"
    assert i["occurrence_count"] == 3
    assert i["example_pages"] == ["https://x.com/p1", "https://x.com/p2"]
    assert i["status_code"] == 404
    assert i["response_time_ms"] == 123.5
    assert i["anchor_quality"] == "weak"
    assert i["redirect_chain"] == "301: https://x.com/a"


@pytest.mark.asyncio
async def test_get_shared_report_public(harness):
    client, Session, org_id, tmp_path = harness
    csv_path = tmp_path / "report.csv"
    _write_report(csv_path, [_issue("https://x.com/broken")])

    async with Session() as s:
        crawl = Crawl(name="c", sitemap_url="https://x.com/sitemap.xml", org_id=org_id,
                      status=CrawlStatus.COMPLETED, report_csv_path=str(csv_path),
                      share_token="tok123")
        s.add(crawl)
        await s.commit()

    r = await client.get("/api/crawls/shared/tok123")
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 1
    assert r.json()["issues"][0]["link_url"] == "https://x.com/broken"


@pytest.mark.asyncio
async def test_diff_explicit_against(harness):
    client, Session, org_id, tmp_path = harness
    cur_csv = tmp_path / "cur.csv"
    _write_report(cur_csv, [_issue("https://x.com/new")])
    prior_csv = tmp_path / "prior.csv"
    _write_report(prior_csv, [_issue("https://x.com/old")])

    async with Session() as s:
        project = await resolve_or_create_project(s, org_id, "https://x.com/sitemap.xml")
        prior = Crawl(name="p", sitemap_url="https://x.com/sitemap.xml", org_id=org_id,
                      project_id=project.id, status=CrawlStatus.COMPLETED, report_csv_path=str(prior_csv))
        cur = Crawl(name="c", sitemap_url="https://x.com/sitemap.xml", org_id=org_id,
                    project_id=project.id, status=CrawlStatus.COMPLETED, report_csv_path=str(cur_csv))
        s.add_all([prior, cur])
        await s.commit()
        await s.refresh(prior)
        await s.refresh(cur)

    r = await client.get(f"/api/crawls/{cur.id}/diff?against={prior.id}")
    assert r.status_code == 200, r.text
    assert r.json()["against_crawl_id"] == prior.id
    assert [i["link_url"] for i in r.json()["new"]["issues"]["high"]] == ["https://x.com/new"]


@pytest.mark.asyncio
async def test_diff_identical_crawls_empty(harness):
    client, Session, org_id, tmp_path = harness
    csv_path = tmp_path / "same.csv"
    _write_report(csv_path, [_issue("https://x.com/same")])

    async with Session() as s:
        project = await resolve_or_create_project(s, org_id, "https://x.com/sitemap.xml")
        prior = Crawl(name="p", sitemap_url="https://x.com/sitemap.xml", org_id=org_id,
                      project_id=project.id, status=CrawlStatus.COMPLETED, report_csv_path=str(csv_path))
        cur = Crawl(name="c", sitemap_url="https://x.com/sitemap.xml", org_id=org_id,
                    project_id=project.id, status=CrawlStatus.COMPLETED, report_csv_path=str(csv_path))
        s.add_all([prior, cur])
        await s.commit()
        await s.refresh(prior)
        await s.refresh(cur)

    r = await client.get(f"/api/crawls/{cur.id}/diff")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["new"]["counts"]["total"] == 0
    assert d["resolved"]["counts"]["total"] == 0
    assert d["persistent"]["counts"]["total"] == 1
    assert [i["link_url"] for i in d["persistent"]["issues"]["high"]] == ["https://x.com/same"]


@pytest.mark.asyncio
async def test_delete_crawl_org_isolation(harness):
    client, Session, org_id, tmp_path = harness
    async with Session() as s:
        other = Organization(name="Other", slug="other")
        s.add(other)
        await s.commit()
        await s.refresh(other)
        crawl = Crawl(name="foreign", sitemap_url="https://z.com/sitemap.xml",
                      org_id=other.id, status=CrawlStatus.COMPLETED)
        s.add(crawl)
        await s.commit()
        await s.refresh(crawl)

    r = await client.delete(f"/api/crawls/{crawl.id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_diff_picks_most_recent_prior(harness):
    from datetime import datetime, timedelta

    client, Session, org_id, tmp_path = harness
    r1 = tmp_path / "r1.csv"
    _write_report(r1, [_issue("https://x.com/one")])
    r2 = tmp_path / "r2.csv"
    _write_report(r2, [_issue("https://x.com/two")])
    r3 = tmp_path / "r3.csv"
    _write_report(r3, [_issue("https://x.com/three")])

    base = datetime.utcnow()
    async with Session() as s:
        project = await resolve_or_create_project(s, org_id, "https://x.com/sitemap.xml")
        c1 = Crawl(name="c1", sitemap_url="https://x.com/sitemap.xml", org_id=org_id,
                   project_id=project.id, status=CrawlStatus.COMPLETED,
                   report_csv_path=str(r1), created_at=base - timedelta(days=2))
        c2 = Crawl(name="c2", sitemap_url="https://x.com/sitemap.xml", org_id=org_id,
                   project_id=project.id, status=CrawlStatus.COMPLETED,
                   report_csv_path=str(r2), created_at=base - timedelta(days=1))
        c3 = Crawl(name="c3", sitemap_url="https://x.com/sitemap.xml", org_id=org_id,
                   project_id=project.id, status=CrawlStatus.COMPLETED,
                   report_csv_path=str(r3), created_at=base)
        s.add_all([c1, c2, c3])
        await s.commit()
        await s.refresh(c1)
        await s.refresh(c2)
        await s.refresh(c3)

    r = await client.get(f"/api/crawls/{c3.id}/diff")
    assert r.status_code == 200, r.text
    d = r.json()
    # Most recent prior is c2 (not c1)
    assert d["against_crawl_id"] == c2.id
    assert [i["link_url"] for i in d["new"]["issues"]["high"]] == ["https://x.com/three"]
    assert [i["link_url"] for i in d["resolved"]["issues"]["high"]] == ["https://x.com/two"]



