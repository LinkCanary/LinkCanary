"""Tests for the LinkCanary MCP server."""

import link_checker.mcp_server as server


def test_tools_registered():
    tools = server.mcp._tool_manager.list_tools()
    names = {t.name for t in tools}
    assert names == {
        "validate_schema",
        "check_core_web_vitals",
        "gsc_search_analytics",
        "gsc_declining_pages",
    }


def test_validate_schema_tool(monkeypatch):
    monkeypatch.setattr(
        server, "_fetch_html",
        lambda url: '<html><head><script type="application/ld+json">{bad json</script></head></html>',
    )
    result = server.validate_schema("https://x.com")
    assert result["url"] == "https://x.com"
    assert any(f["issue_type"] == "invalid_json_ld" for f in result["findings"])


def test_cwv_tool_requires_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    result = server.check_core_web_vitals(["https://x.com"])
    assert result == {"error": "GOOGLE_API_KEY is not set"}


def test_gsc_tools_require_token(monkeypatch):
    monkeypatch.delenv("GOOGLE_ACCESS_TOKEN", raising=False)
    assert server.gsc_search_analytics("https://x.com/", "2026-01-01", "2026-01-31") == {
        "error": "GOOGLE_ACCESS_TOKEN is not set"
    }
    assert server.gsc_declining_pages(
        "https://x.com/", "2026-01-01", "2026-01-31", "2025-12-01", "2025-12-31"
    ) == {"error": "GOOGLE_ACCESS_TOKEN is not set"}
