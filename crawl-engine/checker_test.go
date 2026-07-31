package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestCheckLink200(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(200)
	}))
	defer srv.Close()

	lc := NewLinkChecker("test", 10, 0, 3, 0.1, 2.0)
	status := lc.CheckLink(srv.URL + "/page")
	if status.StatusCode != 200 {
		t.Errorf("status code = %d, want 200", status.StatusCode)
	}
	if status.IsRedirect {
		t.Error("should not be a redirect")
	}
	if status.Error != "" {
		t.Errorf("unexpected error: %q", status.Error)
	}
}

func TestCheckLink404(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(404)
	}))
	defer srv.Close()

	lc := NewLinkChecker("test", 10, 0, 3, 0.1, 2.0)
	status := lc.CheckLink(srv.URL + "/missing")
	if status.StatusCode != 404 {
		t.Errorf("status code = %d, want 404", status.StatusCode)
	}
}

func TestCheckLinkRedirect(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/old":
			w.Header().Set("Location", "/new")
			w.WriteHeader(301)
		case "/new":
			w.WriteHeader(200)
		default:
			w.WriteHeader(404)
		}
	}))
	defer srv.Close()

	lc := NewLinkChecker("test", 10, 0, 3, 0.1, 2.0)
	status := lc.CheckLink(srv.URL + "/old")
	if !status.IsRedirect {
		t.Error("should be a redirect")
	}
	if status.StatusCode != 200 {
		t.Errorf("final status code = %d, want 200", status.StatusCode)
	}
	if len(status.RedirectChain) != 2 {
		t.Errorf("redirect chain length = %d, want 2", len(status.RedirectChain))
	}
}

func TestCheckLinkRedirectLoop(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// /a -> /b -> /a
		switch r.URL.Path {
		case "/a":
			w.Header().Set("Location", "/b")
			w.WriteHeader(302)
		case "/b":
			w.Header().Set("Location", "/a")
			w.WriteHeader(302)
		}
	}))
	defer srv.Close()

	lc := NewLinkChecker("test", 10, 0, 3, 0.1, 2.0)
	status := lc.CheckLink(srv.URL + "/a")
	if !status.IsLoop {
		t.Error("should detect redirect loop")
	}
}

func TestCheckLinkHeadFallback(t *testing.T) {
	headCalled := false
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "HEAD" {
			headCalled = true
			w.WriteHeader(405) // Method not allowed
			return
		}
		w.WriteHeader(200)
	}))
	defer srv.Close()

	lc := NewLinkChecker("test", 10, 0, 3, 0.1, 2.0)
	status := lc.CheckLink(srv.URL + "/page")
	if !headCalled {
		t.Error("HEAD should have been tried first")
	}
	if status.StatusCode != 200 {
		t.Errorf("status code = %d, want 200 (after GET fallback)", status.StatusCode)
	}
}

func TestCheckLinkRetryOn503(t *testing.T) {
	attemptCount := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attemptCount++
		if attemptCount < 3 {
			w.WriteHeader(503)
			return
		}
		w.WriteHeader(200)
	}))
	defer srv.Close()

	lc := NewLinkChecker("test", 10, 0, 3, 0.01, 2.0) // very short retry delay
	status := lc.CheckLink(srv.URL + "/flaky")
	if status.StatusCode != 200 {
		t.Errorf("status code = %d, want 200 (after retries)", status.StatusCode)
	}
	if status.Retries < 2 {
		t.Errorf("retries = %d, want >= 2", status.Retries)
	}
}

func TestCheckLinkCanonicalRedirect(t *testing.T) {
	var srvURL string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// /page -> /page/ (canonical trailing slash)
		switch r.URL.Path {
		case "/page":
			w.Header().Set("Location", srvURL+"/page/")
			w.WriteHeader(301)
		case "/page/":
			w.WriteHeader(200)
		}
	}))
	defer srv.Close()
	srvURL = srv.URL

	lc := NewLinkChecker("test", 10, 0, 3, 0.1, 2.0)
	status := lc.CheckLink(srvURL + "/page")
	if !status.IsRedirect {
		t.Error("should be a redirect")
	}
	if !status.IsCanonicalRedir {
		t.Error("should be a canonical redirect (trailing slash)")
	}
}

func TestCheckLinkCaching(t *testing.T) {
	requestCount := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestCount++
		w.WriteHeader(200)
	}))
	defer srv.Close()

	lc := NewLinkChecker("test", 10, 0, 3, 0.1, 2.0)
	lc.CheckLink(srv.URL + "/page")
	lc.CheckLink(srv.URL + "/page") // should use cache
	if requestCount != 1 {
		t.Errorf("expected 1 request, got %d (cache not working)", requestCount)
	}
}

func TestCheckLinkError(t *testing.T) {
	lc := NewLinkChecker("test", 2, 0, 0, 0.1, 2.0)
	// Use a port that's definitely not listening
	status := lc.CheckLink("http://127.0.0.1:9999/page")
	if status.Error == "" {
		t.Error("expected error for unreachable URL")
	}
	if status.StatusCode != 0 {
		t.Errorf("status code = %d, want 0 for error", status.StatusCode)
	}
}

func TestCheckLink429(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "HEAD" {
			w.WriteHeader(405) // Force GET fallback
			return
		}
		w.WriteHeader(429) // Always rate limited for GET
	}))
	defer srv.Close()

	lc := NewLinkChecker("test", 10, 0, 0, 0.01, 2.0) // no retries, short delay
	status := lc.CheckLink(srv.URL + "/limited")
	if status.StatusCode != 0 {
		t.Errorf("status code = %d, want 0 (error path)", status.StatusCode)
	}
	if status.Error == "" {
		t.Error("expected error message for rate limiting")
	}
}

func TestToJSONStatus(t *testing.T) {
	ls := LinkStatus{
		URL:           "https://example.com/old",
		StatusCode:    200,
		IsRedirect:    true,
		RedirectChain: [][2]string{{"301", "https://example.com/old"}, {"200", "https://example.com/new"}},
		FinalURL:      "https://example.com/new",
		Retries:       1,
		ResponseTimeMs: 42.5,
	}
	json := ls.ToJSONStatus()
	if json.URL != ls.URL {
		t.Errorf("URL = %q, want %q", json.URL, ls.URL)
	}
	if len(json.RedirectChain) != 2 {
		t.Errorf("redirect chain length = %d, want 2", len(json.RedirectChain))
	}
	if json.RedirectChain[0].Status != 301 {
		t.Errorf("first hop status = %d, want 301", json.RedirectChain[0].Status)
	}
	if json.ResponseTimeMs != 42.5 {
		t.Errorf("response time = %v, want 42.5", json.ResponseTimeMs)
	}
}
