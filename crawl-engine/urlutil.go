package main

import (
	"net/url"
	"path"
	"regexp"
	"sort"
	"strings"
)

// --- URL normalization and utilities ---
// Port of link_checker/utils.py

// NormalizeURL normalizes a URL for consistent comparison:
// lowercase scheme/host, remove default ports, decode percent-encoding
// in path, remove fragments, sort query parameters.
func NormalizeURL(rawURL string) string {
	if rawURL == "" {
		return rawURL
	}
	u, err := url.Parse(rawURL)
	if err != nil {
		return rawURL
	}

	u.Scheme = strings.ToLower(u.Scheme)
	u.Host = strings.ToLower(u.Host)

	// Remove default ports
	if u.Scheme == "http" && strings.HasSuffix(u.Host, ":80") {
		u.Host = strings.TrimSuffix(u.Host, ":80")
	} else if u.Scheme == "https" && strings.HasSuffix(u.Host, ":443") {
		u.Host = strings.TrimSuffix(u.Host, ":443")
	}

	u.Fragment = ""

	// Sort query parameters
	if u.RawQuery != "" {
		vals := u.Query()
		u.RawQuery = vals.Encode() // Encode sorts keys alphabetically
	}

	return u.String()
}

// GetDomain extracts the netloc (host:port) from a URL, lowercased.
func GetDomain(rawURL string) string {
	u, err := url.Parse(rawURL)
	if err != nil {
		return ""
	}
	return strings.ToLower(u.Host)
}

// GetRootDomain extracts the root domain (e.g. blog.example.com -> example.com).
func GetRootDomain(rawURL string) string {
	domain := GetDomain(rawURL)
	if domain == "" {
		return ""
	}
	// Strip port
	if idx := strings.Index(domain, ":"); idx >= 0 {
		domain = domain[:idx]
	}
	parts := strings.Split(domain, ".")
	if len(parts) <= 2 {
		return domain
	}
	commonTLDs := map[string]bool{
		"co.uk": true, "com.au": true, "co.nz": true,
		"co.za": true, "com.br": true, "co.jp": true, "co.kr": true,
	}
	if len(parts) >= 3 {
		potentialTLD := strings.Join(parts[len(parts)-2:], ".")
		if commonTLDs[potentialTLD] {
			return strings.Join(parts[len(parts)-3:], ".")
		}
	}
	return strings.Join(parts[len(parts)-2:], ".")
}

// IsInternalLink determines if linkURL is internal to baseURL's domain.
func IsInternalLink(linkURL, baseURL string, includeSubdomains bool) bool {
	if linkURL == "" || baseURL == "" {
		return false
	}
	linkDomain := GetDomain(linkURL)
	baseDomain := GetDomain(baseURL)
	if linkDomain == "" || baseDomain == "" {
		return false
	}
	// Strip ports
	if idx := strings.Index(linkDomain, ":"); idx >= 0 {
		linkDomain = linkDomain[:idx]
	}
	if idx := strings.Index(baseDomain, ":"); idx >= 0 {
		baseDomain = baseDomain[:idx]
	}
	if linkDomain == baseDomain {
		return true
	}
	if includeSubdomains {
		return GetRootDomain(linkURL) == GetRootDomain(baseURL)
	}
	return false
}

// IsValidHTTPURL checks if a URL is a valid http/https URL.
func IsValidHTTPURL(rawURL string) bool {
	if rawURL == "" {
		return false
	}
	u, err := url.Parse(rawURL)
	if err != nil {
		return false
	}
	return (u.Scheme == "http" || u.Scheme == "https") && u.Host != ""
}

// ShouldSkipLink returns true for non-HTTP link schemes (mailto, tel, etc.)
// and anchor-only links (#fragment).
func ShouldSkipLink(href string) bool {
	if href == "" {
		return true
	}
	href = strings.TrimSpace(href)
	if strings.HasPrefix(href, "#") {
		return true
	}
	skipSchemes := []string{"mailto:", "tel:", "javascript:", "data:", "file:", "ftp:", "ssh:"}
	lower := strings.ToLower(href)
	for _, s := range skipSchemes {
		if strings.HasPrefix(lower, s) {
			return true
		}
	}
	return false
}

