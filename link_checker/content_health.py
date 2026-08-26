"""Content-health signals: on-page SEO checks extracted from crawled page HTML.

Produces the same ``ReportRow`` shape as the rest of the reporter so results can
be concatenated onto the main report. Checks are cheap (they reuse the HTML
already fetched during the crawl) and heuristic:

  - missing / duplicate ``<title>``
  - missing / duplicate meta description
  - missing / multiple ``<h1>``
  - images missing ``alt`` text
  - thin content (word count below a threshold)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup

from .content_extractor import extract_main_text
from .reporter import ReportRow

# Pages with fewer than this many main-content words are flagged as thin.
DEFAULT_THIN_CONTENT_WORDS = 100


@dataclass
class PageMetadata:
    """On-page metadata extracted from a single page's HTML."""
    url: str
    title: str = ""
    meta_description: str = ""
    h1_texts: list[str] = field(default_factory=list)
    imgs_without_alt: list[str] = field(default_factory=list)
    word_count: int = 0


def extract_page_metadata(url: str, html: Optional[str]) -> Optional[PageMetadata]:
    """Extract on-page SEO metadata from HTML, or ``None`` if unparseable."""
    if not html or not html.strip():
        return None

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return None

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    meta = soup.find("meta", attrs={"name": "description"})
    meta_description = ""
    if meta is not None and meta.get("content"):
        meta_description = meta["content"].strip()

    h1_texts = [h.get_text(strip=True) for h in soup.find_all("h1") if h.get_text(strip=True)]

    imgs_without_alt = [
        img.get("src", "")
        for img in soup.find_all("img")
        if img.get("src") and not (img.get("alt") or "").strip()
    ]

    text = extract_main_text(html)
    word_count = len(text.split())

    return PageMetadata(
        url=url,
        title=title,
        meta_description=meta_description,
        h1_texts=h1_texts,
        imgs_without_alt=imgs_without_alt,
        word_count=word_count,
    )


def _row(
    url: str,
    issue_type: str,
    priority: str,
    fix: str,
    occurrence_count: int = 1,
    example_pages: str = "",
) -> ReportRow:
    return ReportRow(
        source_page=url,
        occurrence_count=occurrence_count,
        example_pages=example_pages,
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


def generate_content_findings(
    pages: list[PageMetadata],
    thin_content_words: int = DEFAULT_THIN_CONTENT_WORDS,
) -> list[ReportRow]:
    """Flag missing/duplicate on-page SEO signals across a set of pages.

    Args:
        pages: Metadata for each crawled page.
        thin_content_words: Word count below which a page is "thin".

    Returns:
        List of ``ReportRow`` findings (may be empty).
    """
    rows: list[ReportRow] = []

    # --- Duplicate detection (across pages) ---
    title_groups: dict[str, list[str]] = defaultdict(list)
    meta_groups: dict[str, list[str]] = defaultdict(list)
    for p in pages:
        if p.title:
            title_groups[p.title].append(p.url)
        if p.meta_description:
            meta_groups[p.meta_description].append(p.url)

    for title, urls in title_groups.items():
        if len(urls) > 1:
            rows.append(_row(
                urls[0], "duplicate_title", "high",
                f'{len(urls)} pages share the same <title> ("{title}"). '
                "Give each page a unique, descriptive title.",
                occurrence_count=len(urls),
                example_pages="|".join(urls),
            ))

    for meta, urls in meta_groups.items():
        if len(urls) > 1:
            rows.append(_row(
                urls[0], "duplicate_meta_description", "low",
                f'{len(urls)} pages share the same meta description ("{meta}"). '
                "Differentiate each page's meta description.",
                occurrence_count=len(urls),
                example_pages="|".join(urls),
            ))

    # --- Per-page checks ---
    for p in pages:
        if not p.title:
            rows.append(_row(
                p.url, "missing_title", "high",
                "Add a unique <title> tag (50-60 chars) describing this page.",
            ))
        if not p.meta_description:
            rows.append(_row(
                p.url, "missing_meta_description", "medium",
                "Add a meta description (150-160 chars) summarizing this page.",
            ))
        if not p.h1_texts:
            rows.append(_row(
                p.url, "missing_h1", "medium",
                "Add a single <h1> heading describing this page's main topic.",
            ))
        elif len(p.h1_texts) > 1:
            rows.append(_row(
                p.url, "multiple_h1", "medium",
                f"Page has {len(p.h1_texts)} <h1> tags. Use exactly one H1 per page.",
            ))
        if p.imgs_without_alt:
            rows.append(_row(
                p.url, "missing_alt", "low",
                f"{len(p.imgs_without_alt)} image(s) are missing alt text. "
                "Add descriptive alt text for accessibility and image SEO.",
                occurrence_count=len(p.imgs_without_alt),
                example_pages="|".join(p.imgs_without_alt),
            ))
        if p.word_count < thin_content_words:
            rows.append(_row(
                p.url, "thin_content", "low",
                f"Only {p.word_count} words of content. Add substantive copy to "
                "avoid being treated as thin/boilerplate content.",
            ))

    return rows
