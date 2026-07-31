package main

import (
	"testing"
)

func TestNormalizeURL(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"HTTPS://Example.COM/Path", "https://example.com/Path"},
		{"https://example.com:443/path", "https://example.com/path"},
		{"http://example.com:80/path", "http://example.com/path"},
		{"https://example.com/path#fragment", "https://example.com/path"},
		{"", ""},
	}
	for _, tc := range tests {
		got := NormalizeURL(tc.input)
		if got != tc.expected {
			t.Errorf("NormalizeURL(%q) = %q, want %q", tc.input, got, tc.expected)
		}
	}
}

func TestGetDomain(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"https://Example.COM/path", "example.com"},
		{"https://blog.example.com/path", "blog.example.com"},
		{"not a url", ""},
	}
	for _, tc := range tests {
		got := GetDomain(tc.input)
		if got != tc.expected {
			t.Errorf("GetDomain(%q) = %q, want %q", tc.input, got, tc.expected)
		}
	}
}

func TestGetRootDomain(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"https://blog.example.com/path", "example.com"},
		{"https://example.com/path", "example.com"},
		{"https://www.example.co.uk/path", "example.co.uk"},
	}
	for _, tc := range tests {
		got := GetRootDomain(tc.input)
		if got != tc.expected {
			t.Errorf("GetRootDomain(%q) = %q, want %q", tc.input, got, tc.expected)
		}
	}
}

func TestIsInternalLink(t *testing.T) {
	tests := []struct {
		linkURL          string
		baseURL          string
		includeSubdomains bool
		expected         bool
	}{
		{"https://example.com/page", "https://example.com", false, true},
		{"https://other.com/page", "https://example.com", false, false},
		{"https://blog.example.com/page", "https://example.com", false, false},
		{"https://blog.example.com/page", "https://example.com", true, true},
		{"", "https://example.com", false, false},
	}
	for _, tc := range tests {
		got := IsInternalLink(tc.linkURL, tc.baseURL, tc.includeSubdomains)
		if got != tc.expected {
			t.Errorf("IsInternalLink(%q, %q, %v) = %v, want %v",
				tc.linkURL, tc.baseURL, tc.includeSubdomains, got, tc.expected)
		}
	}
}

func TestIsValidHTTPURL(t *testing.T) {
	tests := []struct {
		input    string
		expected bool
	}{
		{"https://example.com", true},
		{"http://example.com/path", true},
		{"ftp://example.com", false},
		{"not a url", false},
		{"", false},
	}
	for _, tc := range tests {
		got := IsValidHTTPURL(tc.input)
		if got != tc.expected {
			t.Errorf("IsValidHTTPURL(%q) = %v, want %v", tc.input, got, tc.expected)
		}
	}
}

func TestShouldSkipLink(t *testing.T) {
	tests := []struct {
		input    string
		expected bool
	}{
		{"mailto:test@example.com", true},
		{"tel:+1234567890", true},
		{"javascript:void(0)", true},
		{"#anchor", true},
		{"", true},
		{"https://example.com", false},
		{"/blog/post/", false},
	}
	for _, tc := range tests {
		got := ShouldSkipLink(tc.input)
		if got != tc.expected {
			t.Errorf("ShouldSkipLink(%q) = %v, want %v", tc.input, got, tc.expected)
		}
	}
}

func TestResolveRelativeURL(t *testing.T) {
	tests := []struct {
		baseURL    string
		relativeURL string
		expected   string
	}{
		{"https://example.com/blog/", "post-name/", "https://example.com/blog/post-name/"},
		{"https://example.com/blog/my-post/", "/about/", "https://example.com/about/"},
		{"https://example.com/blog/", "https://other.com/page", "https://other.com/page"},
		{"https://example.com/blog/post/", "../other/", "https://example.com/blog/other/"},
		{"https://example.com/page", "mailto:test@test.com", ""},
		{"https://example.com/page", "", ""},
	}
	for _, tc := range tests {
		got := ResolveRelativeURL(tc.baseURL, tc.relativeURL)
		if got != tc.expected {
			t.Errorf("ResolveRelativeURL(%q, %q) = %q, want %q",
				tc.baseURL, tc.relativeURL, got, tc.expected)
		}
	}
}

func TestIsCanonicalRedirect(t *testing.T) {
	tests := []struct {
		source   string
		dest     string
		expected bool
	}{
		{"https://example.com/page", "https://example.com/page/", true},
		{"http://example.com/page", "https://example.com/page", true},
		{"https://example.com/page", "https://example.com/other", false},
		{"https://example.com/page", "https://other.com/page", false},
		{"", "", false},
	}
	for _, tc := range tests {
		got := IsCanonicalRedirect(tc.source, tc.dest)
		if got != tc.expected {
			t.Errorf("IsCanonicalRedirect(%q, %q) = %v, want %v",
				tc.source, tc.dest, got, tc.expected)
		}
	}
}

func TestFormatRedirectChain(t *testing.T) {
	chain := [][2]string{
		{"301", "https://example.com/old"},
		{"302", "https://example.com/new"},
		{"200", "https://example.com/final"},
	}
	got := FormatRedirectChain(chain)
	expected := "301:https://example.com/old → 302:https://example.com/new → 200:https://example.com/final"
	if got != expected {
		t.Errorf("FormatRedirectChain() = %q, want %q", got, expected)
	}
	if FormatRedirectChain(nil) != "" {
		t.Error("FormatRedirectChain(nil) should be empty")
	}
}

func TestGlobMatch(t *testing.T) {
	tests := []struct {
		url      string
		pattern  string
		expected bool
	}{
		{"https://linkedin.com/company", "*linkedin.com*", true},
		{"https://example.com/document.pdf", "*.pdf", true},
		{"https://example.com/blog/post", "/blog/*", true},
		{"https://example.com/docs/api", "/docs/*", true},
		{"https://example.com/about", "/blog/*", false},
		{"https://example.com/page.html", "*.pdf", false},
	}
	for _, tc := range tests {
		got := globMatch(tc.url, tc.pattern)
		if got != tc.expected {
			t.Errorf("globMatch(%q, %q) = %v, want %v", tc.url, tc.pattern, got, tc.expected)
		}
	}
}

func TestPatternMatcher(t *testing.T) {
	pm := NewPatternMatcher(
		[]string{"/blog/*"},
		[]string{"*linkedin.com*"},
		"glob",
	)
	tests := []struct {
		url      string
		expected bool
	}{
		{"https://example.com/blog/post", true},
		{"https://example.com/about", false},
		{"https://linkedin.com/company", false},
	}
	for _, tc := range tests {
		got := pm.ShouldCheck(tc.url)
		if got != tc.expected {
			t.Errorf("PatternMatcher.ShouldCheck(%q) = %v, want %v", tc.url, got, tc.expected)
		}
	}
}
