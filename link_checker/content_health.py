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

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from .content_extractor import extract_main_text
from .reporter import ReportRow
from .utils import normalize_url

# Pages with fewer than this many main-content words are flagged as thin.
DEFAULT_THIN_CONTENT_WORDS = 100

# Pages deeper than this many clicks from the homepage are flagged as buried.
DEFAULT_MAX_CLICK_DEPTH = 3


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


def _graph_key(url: str) -> str:
    """Normalize a URL for link-graph comparison (lowercase, strip trailing slash)."""
    normed = normalize_url(url)
    parsed = urlparse(normed)
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, path, "", parsed.query, ""))


def _find_homepage(page_urls: list[str]) -> str:
    """Pick the page most likely to be the homepage: the shallowest URL path."""
    best = page_urls[0]
    best_depth = None
    for url in page_urls:
        parsed = urlparse(normalize_url(url))
        path = parsed.path.rstrip("/")
        depth = len([seg for seg in path.split("/") if seg])
        if best_depth is None or depth < best_depth:
            best, best_depth = url, depth
    return best


def compute_click_depths(
    page_urls: list[str],
    links: list,
) -> dict[str, Optional[int]]:
    """Compute each page's click depth (BFS from the homepage over internal links).

    Args:
        page_urls: All crawled page URLs (sitemap pages).
        links: ``ExtractedLink`` objects collected during the crawl.

    Returns:
        Mapping of original page URL → depth, or ``None`` if the page cannot be
        reached from the homepage via any chain of internal links.
    """
    if not page_urls:
        return {}

    page_set = {_graph_key(u) for u in page_urls}
    adjacency: dict[str, set[str]] = defaultdict(set)
    for link in links:
        if not getattr(link, "is_internal", False):
            continue
        src = _graph_key(link.source_url)
        dst = _graph_key(link.link_url)
        if src in page_set and dst in page_set and src != dst:
            adjacency[src].add(dst)

    start = _graph_key(_find_homepage(page_urls))
    depths: dict[str, int] = {start: 0}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for nxt in adjacency.get(cur, ()):
            if nxt not in depths:
                depths[nxt] = depths[cur] + 1
                queue.append(nxt)

    return {url: depths.get(_graph_key(url)) for url in page_urls}


def generate_click_depth_findings(
    depths: dict[str, Optional[int]],
    max_depth: int = DEFAULT_MAX_CLICK_DEPTH,
) -> list[ReportRow]:
    """Flag pages that are buried deep or unreachable from the homepage.

    Args:
        depths: Mapping of page URL → click depth (or ``None`` if unreachable).
        max_depth: Depth above which a page is considered "buried".

    Returns:
        List of ``ReportRow`` findings.
    """
    rows: list[ReportRow] = []
    for url, depth in depths.items():
        if depth is None:
            rows.append(_row(
                url, "unreachable_page", "low",
                "This page cannot be reached from the homepage via internal "
                "links. Add navigation links to it or restructure the site.",
            ))
        elif depth > max_depth:
            rows.append(_row(
                url, "deep_page", "low",
                f"Page is {depth} clicks from the homepage (max recommended {max_depth}). "
                "Add more direct links to surface important pages.",
            ))
    return rows
