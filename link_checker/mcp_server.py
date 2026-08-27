"""LinkCanary MCP server — expose content/schema/CWV/GSC tools to Claude.

Run as a standalone stdio MCP server (connect from Claude Desktop / Claude Code):

    python -m link_checker.mcp_server

Requires ``GOOGLE_API_KEY`` (Core Web Vitals) and/or ``GOOGLE_ACCESS_TOKEN``
(Search Console) in the environment. Schema validation needs no keys.
"""

from __future__ import annotations

import os

import requests
from mcp.server.fastmcp import FastMCP

from .core_web_vitals import PageSpeedInsightsClient, generate_cwv_findings
from .gsc import GSCError, SearchConsoleClient, detect_declining_pages
from .schema_validation import validate_page_schema

mcp = FastMCP("linkcanary")


def _fetch_html(url: str) -> str:
    response = requests.get(url, timeout=30, headers={"User-Agent": "LinkCanary/1.0"})
    response.raise_for_status()
    return response.text


@mcp.tool()
def validate_schema(url: str) -> dict:
    """Fetch a URL and validate its JSON-LD structured data (schema.org markup).

    Returns any issues: invalid JSON-LD, missing @context, missing @type, or
    missing required fields for common schema.org types.
    """
    try:
        html = _fetch_html(url)
    except Exception as exc:
        return {"url": url, "error": f"Failed to fetch: {exc}"}

    findings = validate_page_schema(url, html)
    return {
        "url": url,
        "findings": [
            {"issue_type": f.issue_type, "priority": f.priority, "recommended_fix": f.recommended_fix}
            for f in findings
        ],
    }


@mcp.tool()
def check_core_web_vitals(urls: list[str]) -> dict:
    """Check Core Web Vitals (LCP/INP/CLS) for one or more URLs via PageSpeed Insights.

    Requires GOOGLE_API_KEY. Returns per-URL metrics plus any pages that fail
    Google's 'good' thresholds.
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return {"error": "GOOGLE_API_KEY is not set"}

    client = PageSpeedInsightsClient(api_key)
    try:
        results = [client.core_web_vitals(u) for u in urls]
    finally:
        client.close()

    return {
        "results": [
            {"url": r.url, "lcp_ms": r.lcp_ms, "inp_ms": r.inp_ms, "cls": r.cls,
             "source": r.source, "error": r.error}
            for r in results
        ],
        "findings": [
            {"link_url": f.link_url, "priority": f.priority, "recommended_fix": f.recommended_fix}
            for f in generate_cwv_findings(results)
        ],
    }


@mcp.tool()
def gsc_search_analytics(
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: list[str] = ["query"],
    row_limit: int = 100,
) -> dict:
    """Query Google Search Console search analytics (clicks, impressions, CTR, position).

    Requires GOOGLE_ACCESS_TOKEN. site_url is the GSC property (e.g. "https://example.com/"
    or "sc-domain:example.com"). dimensions may be "query", "page", "country", or "device".
    """
    token = os.environ.get("GOOGLE_ACCESS_TOKEN", "")
    if not token:
        return {"error": "GOOGLE_ACCESS_TOKEN is not set"}

    client = SearchConsoleClient(lambda: token)
    try:
        rows = client.search_analytics(site_url, start_date, end_date, dimensions=dimensions, row_limit=row_limit)
    except GSCError as exc:
        return {"error": str(exc)}
    finally:
        client.close()
    return {"rows": rows}


@mcp.tool()
def gsc_declining_pages(
    site_url: str,
    current_start: str,
    current_end: str,
    previous_start: str,
    previous_end: str,
    click_drop_pct: float = 30.0,
    min_clicks: int = 10,
) -> dict:
    """Find pages whose clicks are declining while still being shown (outdated-content signal).

    Compares two periods of Search Console data and flags pages whose clicks fell
    by at least click_drop_pct while impressions held. Requires GOOGLE_ACCESS_TOKEN.
    """
    token = os.environ.get("GOOGLE_ACCESS_TOKEN", "")
    if not token:
        return {"error": "GOOGLE_ACCESS_TOKEN is not set"}

    client = SearchConsoleClient(lambda: token)
    try:
        current = client.top_pages(site_url, current_start, current_end)
        previous = client.top_pages(site_url, previous_start, previous_end)
    except GSCError as exc:
        return {"error": str(exc)}
    finally:
        client.close()

    declining = detect_declining_pages(current, previous, click_drop_pct=click_drop_pct, min_clicks=min_clicks)
    return {
        "declining_pages": [
            {"page": p, "current_clicks": current[p]["clicks"], "previous_clicks": previous[p]["clicks"]}
            for p in declining
        ],
    }


def run() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    run()
