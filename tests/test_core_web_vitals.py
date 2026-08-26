"""Tests for the Core Web Vitals client and finding generation."""

from link_checker.core_web_vitals import (
    CWVResult,
    PageSpeedInsightsClient,
    classify_metric,
    generate_cwv_findings,
)


def test_classify_metric_thresholds():
    assert classify_metric("lcp_ms", 2000) == "good"
    assert classify_metric("lcp_ms", 3000) == "needs_improvement"
    assert classify_metric("lcp_ms", 4500) == "poor"
    assert classify_metric("cls", 0.05) == "good"
    assert classify_metric("cls", 0.3) == "poor"
    assert classify_metric("lcp_ms", None) == ""


def test_client_extracts_field_data(monkeypatch):
    client = PageSpeedInsightsClient("fake-key")

    def fake_fetch(url, strategy="mobile"):
        return {
            "loadingExperience": {"metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 2000},
                "INTERACTION_TO_NEXT_PAINT": {"percentile": 100},
                "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 0.01},
            }},
            "lighthouseResult": {"audits": {}},
        }

    monkeypatch.setattr(client, "fetch", fake_fetch)
    r = client.core_web_vitals("https://x.com")
    assert r.lcp_ms == 2000
    assert r.inp_ms == 100
    assert r.cls == 0.01
    assert r.source == "field"


def test_client_falls_back_to_lab(monkeypatch):
    client = PageSpeedInsightsClient("fake-key")

    def fake_fetch(url, strategy="mobile"):
        return {
            "loadingExperience": {},
            "lighthouseResult": {"audits": {
                "largest-contentful-paint": {"numericValue": 3000},
                "cumulative-layout-shift": {"numericValue": 0.2},
            }},
        }

    monkeypatch.setattr(client, "fetch", fake_fetch)
    r = client.core_web_vitals("https://x.com")
    assert r.lcp_ms == 3000
    assert r.cls == 0.2
    assert r.inp_ms is None
    assert r.source == "lab"


def test_generate_findings_flags_poor_and_needs_improvement():
    results = [
        CWVResult(url="https://x.com/poor", lcp_ms=4500, cls=0.3, source="field"),
        CWVResult(url="https://x.com/ni", lcp_ms=3000, source="lab"),
        CWVResult(url="https://x.com/good", lcp_ms=1500, inp_ms=100, cls=0.05, source="field"),
    ]
    findings = generate_cwv_findings(results)
    by_url = {f.link_url: f for f in findings}
    assert "https://x.com/poor" in by_url
    assert by_url["https://x.com/poor"].priority == "high"
    assert "https://x.com/ni" in by_url
    assert by_url["https://x.com/ni"].priority == "medium"
    assert "https://x.com/good" not in by_url


def test_generate_findings_error():
    results = [CWVResult(url="https://x.com/err", error="boom")]
    findings = generate_cwv_findings(results)
    assert any(f.issue_type == "core_web_vitals" and "unavailable" in f.recommended_fix for f in findings)
