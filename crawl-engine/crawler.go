package main

import (
	"io"
	"net/http"
	"strings"
	"sync"
	"time"

	"golang.org/x/net/html"
)

// --- Page crawler and link extraction ---
// Port of link_checker/crawler.py

// PageCrawler fetches pages and extracts links from HTML.
type PageCrawler struct {
	BaseURL          string
	UserAgent        string
	Timeout          time.Duration
	Delay            time.Duration
	IncludeSubdomains bool
	Client           *http.Client
	lastRequest      time.Time
	mu               sync.Mutex
}

func NewPageCrawler(baseURL, userAgent string, timeoutSec int, delaySec float64, includeSubdomains bool) *PageCrawler {
	return &PageCrawler{
		BaseURL:          baseURL,
		UserAgent:        userAgent,
		Timeout:          time.Duration(timeoutSec) * time.Second,
		Delay:            time.Duration(delaySec * float64(time.Second)),
		IncludeSubdomains: includeSubdomains,
		Client:           &http.Client{Timeout: time.Duration(timeoutSec) * time.Second},
	}
}

// rateLimit applies per-crawler delay between requests.
func (pc *PageCrawler) rateLimit() {
	pc.mu.Lock()
	defer pc.mu.Unlock()
	elapsed := time.Since(pc.lastRequest)
	if elapsed < pc.Delay {
		time.Sleep(pc.Delay - elapsed)
	}
	pc.lastRequest = time.Now()
}

// FetchPage fetches a page and returns its HTML content.
// Returns empty string and false if the fetch fails or content is not HTML.
func (pc *PageCrawler) FetchPage(rawURL string) (string, bool) {
	pc.rateLimit()

	req, err := http.NewRequest("GET", rawURL, nil)
	if err != nil {
		return "", false
	}
	req.Header.Set("User-Agent", pc.UserAgent)
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
	req.Header.Set("Accept-Language", "en-US,en;q=0.5")

	resp, err := pc.Client.Do(req)
	if err != nil {
		return "", false
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return "", false
	}

	contentType := resp.Header.Get("Content-Type")
	if !strings.Contains(contentType, "text/html") && !strings.Contains(contentType, "application/xhtml") {
		return "", false
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", false
	}
	return string(body), true
}

// ExtractLinks extracts all links from HTML content.
// Extracts from <a href>, <img src>, <link href>, <script src>.
func (pc *PageCrawler) ExtractLinks(pageURL, htmlContent string) []ExtractedLink {
	var links []ExtractedLink

	doc, err := html.Parse(strings.NewReader(htmlContent))
	if err != nil {
		return links
	}

	// Determine base URL (check for <base href> tag)
	baseURL := pageURL
	if baseTag := findBaseTag(doc); baseTag != "" {
		if IsValidHTTPURL(baseTag) {
			baseURL = baseTag
		} else {
			resolved := ResolveRelativeURL(pageURL, baseTag)
			if IsValidHTTPURL(resolved) {
				baseURL = resolved
			}
		}
	}

	var walk func(*html.Node)
	walk = func(n *html.Node) {
		if n.Type == html.ElementNode {
			switch n.Data {
			case "a":
				href := getAttr(n, "href")
				if href != "" {
					text := truncateText(getAllText(n), 200)
					pc.resolveAndAppend(&links, pageURL, baseURL, href, text, "a")
				}
			case "img":
				src := getAttr(n, "src")
				if src != "" {
					alt := truncateText(getAttr(n, "alt"), 200)
					pc.resolveAndAppend(&links, pageURL, baseURL, src, alt, "img")
				}
			case "link":
				href := getAttr(n, "href")
				if href != "" {
					rel := getAttr(n, "rel")
					pc.resolveAndAppend(&links, pageURL, baseURL, href, truncateText(rel, 200), "link")
				}
			case "script":
				src := getAttr(n, "src")
				if src != "" {
					pc.resolveAndAppend(&links, pageURL, baseURL, src, "", "script")
				}
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			walk(c)
		}
	}
	walk(doc)

	return links
}

// resolveAndAppend resolves a URL and appends it to the links list if valid.
func (pc *PageCrawler) resolveAndAppend(links *[]ExtractedLink, pageURL, baseURL, href, linkText, elementType string) {
	if ShouldSkipLink(href) {
		return
	}
	absoluteURL := ResolveRelativeURL(baseURL, href)
	if !IsValidHTTPURL(absoluteURL) {
		return
	}
	isInternal := IsInternalLink(absoluteURL, pc.BaseURL, pc.IncludeSubdomains)
	// Mixed content: HTTP resource on HTTPS page (not for <a> tags)
	isMixedContent := elementType != "a" && strings.HasPrefix(pageURL, "https://") && strings.HasPrefix(absoluteURL, "http://")

	*links = append(*links, ExtractedLink{
		SourceURL:      pageURL,
		LinkURL:        absoluteURL,
		LinkText:       linkText,
		IsInternal:     isInternal,
		ElementType:    elementType,
		IsMixedContent: isMixedContent,
	})
}

// CrawlPage fetches a page and extracts links.
func (pc *PageCrawler) CrawlPage(rawURL string) []ExtractedLink {
	htmlContent, ok := pc.FetchPage(rawURL)
	if !ok {
		return nil
	}
	return pc.ExtractLinks(rawURL, htmlContent)
}

// CrawlPageWithHTML returns both links and raw HTML (for embeddings).
func (pc *PageCrawler) CrawlPageWithHTML(rawURL string) ([]ExtractedLink, string) {
	htmlContent, ok := pc.FetchPage(rawURL)
	if !ok {
		return nil, ""
	}
	return pc.ExtractLinks(rawURL, htmlContent), htmlContent
}

// --- HTML helper functions ---

func findBaseTag(doc *html.Node) string {
	var base string
	var walk func(*html.Node)
	walk = func(n *html.Node) {
		if n.Type == html.ElementNode && n.Data == "base" {
			if href := getAttr(n, "href"); href != "" {
				base = strings.TrimSpace(href)
				return
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			walk(c)
			if base != "" {
				return
			}
		}
	}
	walk(doc)
	return base
}

func getAttr(n *html.Node, key string) string {
	for _, attr := range n.Attr {
		if attr.Key == key {
			return strings.TrimSpace(attr.Val)
		}
	}
	return ""
}

func getAllText(n *html.Node) string {
	if n.Type == html.TextNode {
		return n.Data
	}
	var sb strings.Builder
	for c := n.FirstChild; c != nil; c = c.NextSibling {
		sb.WriteString(getAllText(c))
	}
	return sb.String()
}

func truncateText(s string, maxLen int) string {
	s = strings.TrimSpace(s)
	if len(s) > maxLen {
		return s[:maxLen]
	}
	return s
}
