package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestParseRobotsTxt(t *testing.T) {
	rc := NewRobotsChecker("LinkCanary", 10, false)
	rules := rc.parseRobotsTxt(`User-agent: *
Disallow: /private/
Disallow: /admin/
Allow: /public/
Crawl-delay: 2

User-agent: LinkCanary
Disallow: /custom/`)
	if len(rules) != 2 {
		t.Fatalf("expected 2 rule groups, got %d", len(rules))
	}
	if rules[0].UserAgent != "*" {
		t.Errorf("first rule UA = %q, want *", rules[0].UserAgent)
	}
	if len(rules[0].DisallowPaths) != 2 {
		t.Errorf("expected 2 disallow paths, got %d", len(rules[0].DisallowPaths))
	}
	if rules[0].CrawlDelay != 2 {
		t.Errorf("crawl-delay = %v, want 2", rules[0].CrawlDelay)
	}
}

func TestRobotsIsAllowed(t *testing.T) {
	robotsTxt := `User-agent: *
Disallow: /private/
Disallow: /admin/`

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/robots.txt" {
			w.Write([]byte(robotsTxt))
			return
		}
		w.WriteHeader(404)
	}))
	defer srv.Close()

	rc := NewRobotsChecker("LinkCanary", 10, false)

	// Disallowed
	ok, _ := rc.IsAllowed(srv.URL+"/private/page", srv.URL)
	if ok {
		t.Error("expected /private/ to be disallowed")
	}

	// Allowed (no matching disallow)
	ok, _ = rc.IsAllowed(srv.URL+"/public/page", srv.URL)
	if !ok {
		t.Error("expected /public/ to be allowed")
	}
}

func TestRobotsIgnoreMode(t *testing.T) {
	rc := NewRobotsChecker("LinkCanary", 10, true)
	ok, reason := rc.IsAllowed("https://example.com/private/", "https://example.com")
	if !ok {
		t.Error("ignore mode should allow everything")
	}
	if reason != "robots.txt ignored" {
		t.Errorf("reason = %q, want 'robots.txt ignored'", reason)
	}
}

func TestRobotsCrawlDelay(t *testing.T) {
	robotsTxt := `User-agent: *
Crawl-delay: 1.5`

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/robots.txt" {
			w.Write([]byte(robotsTxt))
			return
		}
		w.WriteHeader(404)
	}))
	defer srv.Close()

	rc := NewRobotsChecker("LinkCanary", 10, false)
	delay := rc.GetCrawlDelay(srv.URL)
	if delay != 1.5 {
		t.Errorf("crawl delay = %v, want 1.5", delay)
	}
}

func TestRobotsNoRobotsTxt(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(404)
	}))
	defer srv.Close()

	rc := NewRobotsChecker("LinkCanary", 10, false)
	ok, _ := rc.IsAllowed(srv.URL+"/anything", srv.URL)
	if !ok {
		t.Error("no robots.txt should allow everything")
	}
}

func TestRobotsWildcardPattern(t *testing.T) {
	rc := NewRobotsChecker("LinkCanary", 10, false)
	rules := rc.parseRobotsTxt(`User-agent: *
Disallow: /*.pdf$
Disallow: /admin/*`)
	if len(rules) != 1 {
		t.Fatalf("expected 1 rule, got %d", len(rules))
	}

	// Inject rules directly for testing
	rc.cachedRules["https://example.com"] = rules

	ok, _ := rc.IsAllowed("https://example.com/doc.pdf", "https://example.com")
	if ok {
		t.Error("*.pdf$ should disallow doc.pdf")
	}

	ok, _ = rc.IsAllowed("https://example.com/admin/page", "https://example.com")
	if ok {
		t.Error("/admin/* should disallow /admin/page")
	}

	ok, _ = rc.IsAllowed("https://example.com/page.html", "https://example.com")
	if !ok {
		t.Error("page.html should be allowed")
	}
}

func TestRobotsCheckURLSkipped(t *testing.T) {
	robotsTxt := `User-agent: *
Disallow: /blocked/`

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/robots.txt" {
			w.Write([]byte(robotsTxt))
			return
		}
		w.WriteHeader(404)
	}))
	defer srv.Close()

	rc := NewRobotsChecker("LinkCanary", 10, false)
	ok, _ := rc.CheckURL(srv.URL+"/blocked/page", srv.URL)
	if ok {
		t.Error("should be blocked")
	}
	stats := rc.GetStats()
	if stats.URLsSkipped != 1 {
		t.Errorf("skipped count = %d, want 1", stats.URLsSkipped)
	}
}

func TestFmtSscanf(t *testing.T) {
	var f float64
	fmt_sscanf("2.5", &f)
	if f != 2.5 {
		t.Errorf("fmt_sscanf('2.5') = %v, want 2.5", f)
	}
	fmt_sscanf("10", &f)
	if f != 10 {
		t.Errorf("fmt_sscanf('10') = %v, want 10", f)
	}
}

func TestRobotsCaching(t *testing.T) {
	callCount := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/robots.txt" {
			callCount++
			w.Write([]byte("User-agent: *\nDisallow: /blocked/"))
			return
		}
		w.WriteHeader(404)
	}))
	defer srv.Close()

	rc := NewRobotsChecker("LinkCanary", 10, false)
	rc.GetRulesForDomain(srv.URL)     // First call fetches
	rc.GetRulesForDomain(srv.URL)     // Second call uses cache
	if callCount != 1 {
		t.Errorf("expected 1 robots.txt fetch, got %d", callCount)
	}
}