// ResolveRelativeURL resolves a relative URL against a base URL.
func ResolveRelativeURL(baseURL, relativeURL string) string {
	if relativeURL == "" {
		return ""
	}
	relativeURL = strings.TrimSpace(relativeURL)
	if ShouldSkipLink(relativeURL) {
		return ""
	}
	base, err := url.Parse(baseURL)
	if err != nil {
		return ""
	}
	rel, err := url.Parse(relativeURL)
	if err != nil {
		return ""
	}
	resolved := base.ResolveReference(rel)
	// Remove fragment
	resolved.Fragment = ""
	return resolved.String()
}

// IsCanonicalRedirect checks if a redirect is canonical (trailing slash,
// case, or protocol difference only).
func IsCanonicalRedirect(sourceURL, destURL string) bool {
	if sourceURL == "" || destURL == "" {
		return false
	}
	src, err := url.Parse(sourceURL)
	if err != nil {
		return false
	}
	dst, err := url.Parse(destURL)
	if err != nil {
		return false
	}
	srcHost := strings.ToLower(src.Host)
	dstHost := strings.ToLower(dst.Host)
	srcHost = strings.TrimSuffix(srcHost, ":80")
	srcHost = strings.TrimSuffix(srcHost, ":443")
	dstHost = strings.TrimSuffix(dstHost, ":80")
	dstHost = strings.TrimSuffix(dstHost, ":443")
	if srcHost != dstHost {
		return false
	}
	srcPath := strings.ToLower(src.Path)
	dstPath := strings.ToLower(dst.Path)
	srcPath = strings.TrimSuffix(srcPath, "/")
	dstPath = strings.TrimSuffix(dstPath, "/")
	if srcPath != dstPath {
		return false
	}
	if src.RawQuery != dst.RawQuery {
		return false
	}
	return true
}

// FormatRedirectChain formats a redirect chain as "301:url1 → 302:url2 → 200:url3".
func FormatRedirectChain(chain [][2]string) string {
	if len(chain) == 0 {
		return ""
	}
	parts := make([]string, len(chain))
	for i, hop := range chain {
		parts[i] = hop[0] + ":" + hop[1]
	}
	return strings.Join(parts, " → ")
}

// --- URL pattern matching (glob and regex) ---
// Port of link_checker/patterns.py URLPatternMatcher

// PatternMatcher matches URLs against include/exclude patterns.
type PatternMatcher struct {
	IncludePatterns []string
	ExcludePatterns []string
	PatternType     string // "glob" or "regex"
	compiledInclude []*regexp.Regexp
	compiledExclude []*regexp.Regexp
}

func NewPatternMatcher(include, exclude []string, patternType string) *PatternMatcher {
	pm := &PatternMatcher{
		IncludePatterns: include,
		ExcludePatterns: exclude,
		PatternType:     patternType,
	}
	if patternType == "regex" {
		for _, p := range include {
			re, err := regexp.Compile("(?i)" + p)
			if err == nil {
				pm.compiledInclude = append(pm.compiledInclude, re)
			}
		}
		for _, p := range exclude {
			re, err := regexp.Compile("(?i)" + p)
			if err == nil {
				pm.compiledExclude = append(pm.compiledExclude, re)
			}
		}
	}
	return pm
}

// ShouldCheck returns true if a URL passes the pattern filters.
func (pm *PatternMatcher) ShouldCheck(rawURL string) bool {
	if len(pm.IncludePatterns) == 0 && len(pm.ExcludePatterns) == 0 {
		return true
	}
	if pm.matchesExclude(rawURL) {
		return false
	}
	if len(pm.IncludePatterns) > 0 {
		return pm.matchesInclude(rawURL)
	}
	return true
}

func (pm *PatternMatcher) matchesInclude(rawURL string) bool {
	if len(pm.IncludePatterns) == 0 {
		return true
	}
	if pm.PatternType == "regex" {
		for _, re := range pm.compiledInclude {
			if re.MatchString(rawURL) {
				return true
			}
		}
		return false
	}
	for _, p := range pm.IncludePatterns {
		if globMatch(rawURL, p) {
			return true
		}
	}
	return false
}

