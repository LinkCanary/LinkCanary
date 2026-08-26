"""Schema validation — check a page's JSON-LD structured data.

Extracts ``<script type="application/ld+json">`` blocks and validates them:

  - parses as valid JSON
  - has a ``schema.org`` ``@context``
  - has an ``@type``
  - includes required fields for common schema.org types

Results are ``ReportRow`` findings (same shape as the rest of the reporter) so
they concatenate onto the main report. JSON-LD covers the large majority of
real-world structured data; microdata/RDFa support can be layered on later
(via ``extruct``) without changing this interface.
"""

from __future__ import annotations

import json

from bs4 import BeautifulSoup

from .reporter import ReportRow

# Minimal required fields for common schema.org types. Not exhaustive — it
# covers the highest-traffic rich-result types.
REQUIRED_FIELDS: dict[str, list[str]] = {
    "Product": ["name", "offers"],
    "Article": ["headline"],
    "NewsArticle": ["headline"],
    "BlogPosting": ["headline"],
    "Recipe": ["name", "recipeIngredient"],
    "FAQPage": ["mainEntity"],
    "BreadcrumbList": ["itemListElement"],
    "Organization": ["name"],
    "LocalBusiness": ["name"],
    "Event": ["name", "startDate"],
    "Review": ["reviewRating"],
    "Person": ["name"],
}


def extract_json_ld(html: str) -> list[dict]:
    """Extract JSON-LD blocks from HTML, each as ``{raw, parsed, error}``."""
    if not html or not html.strip():
        return []

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return []

    blocks: list[dict] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
            blocks.append({"raw": raw, "parsed": parsed, "error": None})
        except (json.JSONDecodeError, ValueError) as exc:
            blocks.append({"raw": raw, "parsed": None, "error": str(exc)})
    return blocks


def _schema_context_ok(item: dict) -> bool:
    ctx = item.get("@context")
    if isinstance(ctx, str):
        return "schema.org" in ctx
    if isinstance(ctx, list):
        return any(isinstance(c, str) and "schema.org" in c for c in ctx)
    if isinstance(ctx, dict):
        return any("schema.org" in str(v) for v in ctx.values())
    return False


def _get_types(item: dict) -> list[str]:
    t = item.get("@type")
    if isinstance(t, str):
        return [t]
    if isinstance(t, list):
        return [x for x in t if isinstance(x, str)]
    return []


def _validate_block(parsed) -> list[tuple[str, str]]:
    """Return ``(issue_type, message)`` pairs for a parsed JSON-LD block."""
    issues: list[tuple[str, str]] = []

    items: list = []
    if isinstance(parsed, dict) and isinstance(parsed.get("@graph"), list):
        items = parsed["@graph"]
    else:
        items = [parsed]

    for item in items:
        if not isinstance(item, dict):
            issues.append(("invalid_json_ld", "JSON-LD node is not an object"))
            continue
        if not _schema_context_ok(item):
            issues.append(("missing_schema_context", "Missing or non-schema.org @context"))
        types = _get_types(item)
        if not types:
            issues.append(("missing_schema_type", "Missing @type"))
            continue
        for t in types:
            if t in REQUIRED_FIELDS:
                missing = [
                    f for f in REQUIRED_FIELDS[t]
                    if f not in item or item[f] in (None, "", [], {})
                ]
                if missing:
                    issues.append((
                        "schema_missing_fields",
                        f"{t} is missing required field(s): {', '.join(missing)}",
                    ))
    return issues


_PRIORITY = {
    "invalid_json_ld": "high",
    "missing_schema_context": "medium",
    "missing_schema_type": "medium",
    "schema_missing_fields": "low",
}


def validate_page_schema(url: str, html: str) -> list[ReportRow]:
    """Validate a page's JSON-LD and return ``ReportRow`` findings.

    A page with no structured data produces no findings (absence is not an
    error; only malformed or incomplete structured data is flagged).
    """
    blocks = extract_json_ld(html)
    rows: list[ReportRow] = []

    for block in blocks:
        if block["error"] is not None:
            rows.append(_row(
                url, "invalid_json_ld", _PRIORITY["invalid_json_ld"],
                f"JSON-LD failed to parse: {block['error']}",
            ))
            continue
        for issue_type, message in _validate_block(block["parsed"]):
            rows.append(_row(url, issue_type, _PRIORITY[issue_type], message))

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
