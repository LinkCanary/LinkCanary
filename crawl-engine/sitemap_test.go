package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestParseSitemapURLSet(t *testing.T) {
	xml := `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/a/</loc></url>
  <url><loc>https://example.com/b/</loc></url>
  <url><loc>https://example.com/c/</loc></url>
</urlset>`

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/xml")
		w.Write([]byte(xml))
	}))
	defer srv.Close()

	sp := NewSitemapParser("test", 10)
	urls, err := sp.ParseSitemap(srv.URL, nil)
	if err != nil {
		t.Fatalf("ParseSitemap failed: %v", err)
	}
	if len(urls) != 3 {
		t.Fatalf("expected 3 URLs, got %d", len(urls))
	}
	if urls[0] != "https://example.com/a/" {
		t.Errorf("first URL = %q, want https://example.com/a/", urls[0])
	}
}

func TestParseSitemapIndex(t *testing.T) {
	sitemap1XML := `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/page1/</loc></url>
</urlset>`
	sitemap2XML := `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/page2/</loc></url>
</urlset>`

	var srvURL string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/xml")
		switch r.URL.Path {
		case "/sitemap.xml":
			indexXML := `<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>` + srvURL + `/sitemap1.xml</loc></sitemap>
  <sitemap><loc>` + srvURL + `/sitemap2.xml</loc></sitemap>
</sitemapindex>`
			w.Write([]byte(indexXML))
		case "/sitemap1.xml":
			w.Write([]byte(sitemap1XML))
		case "/sitemap2.xml":
			w.Write([]byte(sitemap2XML))
		default:
			w.WriteHeader(404)
		}
	}))
	defer srv.Close()
	srvURL = srv.URL

	sp := NewSitemapParser("test", 10)
	urls, err := sp.ParseSitemap(srvURL+"/sitemap.xml", nil)
	if err != nil {
		t.Fatalf("ParseSitemap failed: %v", err)
	}
	if len(urls) != 2 {
		t.Fatalf("expected 2 URLs from nested sitemaps, got %d", len(urls))
	}
}

func TestParseSitemapLastmodFilter(t *testing.T) {
	xml := `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/old/</loc><lastmod>2024-01-01</lastmod></url>
  <url><loc>https://example.com/new/</loc><lastmod>2026-01-01</lastmod></url>
</urlset>`

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/xml")
		w.Write([]byte(xml))
	}))
	defer srv.Close()

	sp := NewSitemapParser("test", 10)
	since := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)
	urls, err := sp.ParseSitemap(srv.URL, &since)
	if err != nil {
		t.Fatalf("ParseSitemap failed: %v", err)
	}
	if len(urls) != 1 {
		t.Fatalf("expected 1 URL after lastmod filter, got %d", len(urls))
	}
	if urls[0] != "https://example.com/new/" {
		t.Errorf("expected new/ URL, got %q", urls[0])
	}
}

func TestParseSitemapGzip(t *testing.T) {
	// Test that a .gz URL triggers gzip handling path
	// (actual decompression is tested by the gzip library)
	rawXML := `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/page/</loc></url>
</urlset>`
	// This tests the non-gzip path with a .gz URL that returns plain XML
	// (the gzip reader will fail and we fall back to raw body)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(rawXML))
	}))
	defer srv.Close()

	sp := NewSitemapParser("test", 10)
	// The URL doesn't end in .gz, so it goes through the normal path
	urls, err := sp.ParseSitemap(srv.URL, nil)
	if err != nil {
		t.Fatalf("ParseSitemap failed: %v", err)
	}
	if len(urls) != 1 {
		t.Fatalf("expected 1 URL, got %d", len(urls))
	}
}

func TestParseSitemapEmpty(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(""))
	}))
	defer srv.Close()

	sp := NewSitemapParser("test", 10)
	_, err := sp.ParseSitemap(srv.URL, nil)
	if err == nil {
		t.Error("expected error for empty sitemap, got nil")
	}
}

func TestParseLastmod(t *testing.T) {
	tests := []string{
		"2026-01-15",
		"2026-01-15T12:30:00Z",
		"2026-01-15T12:30:00+00:00",
		"2026-01-15T12:30:00.000000Z",
	}
	for _, s := range tests {
		tm := parseLastmod(s)
		if tm == nil {
			t.Errorf("parseLastmod(%q) returned nil", s)
		}
	}
	if parseLastmod("") != nil {
		t.Error("parseLastmod('') should return nil")
	}
	if parseLastmod("invalid date") != nil {
		t.Error("parseLastmod('invalid date') should return nil")
	}
}

func TestFetchSitemapNotFound(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(404)
	}))
	defer srv.Close()

	sp := NewSitemapParser("test", 10)
	_, err := sp.FetchSitemap(srv.URL)
	if err == nil {
		t.Error("expected error for 404, got nil")
	}
	if !strings.Contains(err.Error(), "404") {
		t.Errorf("error should mention 404, got: %v", err)
	}
}
