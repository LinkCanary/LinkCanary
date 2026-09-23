"""Tests for JSON-LD schema validation."""

from link_checker.schema_validation import (
    extract_json_ld,
    validate_page_schema,
)


def _wrap(jsonld: str) -> str:
    return f'<html><head><script type="application/ld+json">{jsonld}</script></head><body></body></html>'


def test_valid_product_no_findings():
    html = _wrap('{"@context": "https://schema.org", "@type": "Product", "name": "Widget", "offers": {"price": "10"}}')
    assert validate_page_schema("https://x.com/p", html) == []


def test_invalid_json_flagged():
    html = _wrap('{this is not json')
    findings = validate_page_schema("https://x.com/p", html)
    assert any(f.issue_type == "invalid_json_ld" for f in findings)


def test_missing_context_flagged():
    html = _wrap('{"@type": "Product", "name": "Widget"}')
    findings = validate_page_schema("https://x.com/p", html)
    types = {f.issue_type for f in findings}
    assert "missing_schema_context" in types


def test_missing_type_flagged():
    html = _wrap('{"@context": "https://schema.org", "name": "Widget"}')
    findings = validate_page_schema("https://x.com/p", html)
    assert any(f.issue_type == "missing_schema_type" for f in findings)


def test_missing_required_fields_flagged():
    html = _wrap('{"@context": "https://schema.org", "@type": "Product", "name": "Widget"}')
    findings = validate_page_schema("https://x.com/p", html)
    assert any(f.issue_type == "schema_missing_fields" for f in findings)


def test_graph_items_validated():
    html = _wrap(
        '{"@context": "https://schema.org", "@graph": ['
        '{"@type": "Product", "name": "A", "offers": {}}, '
        '{"@type": "Product"}'
        "]}"
    )
    findings = validate_page_schema("https://x.com/p", html)
    # Second graph item (Product with no name/offers) is missing fields.
    assert any(f.issue_type == "schema_missing_fields" for f in findings)


def test_no_structured_data_no_findings():
    html = "<html><head><title>No schema</title></head><body><p>hi</p></body></html>"
    assert validate_page_schema("https://x.com/p", html) == []


def test_extract_json_ld_multiple_blocks():
    html = (
        '<script type="application/ld+json">{"@type":"Organization","@context":"https://schema.org","name":"X"}</script>'
        '<script type="application/ld+json">{"@type":"WebSite"}</script>'
    )
    blocks = extract_json_ld(html)
    assert len(blocks) == 2
    assert blocks[0]["error"] is None
    assert blocks[0]["parsed"]["@type"] == "Organization"
