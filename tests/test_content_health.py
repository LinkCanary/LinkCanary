"""Tests for content-health signal extraction and finding generation."""

from link_checker.content_health import (
    DEFAULT_THIN_CONTENT_WORDS,
    PageMetadata,
    compute_click_depths,
    extract_page_metadata,
    generate_click_depth_findings,
    generate_content_findings,
)
from link_checker.crawler import ExtractedLink


def _thick(extra=""):
    return " ".join(["word"] * 150) + " " + extra


def test_extract_page_metadata_fields():
    html = (
        "<html><head><title>My Page</title>"
        '<meta name="description" content="A description">'
        '</head><body><h1>Heading</h1>'
        '<img src="/a.png"><img src="/b.png" alt="b">'
        f'<p>{_thick()}</p></body></html>'
    )
    m = extract_page_metadata("https://x.com/p", html)
    assert m is not None
    assert m.title == "My Page"
    assert m.meta_description == "A description"
    assert m.h1_texts == ["Heading"]
    assert m.imgs_without_alt == ["/a.png"]
    assert m.word_count >= 150


def test_extract_page_metadata_none_for_empty():
    assert extract_page_metadata("https://x.com/p", "") is None
    assert extract_page_metadata("https://x.com/p", None) is None


def test_missing_signals_flagged():
    m = PageMetadata(url="https://x.com/p", title="", meta_description="", h1_texts=[], word_count=10)
    findings = generate_content_findings([m])
    types = {f.issue_type for f in findings}
    assert "missing_title" in types
    assert "missing_meta_description" in types
    assert "missing_h1" in types
    assert "thin_content" in types


def test_duplicate_title_and_meta_flagged():
    a = PageMetadata(url="https://x.com/a", title="Same", meta_description="Same meta", word_count=200)
    b = PageMetadata(url="https://x.com/b", title="Same", meta_description="Same meta", word_count=200)
    findings = generate_content_findings([a, b])
    types = {f.issue_type for f in findings}
    assert "duplicate_title" in types
    assert "duplicate_meta_description" in types


def test_multiple_h1_flagged():
    m = PageMetadata(url="https://x.com/p", title="T", meta_description="M",
                     h1_texts=["One", "Two"], word_count=200)
    findings = generate_content_findings([m])
    assert any(f.issue_type == "multiple_h1" for f in findings)


def test_clean_page_produces_no_findings():
    m = PageMetadata(url="https://x.com/p", title="Unique", meta_description="Unique meta",
                     h1_texts=["Heading"], word_count=200)
    assert generate_content_findings([m]) == []


def _link(src, dst, internal=True):
    return ExtractedLink(source_url=src, link_url=dst, link_text="", is_internal=internal)


def test_click_depths_bfs():
    pages = [
        "https://x.com/",          # homepage, depth 0
        "https://x.com/about",     # depth 1
        "https://x.com/team",      # depth 2
        "https://x.com/deep",      # depth 3
        "https://x.com/orphan",    # unreachable
    ]
    links = [
        _link("https://x.com/", "https://x.com/about"),
        _link("https://x.com/about", "https://x.com/team"),
        _link("https://x.com/team", "https://x.com/deep"),
    ]
    depths = compute_click_depths(pages, links)
    assert depths["https://x.com/"] == 0
    assert depths["https://x.com/about"] == 1
    assert depths["https://x.com/team"] == 2
    assert depths["https://x.com/deep"] == 3
    assert depths["https://x.com/orphan"] is None


def test_click_depth_findings_flag_deep_and_unreachable():
    depths = {
        "https://x.com/": 0,
        "https://x.com/a": 2,
        "https://x.com/deep": 4,     # > default max depth 3
        "https://x.com/orphan": None,
    }
    findings = generate_click_depth_findings(depths)
    types = {f.issue_type for f in findings}
    assert "deep_page" in types
    assert "unreachable_page" in types
    # shallow pages not flagged
    flagged_urls = {f.link_url for f in findings}
    assert "https://x.com/" not in flagged_urls
    assert "https://x.com/a" not in flagged_urls


def test_click_depths_ignores_external_links():
    pages = ["https://x.com/", "https://x.com/about"]
    links = [
        _link("https://x.com/", "https://external.com/", internal=False),
    ]
    depths = compute_click_depths(pages, links)
    assert depths["https://x.com/about"] is None  # no internal link reaches it
