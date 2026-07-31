package main

import (
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
)

// --- robots.txt parsing and compliance ---
// Port of link_checker/robots.py

// RobotsRule represents a single robots.txt rule group.
type RobotsRule struct {
	UserAgent    string
	AllowPaths   []string
	DisallowPaths []string
	CrawlDelay   float64 // seconds, -1 = not set
}

// RobotsChecker fetches, parses, and enforces robots.txt rules.
type RobotsChecker struct {
	Client        *http.Client
	UserAgent     string
	IgnoreRobots  bool
	cachedRules   map[string][]RobotsRule // keyed by "scheme://host"
	skippedCount  int
}

func NewRobotsChecker(userAgent string, timeoutSec int, ignore bool) *RobotsChecker {
	return &RobotsChecker{
		Client:       &http.Client{Timeout: time.Duration(timeoutSec) * time.Second},
		UserAgent:    strings.ToLower(userAgent),
		IgnoreRobots: ignore,
		cachedRules:  make(map[string][]RobotsRule),
	}
}

// GetRulesForDomain fetches and caches robots.txt rules for a domain.
func (rc *RobotsChecker) GetRulesForDomain(baseURL string) []RobotsRule {
	if rc.IgnoreRobots {
		return nil
	}
	parsed, err := url.Parse(baseURL)
	if err != nil {
		return nil
	}
	domain := parsed.Scheme + "://" + parsed.Host
	if rules, ok := rc.cachedRules[domain]; ok {
		return rules
	}
	content := rc.fetchRobotsTxt(domain)
	rules := rc.parseRobotsTxt(content)
	rc.cachedRules[domain] = rules
	return rules
}

func (rc *RobotsChecker) fetchRobotsTxt(domain string) string {
	robotsURL := domain + "/robots.txt"
	req, err := http.NewRequest("GET", robotsURL, nil)
	if err != nil {
		return ""
	}
	req.Header.Set("User-Agent", rc.UserAgent)
	resp, err := rc.Client.Do(req)
	if err != nil {
		return ""
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return ""
	}
	buf := make([]byte, 0, 4096)
	tmp := make([]byte, 4096)
	for {
		n, err := resp.Body.Read(tmp)
		if n > 0 {
			buf = append(buf, tmp[:n]...)
		}
		if err != nil {
			break
		}
	}
	return string(buf)
}

func (rc *RobotsChecker) parseRobotsTxt(content string) []RobotsRule {
	var rules []RobotsRule
	var current *RobotsRule
	for _, line := range strings.Split(content, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		idx := strings.Index(line, ":")
		if idx < 0 {
			continue
		}
		directive := strings.ToLower(strings.TrimSpace(line[:idx]))
		value := strings.TrimSpace(line[idx+1:])
		switch directive {
		case "user-agent":
			if current != nil {
				rules = append(rules, *current)
			}
			current = &RobotsRule{UserAgent: strings.ToLower(value), CrawlDelay: -1}
		case "allow":
			if current != nil {
				current.AllowPaths = append(current.AllowPaths, value)
			}
		case "disallow":
			if current != nil {
				current.DisallowPaths = append(current.DisallowPaths, value)
			}
		case "crawl-delay":
			if current != nil {
				var delay float64
				_, err := strings.Fields(value)[0], error(nil)
				if len(strings.Fields(value)) > 0 {
					_, err = regexp.MatchString(`^-?[\d.]+$`, strings.Fields(value)[0])
				}
				if err == nil && len(strings.Fields(value)) > 0 {
					fmt_sscanf(strings.Fields(value)[0], &delay)
					current.CrawlDelay = delay
				}
			}
		}
	}
	if current != nil {
		rules = append(rules, *current)
	}
	return rules
}

// fmt_sscanf is a simple float parser to avoid importing fmt for Sscanf.
func fmt_sscanf(s string, f *float64) {
	// Simple parse: handle common cases
	negative := false
	if strings.HasPrefix(s, "-") {
		negative = true
		s = s[1:]
	}
	var result float64
	decimalSeen := false
	var decimalPlace float64 = 10
	for _, c := range s {
		if c >= '0' && c <= '9' {
			digit := float64(c - '0')
			if !decimalSeen {
				result = result*10 + digit
			} else {
				result += digit / decimalPlace
				decimalPlace *= 10
			}
		} else if c == '.' && !decimalSeen {
			decimalSeen = true
		} else {
			break
		}
	}
	if negative {
		result = -result
	}
	*f = result
}

