"""Tests for the Google Search Console client."""

from link_checker.gsc import SearchConsoleClient, detect_declining_pages


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self._payload = payload
        self.last_body = None
        self.last_url = None

    def post(self, url, json, headers, timeout):
        self.last_url = url
        self.last_body = json
        return _FakeResp(self._payload)


def test_search_analytics_normalizes_rows(monkeypatch):
    client = SearchConsoleClient(lambda: "token")
    fake = _FakeSession({
        "rows": [
            {"keys": ["/page-a"], "clicks": 10, "impressions": 100, "ctr": 0.1, "position": 5.0},
            {"keys": ["/page-b"], "clicks": 3, "impressions": 200, "ctr": 0.015, "position": 9.5},
        ]
    })
    monkeypatch.setattr(client, "session", fake)

    rows = client.search_analytics("https://x.com/", "2026-01-01", "2026-01-31", dimensions=["page"])
    assert len(rows) == 2
    assert rows[0]["keys"] == ["/page-a"]
    assert rows[0]["clicks"] == 10
    assert fake.last_body["dimensions"] == ["page"]
    assert fake.last_body["startDate"] == "2026-01-01"


def test_top_pages_and_queries(monkeypatch):
    client = SearchConsoleClient(lambda: "token")
    monkeypatch.setattr(client, "session", _FakeSession({
        "rows": [{"keys": ["/x"], "clicks": 7, "impressions": 70, "ctr": 0.1, "position": 4.0}]
    }))
    pages = client.top_pages("https://x.com/", "2026-01-01", "2026-01-31")
    assert pages["/x"]["clicks"] == 7
    assert pages["/x"]["impressions"] == 70


def test_detect_declining_pages():
    current = {
        "/stale": {"clicks": 5, "impressions": 1000},
        "/fresh": {"clicks": 50, "impressions": 2000},
        "/gone": {"clicks": 0, "impressions": 300},  # impressions collapsed < 50%
    }
    previous = {
        "/stale": {"clicks": 50, "impressions": 900},
        "/fresh": {"clicks": 60, "impressions": 2000},
        "/gone": {"clicks": 30, "impressions": 800},
    }
    declining = detect_declining_pages(current, previous, click_drop_pct=30, min_clicks=10)
    # /stale: clicks 50→5 (90% drop), impressions 900→1000 (held) → declining
    # /fresh: clicks 60→50 (17% drop) → not flagged
    # /gone: clicks 30→0 but impressions 800→300 (<50%) → page is disappearing, not "declining"
    assert declining == ["/stale"]


def test_token_provider_resolution():
    from link_checker.gsc import _resolve_token

    class Provider:
        def get_token(self):
            return "obj-token"

    assert _resolve_token(lambda: "callable-token") == "callable-token"
    assert _resolve_token(Provider()) == "obj-token"
