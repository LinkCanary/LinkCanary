"""Google Search Console client (Search Analytics API).

Provides search-performance queries (clicks, impressions, CTR, position) by
query or page, plus a helper to flag pages whose click-through is declining —
the "outdated content" signal from the content-health spec.

Auth is OAuth 2.0. The client accepts a *token provider* (a callable returning
an access token, or an object with ``get_token()``) so the token source can be
wired to Better Auth's Google OAuth later without changing this module.
"""

from __future__ import annotations

from typing import Callable, Optional, Union
from urllib.parse import quote

import requests

BASE_URL = "https://searchconsole.googleapis.com/webmasters/v3"


class GSCError(RuntimeError):
    """Raised when the Search Console API fails."""


TokenProvider = Union[Callable[[], str], object]


def _resolve_token(provider: TokenProvider) -> str:
    if callable(provider):
        return provider()
    get_token = getattr(provider, "get_token", None)
    if callable(get_token):
        return get_token()
    raise GSCError("token provider must be callable or expose get_token()")


class SearchConsoleClient:
    """Minimal Google Search Console Search Analytics client."""

    def __init__(self, token_provider: TokenProvider, timeout: int = 30, user_agent: str = "LinkCanary/1.0"):
        self.token_provider = token_provider
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {_resolve_token(self.token_provider)}"}

    def search_analytics(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: list[str] | None = None,
        row_limit: int = 100,
        data_state: str = "final",
    ) -> list[dict]:
        """Run a searchAnalytics query and return normalized rows.

        Each returned row has ``keys`` (dimension values), ``clicks``,
        ``impressions``, ``ctr``, and ``position``.

        Args:
            site_url: GSC property (``https://example.com/`` or ``sc-domain:example.com``).
            start_date/end_date: ``YYYY-MM-DD`` inclusive range.
            dimensions: e.g. ``["query"]``, ``["page"]``, ``["query", "page"]``.
            row_limit: Max rows (API cap is 25,000).
        """
        url = f"{BASE_URL}/sites/{quote(site_url, safe='')}/searchAnalytics/query"
        body: dict = {
            "startDate": start_date,
            "endDate": end_date,
            "rowLimit": row_limit,
            "dataState": data_state,
        }
        if dimensions:
            body["dimensions"] = dimensions

        try:
            response = self.session.post(
                url, json=body, headers=self._headers(), timeout=self.timeout
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise GSCError(f"Search Console query failed for {site_url}: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise GSCError(f"Search Console returned non-JSON for {site_url}") from exc

        return data.get("rows", [])

    def top_pages(
        self, site_url: str, start_date: str, end_date: str, row_limit: int = 100
    ) -> dict[str, dict]:
        """Return ``{page_url: {clicks, impressions, ctr, position}}`` for top pages."""
        rows = self.search_analytics(site_url, start_date, end_date, dimensions=["page"], row_limit=row_limit)
        return {
            row["keys"][0]: {
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": row.get("ctr", 0.0),
                "position": row.get("position", 0.0),
            }
            for row in rows
            if row.get("keys")
        }

    def top_queries(
        self, site_url: str, start_date: str, end_date: str, row_limit: int = 100
    ) -> dict[str, dict]:
        """Return ``{query: {clicks, impressions, ctr, position}}`` for top queries."""
        rows = self.search_analytics(site_url, start_date, end_date, dimensions=["query"], row_limit=row_limit)
        return {
            row["keys"][0]: {
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": row.get("ctr", 0.0),
                "position": row.get("position", 0.0),
            }
            for row in rows
            if row.get("keys")
        }

    def close(self) -> None:
        self.session.close()


def detect_declining_pages(
    current: dict[str, dict],
    previous: dict[str, dict],
    click_drop_pct: float = 30.0,
    min_clicks: int = 10,
) -> list[str]:
    """Flag pages whose clicks dropped sharply while still being shown.

    A page is "declining" (likely outdated/thin) if its clicks fell by at least
    ``click_drop_pct`` vs. the prior period while impressions held at least half,
    i.e. it's still ranking/impressing but users are clicking it less.

    Args:
        current: ``{page: {clicks, impressions, ...}}`` for the recent period.
        previous: same shape for the earlier comparison period.
        click_drop_pct: minimum click decline (%) to flag.
        min_clicks: prior-period click floor to avoid flagging noise.

    Returns:
        Sorted list of declining page URLs.
    """
    declining: list[str] = []
    for page, cur in current.items():
        prev = previous.get(page)
        if prev is None:
            continue
        if prev.get("clicks", 0) < min_clicks:
            continue
        drop = (prev["clicks"] - cur.get("clicks", 0)) / prev["clicks"] * 100.0
        impressions_held = cur.get("impressions", 0) >= prev.get("impressions", 0) * 0.5
        if drop >= click_drop_pct and impressions_held:
            declining.append(page)
    return sorted(declining, key=lambda p: previous[p]["clicks"], reverse=True)
