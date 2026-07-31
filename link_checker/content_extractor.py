"""Heuristic main-content text extraction for embedding.

Strips nav/footer/boilerplate from raw HTML and returns the plain-text
"main content" of a page. Used by the semantic-duplicate feature to feed
page text to an embedding provider (Ollama, OpenAI, Gemini).

The approach is intentionally dependency-free (uses beautifulsoup4 + lxml,
already installed) and heuristic rather than algorithmic:

  1. Drop non-content elements: <script>, <style>, <nav>, <footer>,
     <header>, <aside>, <form>, <noscript>, <svg>, <iframe>.
  2. Prefer semantic containers in this order: <main>, <article>,
     [role="main"], <div id="content"/class="content">.
  3. Fall back to the largest <div> by visible text length.
  4. Collapse whitespace and truncate to a configurable char limit.

It will not be as robust as a dedicated readability library, but it keeps
LinkCanary's dependency tree flat and works well on sites that use
semantic HTML5 or common content wrappers.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Tags whose entire subtree is non-content boilerplate.
_DROP_TAGS = (
    "script", "style", "nav", "footer", "header", "aside",
    "form", "noscript", "svg", "iframe", "figure", "figcaption",
)

# Common id/class substrings that signal a content container.
_CONTENT_HINTS = ("content", "main", "article", "post", "entry", "body")

# Default cap on extracted text length before it is sent to the embedder.
# 8000 chars is roughly 1500-2000 tokens, well within nomic-embed-text's
# 8192-token context window and keeps per-page payload size predictable.
DEFAULT_MAX_CHARS = 8000

_WHITESPACE_RE = re.compile(r"\s+")


def _drop_boilerplate(soup: BeautifulSoup) -> None:
    """Remove non-content tag subtrees in place."""
    for tag_name in _DROP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()


def _pick_main_container(soup: BeautifulSoup):
    """Pick the most likely main-content container, or None to use <body>."""
    # 1. Semantic HTML5 elements, in priority order.
    for selector in ("main", "article", '[role="main"]'):
        node = soup.select_one(selector)
        if node and node.get_text(strip=True):
            return node

    # 2. <div> with content-suggestive id or class.
    for div in soup.find_all("div"):
        ident = " ".join(
            filter(None, (str(div.get("id", "")), " ".join(div.get("class", []) or [])))
        ).lower()
        if any(hint in ident for hint in _CONTENT_HINTS):
            if div.get_text(strip=True):
                return div

    # 3. Largest <div> by visible text length.
    best_div = None
    best_len = 0
    for div in soup.find_all("div"):
        text_len = len(div.get_text(strip=True))
        if text_len > best_len:
            best_div = div
            best_len = text_len
    if best_div is not None and best_len > 0:
        return best_div

    return None


def extract_main_text(
    html: str,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    """Extract the main-content plain text from an HTML document.

    Args:
        html: Raw HTML markup for a single page.
        max_chars: Maximum number of characters of text to return. Text is
            truncated from the end (preserving the lead of the article).

    Returns:
        Whitespace-collapsed plain text. Empty string if no content could be
        extracted (e.g. empty page, non-HTML payload, or parse failure).
    """
    if not html or not html.strip():
        return ""

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as exc:  # lxml parse error, malformed input, etc.
        logger.warning("Failed to parse HTML for content extraction: %s", exc)
        return ""

    _drop_boilerplate(soup)

    container = _pick_main_container(soup)
    if container is None:
        container = soup.body or soup

    text = container.get_text(separator=" ", strip=True)
    text = _WHITESPACE_RE.sub(" ", text).strip()

    if max_chars and len(text) > max_chars:
        text = text[:max_chars].rstrip()
    return text