func (pm *PatternMatcher) matchesExclude(rawURL string) bool {
	if len(pm.ExcludePatterns) == 0 {
		return false
	}
	if pm.PatternType == "regex" {
		for _, re := range pm.compiledExclude {
			if re.MatchString(rawURL) {
				return true
			}
		}
		return false
	}
	for _, p := range pm.ExcludePatterns {
		if globMatch(rawURL, p) {
			return true
		}
	}
	return false
}

// FilterURLs returns (included, excluded) URL lists.
func (pm *PatternMatcher) FilterURLs(urls []string) ([]string, []string) {
	var included, excluded []string
	for _, u := range urls {
		if pm.ShouldCheck(u) {
			included = append(included, u)
		} else {
			excluded = append(excluded, u)
		}
	}
	return included, excluded
}

// globMatch implements the same glob matching logic as patterns.py _glob_match.
func globMatch(rawURL, pattern string) bool {
	patternLower := strings.ToLower(pattern)
	urlLower := strings.ToLower(rawURL)

	// Path pattern: starts with / - match against URL path
	if strings.HasPrefix(pattern, "/") {
		u, err := url.Parse(rawURL)
		if err != nil {
			return false
		}
		p := strings.ToLower(u.Path)
		return simpleGlob(p, patternLower) || strings.Contains(p, patternLower)
	}

	// Full wildcard: *something* - match anywhere
	if strings.HasPrefix(pattern, "*") && strings.HasSuffix(pattern, "*") {
		search := strings.Trim(patternLower, "*")
		return strings.Contains(urlLower, search)
	}

	// Prefix wildcard: *something - check suffix/contained
	if strings.HasPrefix(pattern, "*") {
		suffix := patternLower[1:]
		return strings.HasSuffix(urlLower, suffix) || strings.Contains(urlLower, suffix)
	}

	// Suffix wildcard: something* - check prefix/contained
	if strings.HasSuffix(pattern, "*") {
		prefix := patternLower[:len(patternLower)-1]
		return strings.HasPrefix(urlLower, prefix) || strings.Contains(urlLower, prefix)
	}

	// Wildcard in middle
	if strings.Contains(pattern, "*") {
		return simpleGlob(urlLower, patternLower)
	}

	// No wildcards: substring match
	return strings.Contains(urlLower, patternLower)
}

// simpleGlob does a fnmatch-style glob match (* and ? wildcards).
func simpleGlob(text, pattern string) bool {
	// Convert glob to regex
	var re strings.Builder
	re.WriteString("(?i)^")
	for _, c := range pattern {
		switch c {
		case '*':
			re.WriteString(".*")
		case '?':
			re.WriteString(".")
		case '.', '+', '(', ')', '{', '}', '[', ']', '^', '$', '|', '\\':
			re.WriteByte('\\')
			re.WriteRune(c)
		default:
			re.WriteRune(c)
		}
	}
	re.WriteString("$")
	r, err := regexp.Compile(re.String())
	if err != nil {
		return false
	}
	return r.MatchString(text)
}

// SortURLs sorts a slice of URL strings alphabetically.
func SortURLs(urls []string) {
	sort.Strings(urls)
}

// EnsurePath ensures a URL path is non-empty (defaults to "/").
func EnsurePath(rawURL string) string {
	u, err := url.Parse(rawURL)
	if err != nil {
		return rawURL
	}
	if u.Path == "" {
		u.Path = "/"
	}
	return u.String()
}

// JoinPath joins a base URL with a relative path (for sitemap lastmod etc).
func JoinPath(base, rel string) string {
	baseU, err := url.Parse(base)
	if err != nil {
		return rel
	}
	relU, err := url.Parse(rel)
	if err != nil {
		return rel
	}
	return baseU.ResolveReference(relU).String()
}

// FilePathBase returns the last element of a URL path.
func FilePathBase(rawURL string) string {
	u, err := url.Parse(rawURL)
	if err != nil {
		return ""
	}
	return path.Base(u.Path)
}
