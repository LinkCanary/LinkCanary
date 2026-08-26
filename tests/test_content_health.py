"""Tests for content-health signal extraction and finding generation."""

from link_checker.content_health import (
    DEFAULT_THIN_CONTENT_WORDS,
    PageMetadata,
    extract_page_metadata,
    generate_content_findings,
)


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
