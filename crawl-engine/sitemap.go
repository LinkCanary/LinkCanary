package main

import (
	"compress/gzip"
	"encoding/xml"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// --- Sitemap parsing ---
// Port of link_checker/sitemap.py

// SitemapParser fetches and parses XML sitemaps (urlset and sitemapindex).
type SitemapParser struct {
	Client     *http.Client
	UserAgent  string
	Timeout    time.Duration
}

func NewSitemapParser(userAgent string, timeoutSec int) *SitemapParser {
	return &SitemapParser{
		Client:    &http.Client{Timeout: time.Duration(timeoutSec) * time.Second},
		UserAgent: userAgent,
		Timeout:   time.Duration(timeoutSec) * time.Second,
	}
}

// FetchSitemap fetches the sitemap content, handling gzip.
func (sp *SitemapParser) FetchSitemap(rawURL string) ([]byte, error) {
	req, err := http.NewRequest("GET", rawURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", sp.UserAgent)
	req.Header.Set("Accept", "application/xml, text/xml, */*")

	resp, err := sp.Client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("sitemap fetch returned status %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	// Handle gzip (either by URL extension or Content-Encoding header)
	if strings.HasSuffix(rawURL, ".gz") || resp.Header.Get("Content-Encoding") == "gzip" {
		gr, err := gzip.NewReader(strings.NewReader(string(body)))
		if err != nil {
			// Not actually gzip, return raw body
			return body, nil
		}
		defer gr.Close()
		decompressed, err := io.ReadAll(gr)
		if err != nil {
			return body, nil
		}
		return decompressed, nil
	}

	return body, nil
}

// XML structures for sitemap parsing
type xmlURLSet struct {
	XMLName xml.Name    `xml:"urlset"`
	URLs    []xmlURL    `xml:"url"`
}

type xmlSitemapIndex struct {
	XMLName  xml.Name      `xml:"sitemapindex"`
	Sitemaps []xmlSitemap  `xml:"sitemap"`
}

type xmlURL struct {
	Loc     string `xml:"loc"`
	Lastmod string `xml:"lastmod"`
}

type xmlSitemap struct {
	Loc     string `xml:"loc"`
	Lastmod string `xml:"lastmod"`
}

// ParseSitemap fetches and parses a sitemap, returning page URLs.
// Handles sitemap indexes recursively. If since is non-nil, filters by lastmod.
func (sp *SitemapParser) ParseSitemap(rawURL string, since *time.Time) ([]string, error) {
	content, err := sp.FetchSitemap(rawURL)
	if err != nil {
		return nil, err
	}
	return sp.parseSitemapContent(content, since)
}

func (sp *SitemapParser) parseSitemapContent(content []byte, since *time.Time) ([]string, error) {
	// Try parsing as sitemapindex first
	var index xmlSitemapIndex
	if err := xml.Unmarshal(content, &index); err == nil && index.XMLName.Local == "sitemapindex" {
		var allURLs []string
		for _, sm := range index.Sitemaps {
			if sm.Loc == "" {
				continue
			}
			nestedURLs, err := sp.ParseSitemap(strings.TrimSpace(sm.Loc), since)
			if err != nil {
				continue
			}
			allURLs = append(allURLs, nestedURLs...)
		}
		return allURLs, nil
	}

	// Try parsing as urlset
	var urlset xmlURLSet
	if err := xml.Unmarshal(content, &urlset); err != nil {
		return nil, fmt.Errorf("failed to parse sitemap XML: %v", err)
	}
	if urlset.XMLName.Local != "urlset" {
		return nil, fmt.Errorf("unknown sitemap root element: %s", urlset.XMLName.Local)
	}

	var urls []string
	for _, u := range urlset.URLs {
		loc := strings.TrimSpace(u.Loc)
		if loc == "" {
			continue
		}
		if since != nil {
			lastmod := parseLastmod(u.Lastmod)
			if lastmod != nil && lastmod.Before(*since) {
				continue
			}
		}
		urls = append(urls, loc)
	}
	return urls, nil
}

// parseLastmod parses a sitemap lastmod date string.
func parseLastmod(s string) *time.Time {
	if s == "" {
		return nil
	}
	s = strings.TrimSpace(s)
	// Try common formats
	formats := []string{
		"2006-01-02T15:04:05Z07:00",
		"2006-01-02T15:04:05.000000Z07:00",
		"2006-01-02T15:04:05Z",
		"2006-01-02T15:04:05",
		"2006-01-02",
	}
	for _, f := range formats {
		t, err := time.Parse(f, s)
		if err == nil {
			return &t
		}
	}
	return nil
}
