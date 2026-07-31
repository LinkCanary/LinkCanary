package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os/exec"
	"strings"
	"testing"
)

// TestIntegrationEndToEnd spins up a test server with sitemap + pages,
// runs the crawl-engine binary, and verifies the JSON output.
func TestIntegrationEndToEnd(t *testing.T) {
	// Set up a test server with sitemap and pages
	sitemapXML := `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>%s/page1/</loc></url>
  <url><loc>%s/page2/</loc></url>
</urlset>`

	page1HTML := `<html><body>
		<a href="/page2/">Page 2</a>
		<a href="https://external.com/">External</a>
		<a href="/broken/">Broken Link</a>
	</body></html>`

	page2HTML := `<html><body>
		<a href="/page1/">Page 1</a>
		<img src="/images/photo.png" alt="Photo">
	</body></html>`

	var srvURL string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/sitemap.xml":
			w.Header().Set("Content-Type", "application/xml")
			w.Write([]byte(strings.ReplaceAll(sitemapXML, "%s", srvURL)))
		case "/page1/":
			w.Header().Set("Content-Type", "text/html")
			w.Write([]byte(page1HTML))
		case "/page2/":
			w.Header().Set("Content-Type", "text/html")
			w.Write([]byte(page2HTML))
		case "/broken/":
			w.WriteHeader(404)
		case "/images/photo.png":
			w.Header().Set("Content-Type", "image/png")
			w.Write([]byte("fake png"))
		default:
			w.WriteHeader(404)
		}
	}))
	defer srv.Close()
	srvURL = srv.URL

	// Build and run the binary
	cmd := exec.Command("go", "run", ".", "--sitemap-url", srvURL+"/sitemap.xml",
		"--delay", "0", "--timeout", "5", "--no-retry", "--verbose")
	cmd.Dir = "."

	output, err := cmd.Output()
	if err != nil {
		t.Fatalf("crawl-engine failed: %v\nstderr: %s", err, output)
	}

	// Parse JSON output
	var result CrawlOutput
	if err := json.Unmarshal(output, &result); err != nil {
		t.Fatalf("failed to parse JSON output: %v\noutput: %s", err, string(output))
	}

	// Verify metadata
	if !result.Metadata.SitemapMode {
		t.Error("expected sitemap mode to be true")
	}
	if result.Metadata.PageCount != 2 {
		t.Errorf("page count = %d, want 2", result.Metadata.PageCount)
	}

	// Verify we got links from both pages
	if len(result.Links) < 3 {
		t.Errorf("expected at least 3 links, got %d", len(result.Links))
	}

	// Verify link statuses include the 404
	found404 := false
	found200 := false
	for _, status := range result.LinkStatuses {
		if status.StatusCode == 404 {
			found404 = true
		}
		if status.StatusCode == 200 {
			found200 = true
		}
	}
	if !found404 {
		t.Error("expected to find a 404 status")
	}
	if !found200 {
		t.Error("expected to find a 200 status")
	}
}

// TestIntegrationSingleURL tests the --url mode
func TestIntegrationSingleURL(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		w.Write([]byte(`<html><body><a href="/other/">Other</a></body></html>`))
	}))
	defer srv.Close()

	cmd := exec.Command("go", "run", ".", "--url", srv.URL+"/",
		"--delay", "0", "--timeout", "5", "--no-retry")
	cmd.Dir = "."

	output, err := cmd.Output()
	if err != nil {
		t.Fatalf("crawl-engine failed: %v", err)
	}

	var result CrawlOutput
	if err := json.Unmarshal(output, &result); err != nil {
		t.Fatalf("failed to parse JSON: %v\noutput: %s", err, string(output))
	}

	if result.Metadata.PageCount != 1 {
		t.Errorf("page count = %d, want 1", result.Metadata.PageCount)
	}
	if result.Metadata.SitemapMode {
		t.Error("expected sitemap mode to be false for --url")
	}
}

// TestIntegrationCollectHTML tests that --collect-html includes page HTML
func TestIntegrationCollectHTML(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		w.Write([]byte(`<html><body><h1>Test Page</h1></body></html>`))
	}))
	defer srv.Close()

	cmd := exec.Command("go", "run", ".", "--url", srv.URL+"/",
		"--delay", "0", "--timeout", "5", "--no-retry", "--collect-html")
	cmd.Dir = "."

	output, err := cmd.Output()
	if err != nil {
		t.Fatalf("crawl-engine failed: %v", err)
	}

	var result CrawlOutput
	if err := json.Unmarshal(output, &result); err != nil {
		t.Fatalf("failed to parse JSON: %v", err)
	}

	if len(result.PageHTML) == 0 {
		t.Error("expected page HTML to be collected with --collect-html")
	}
}
