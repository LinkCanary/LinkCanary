"""Core Web Vitals via the PageSpeed Insights API.

LCP (Largest Contentful Paint), INP (Interaction to Next Paint), and CLS
(Cumulative Layout Shift) are Google's Core Web Vitals. They are *performance*
metrics, not content, and are sourced from Google's APIs rather than the page
HTML the crawler already has:

  - **field data** (Chrome UX Report) — aggregated real-user measurements,
    present in ``loadingExperience`` for pages with enough traffic.
  - **lab data** (Lighthouse) — a simulated load, in ``lighthouseResult``.

This module prefers field data when available and falls back to lab data. The
client is API-key based (PageSpeed Insights uses a standard Google API key).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests

from .reporter import ReportRow

PSI_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# Google's "good" / "poor" thresholds.
GOOD_THRESHOLDS = {"lcp_ms": 2500.0, "inp_ms": 200.0, "cls": 0.1}
POOR_THRESHOLDS = {"lcp_ms": 4000.0, "inp_ms": 500.0, "cls": 0.25}

# When CWV is run as a crawl signal, check this many pages (PSI is rate-limited
# and slow, so a full crawl is impractical; sample the first N).
DEFAULT_CWV_MAX_PAGES = 10


class CoreWebVitalsError(RuntimeError):
    """Raised when the PSI API cannot return metrics."""


@dataclass
class CWVResult:
    """Core Web Vitals for a single URL."""
    url: str
    lcp_ms: Optional[float] = None
    inp_ms: Optional[float] = None
    cls: Optional[float] = None
    source: str = ""  # "field" | "lab" | "" (no data)
    error: str = ""


class PageSpeedInsightsClient:
    """Client for the PageSpeed Insights API."""

    def __init__(self, api_key: str, timeout: int = 30, user_agent: str = "LinkCanary/1.0"):
        if not api_key:
            raise CoreWebVitalsError(
                "PageSpeed Insights requires a Google API key (set GOOGLE_API_KEY)."
            )
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def fetch(self, url: str, strategy: str = "mobile") -> dict:
        """Raw PSI API response for a URL."""
        params = {"url": url, "strategy": strategy, "key": self.api_key}
        try:
            response = self.session.get(PSI_API_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise CoreWebVitalsError(f"PageSpeed Insights request failed for {url}: {exc}") from exc
        try:
            return response.json()
        except ValueError as exc:
            raise CoreWebVitalsError(f"PageSpeed Insights returned non-JSON for {url}") from exc

    def core_web_vitals(self, url: str, strategy: str = "mobile") -> CWVResult:
        """Extract LCP/INP/CLS, preferring field (CrUX) data over lab data."""
        try:
            data = self.fetch(url, strategy)
        except CoreWebVitalsError as exc:
            return CWVResult(url=url, error=str(exc))

        result = CWVResult(url=url)

        field = (data.get("loadingExperience") or {}).get("metrics") or {}
        if field:
            if "LARGEST_CONTENTFUL_PAINT_MS" in field:
                result.lcp_ms = _num(field["LARGEST_CONTENTFUL_PAINT_MS"].get("percentile"))
            if "INTERACTION_TO_NEXT_PAINT" in field:
                result.inp_ms = _num(field["INTERACTION_TO_NEXT_PAINT"].get("percentile"))
            elif "FIRST_INPUT_DELAY_MS" in field:
                result.inp_ms = _num(field["FIRST_INPUT_DELAY_MS"].get("percentile"))
            if "CUMULATIVE_LAYOUT_SHIFT_SCORE" in field:
                result.cls = _num(field["CUMULATIVE_LAYOUT_SHIFT_SCORE"].get("percentile"))
            if any(v is not None for v in (result.lcp_ms, result.inp_ms, result.cls)):
                result.source = "field"

        lab = (data.get("lighthouseResult") or {}).get("audits") or {}
        if result.lcp_ms is None and "largest-contentful-paint" in lab:
            result.lcp_ms = _num(lab["largest-contentful-paint"].get("numericValue"))
            result.source = result.source or "lab"
        if result.cls is None and "cumulative-layout-shift" in lab:
            result.cls = _num(lab["cumulative-layout-shift"].get("numericValue"))
            result.source = result.source or "lab"

        return result

    def close(self) -> None:
        self.session.close()


def _num(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_metric(name: str, value: Optional[float]) -> str:
    """Return 'good', 'needs_improvement', 'poor', or '' (no data)."""
    if value is None:
        return ""
    good = GOOD_THRESHOLDS[name]
    poor = POOR_THRESHOLDS[name]
    if value <= good:
        return "good"
    if value <= poor:
        return "needs_improvement"
    return "poor"


def generate_cwv_findings(results: list[CWVResult]) -> list[ReportRow]:
    """Flag pages whose Core Web Vitals are worse than 'good'."""
    rows: list[ReportRow] = []
    for r in results:
        if r.error:
            rows.append(_row(r.url, "core_web_vitals", "low", f"Core Web Vitals unavailable: {r.error}"))
            continue

        problems: list[str] = []
        worst = "good"
        for metric, label, unit in (
            ("lcp_ms", "LCP", "ms"),
            ("inp_ms", "INP", "ms"),
            ("cls", "CLS", ""),
        ):
            value = getattr(r, metric)
            rating = classify_metric(metric, value)
            if rating == "poor":
                worst = "poor"
                problems.append(f"{label} {value:g}{unit} (poor)")
            elif rating == "needs_improvement":
                if worst == "good":
                    worst = "needs_improvement"
                problems.append(f"{label} {value:g}{unit} (needs improvement)")

        if problems:
            priority = "high" if worst == "poor" else "medium"
            rows.append(_row(
                r.url, "core_web_vitals", priority,
                "Core Web Vitals need attention: " + "; ".join(problems) + ".",
            ))

    return rows


def _row(url: str, issue_type: str, priority: str, fix: str) -> ReportRow:
    return ReportRow(
        source_page=url,
        occurrence_count=1,
        example_pages="",
        link_url=url,
        link_text="",
        link_type="internal",
        element_type="",
        status_code=0,
        issue_type=issue_type,
        priority=priority,
        redirect_chain="",
        final_url="",
        recommended_fix=fix,
        response_time_ms=None,
        anchor_quality="",
    )