// matchesPattern checks if a path matches a robots.txt pattern (supports * and $).
func matchesRobotsPattern(path, pattern string) bool {
	if pattern == "/" {
		return true
	}
	if strings.Contains(pattern, "*") || strings.Contains(pattern, "$") {
		var re strings.Builder
		for _, c := range pattern {
			switch c {
			case '*':
				re.WriteString(".*")
			case '$':
				re.WriteString("$")
			default:
				if strings.ContainsRune(".^+?{}[]|()\\", c) {
					re.WriteByte('\\')
				}
				re.WriteRune(c)
			}
		}
		if !strings.HasSuffix(re.String(), "$") {
			re.WriteString(".*")
		}
		r, err := regexp.Compile("^" + re.String())
		if err != nil {
			return false
		}
		return r.MatchString(path)
	}
	return strings.HasPrefix(path, pattern)
}

// IsAllowed checks if a URL is allowed by robots.txt.
func (rc *RobotsChecker) IsAllowed(rawURL, baseURL string) (bool, string) {
	if rc.IgnoreRobots {
		return true, "robots.txt ignored"
	}
	rules := rc.GetRulesForDomain(baseURL)
	if len(rules) == 0 {
		return true, "no robots.txt"
	}
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return true, "parse error"
	}
	path := parsed.Path
	if path == "" {
		path = "/"
	}
	if parsed.RawQuery != "" {
		path += "?" + parsed.RawQuery
	}

	// Find applicable rules (most specific user-agent first)
	var applicable []RobotsRule
	for _, rule := range rules {
		if rule.UserAgent == "*" {
			applicable = append(applicable, rule)
		} else if strings.Contains(rule.UserAgent, rc.UserAgent) || strings.Contains(rc.UserAgent, rule.UserAgent) {
			// Insert at beginning (more specific first)
			applicable = append([]RobotsRule{rule}, applicable...)
		}
	}
	if len(applicable) == 0 {
		return true, "no applicable rules"
	}
	for _, rule := range applicable {
		for _, allowPattern := range rule.AllowPaths {
			if matchesRobotsPattern(path, allowPattern) {
				return true, "allowed by pattern: " + allowPattern
			}
		}
		for _, disallowPattern := range rule.DisallowPaths {
			if disallowPattern != "" && matchesRobotsPattern(path, disallowPattern) {
				return false, "disallowed by pattern: " + disallowPattern
			}
		}
	}
	return true, "no matching disallow rules"
}

// CheckURL returns (shouldCrawl, reason). Increments skippedCount if disallowed.
func (rc *RobotsChecker) CheckURL(rawURL, baseURL string) (bool, string) {
	allowed, reason := rc.IsAllowed(rawURL, baseURL)
	if !allowed {
		rc.skippedCount++
	}
	return allowed, reason
}

// FilterURLs returns (allowed, skipped) URL lists.
func (rc *RobotsChecker) FilterURLs(urls []string, baseURL string) ([]string, map[string]string) {
	if rc.IgnoreRobots {
		return urls, nil
	}
	var allowed []string
	skipped := make(map[string]string)
	for _, u := range urls {
		ok, reason := rc.IsAllowed(u, baseURL)
		if ok {
			allowed = append(allowed, u)
		} else {
			skipped[u] = reason
			rc.skippedCount++
		}
	}
	return allowed, skipped
}

// GetCrawlDelay returns the crawl delay from robots.txt, or -1 if not set.
func (rc *RobotsChecker) GetCrawlDelay(baseURL string) float64 {
	rules := rc.GetRulesForDomain(baseURL)
	for _, rule := range rules {
		if rule.UserAgent == "*" || strings.Contains(rule.UserAgent, rc.UserAgent) {
			if rule.CrawlDelay >= 0 {
				return rule.CrawlDelay
			}
		}
	}
	return -1
}

// GetStats returns robots.txt compliance statistics.
func (rc *RobotsChecker) GetStats() JSONRobotsStats {
	return JSONRobotsStats{
		URLsSkipped: rc.skippedCount,
		Ignored:     rc.IgnoreRobots,
	}
}
