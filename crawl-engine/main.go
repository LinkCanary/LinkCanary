package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"
	"sync"
	"time"
)

// --- Main entry point: flag parsing, orchestration, JSON output ---

func main() {
	// Input source (mutually exclusive in Python; here we just check)
	sitemapURL := flag.String("sitemap-url", "", "URL to sitemap.xml")
	singleURL := flag.String("url", "", "Check a single URL")
	urlsFile := flag.String("urls-file", "", "Read URLs from a file")

	// Crawl settings
	delay := flag.Float64("delay", 0.5, "Seconds between requests")
	timeout := flag.Int("timeout", 10, "Request timeout in seconds")
	maxRetries := flag.Int("max-retries", 3, "Max retries for 502/503/504")
	retryDelay := flag.Float64("retry-delay", 1.0, "Initial retry delay in seconds")
	retryBackoff := flag.Float64("retry-backoff", 2.0, "Retry backoff multiplier")
	noRetry := flag.Bool("no-retry", false, "Disable retries")

	// Auth
	authUser := flag.String("auth-user", "", "HTTP Basic Auth username")
	authPass := flag.String("auth-pass", "", "HTTP Basic Auth password")
	authPassEnv := flag.String("auth-pass-env", "", "Env var name for auth password")

	// Headers and cookies (repeated flags)
	var headers multiFlag
	flag.Var(&headers, "header", "Custom header (repeatable): Name: Value")
	var cookies multiFlag
	flag.Var(&cookies, "cookie", "Cookie (repeatable): name=value")

	// Filtering
	internalOnly := flag.Bool("internal-only", false, "Only check internal links")
	externalOnly := flag.Bool("external-only", false, "Only check external links")
	var excludePatterns multiFlag
	flag.Var(&excludePatterns, "exclude-pattern", "Exclude URL pattern (repeatable)")
	var includePatterns multiFlag
	flag.Var(&includePatterns, "include-pattern", "Include URL pattern (repeatable)")
	patternType := flag.String("pattern-type", "glob", "Pattern type: glob|regex")

	// Other options
	_ = flag.Bool("skip-ok", false, "Exclude 200 OK from report (handled by Python)")
	maxPages := flag.Int("max-pages", 0, "Limit pages to crawl (0 = no limit)")
	verbose := flag.Bool("verbose", false, "Show detailed progress")
	userAgent := flag.String("user-agent", "LinkCanary/1.0", "Custom User-Agent")
	includeSubdomains := flag.Bool("include-subdomains", false, "Treat subdomains as internal")
	ignoreRobots := flag.Bool("ignore-robots", false, "Ignore robots.txt")
	var sinceDate string
	flag.StringVar(&sinceDate, "since", "", "Only crawl pages modified after YYYY-MM-DD")
	_ = flag.Bool("no-orphan-check", false, "Skip orphaned page detection (handled by Python)")
	baselineSitemap := flag.String("baseline-sitemap", "", "Baseline sitemap URL for preview_404")
	collectHTML := flag.Bool("collect-html", false, "Include page HTML in output (for embeddings)")

	flag.Parse()

	// Resolve auth password from env
	password := *authPass
	if *authPassEnv != "" {
		password = os.Getenv(*authPassEnv)
	}

	// Parse headers into map
	headerMap := make(map[string]string)
	for _, h := range headers {
		idx := strings.Index(h, ":")
		if idx > 0 {
			headerMap[strings.TrimSpace(h[:idx])] = strings.TrimSpace(h[idx+1:])
		}
	}

	// Parse cookies into map
	cookieMap := make(map[string]string)
	for _, c := range cookies {
		idx := strings.Index(c, "=")
		if idx > 0 {
			cookieMap[strings.TrimSpace(c[:idx])] = strings.TrimSpace(c[idx+1:])
		}
	}

	// Determine input source
	var pageURLs []string
	var sitemapMode bool

	if *singleURL != "" {
		pageURLs = []string{*singleURL}
	} else if *urlsFile != "" {
		data, err := os.ReadFile(*urlsFile)
		if err != nil {
			emitError(fmt.Sprintf("failed to read urls file: %v", err), 2)
			return
		}
		for _, line := range strings.Split(string(data), "\n") {
			line = strings.TrimSpace(line)
			if line != "" && !strings.HasPrefix(line, "#") {
				pageURLs = append(pageURLs, line)
			}
		}
	} else if *sitemapURL != "" {
		sitemapMode = true
		sp := NewSitemapParser(*userAgent, *timeout)
		var since *time.Time
		if sinceDate != "" {
			t, err := time.Parse("2006-01-02", sinceDate)
			if err == nil {
				since = &t
			}
		}
		urls, err := sp.ParseSitemap(*sitemapURL, since)
		if err != nil {
			emitError(fmt.Sprintf("failed to parse sitemap: %v", err), 2)
			return
		}
		pageURLs = urls
	} else {
		emitError("no input source specified (use --sitemap-url, --url, or --urls-file)", 2)
		return
	}

	// Apply max-pages limit
	if *maxPages > 0 && len(pageURLs) > *maxPages {
		pageURLs = pageURLs[:*maxPages]
	}

	// Determine base URL for internal link detection
	baseURL := *sitemapURL
	if baseURL == "" && len(pageURLs) > 0 {
		baseURL = pageURLs[0]
	}
	// Extract root domain as base for subdomain handling
	if *includeSubdomains {
		baseURL = "https://" + GetRootDomain(baseURL)
	}

	// Crawl pages
	crawler := NewPageCrawler(baseURL, *userAgent, *timeout, *delay, *includeSubdomains)
	robotsChecker := NewRobotsChecker(*userAgent, *timeout, *ignoreRobots)

	var allLinks []ExtractedLink
	pageHTML := make(map[string]string)

	for _, pageURL := range pageURLs {
		// Robots check
		allowed, _ := robotsChecker.CheckURL(pageURL, baseURL)
		if !allowed {
			continue
		}

		if *collectHTML {
			links, html := crawler.CrawlPageWithHTML(pageURL)
			allLinks = append(allLinks, links...)
			if html != "" {
				pageHTML[pageURL] = html
			}
		} else {
			links := crawler.CrawlPage(pageURL)
			allLinks = append(allLinks, links...)
		}

		if *verbose {
			fmt.Fprintf(os.Stderr, "Crawled %s: %d links\n", pageURL, len(allLinks))
		}
	}

	// Deduplicate links and apply filters
	patternMatcher := NewPatternMatcher(includePatterns, excludePatterns, *patternType)

	uniqueLinks := deduplicateAndFilter(allLinks, patternMatcher, *internalOnly, *externalOnly)

	// Check links concurrently
	maxRetriesVal := *maxRetries
	if *noRetry {
		maxRetriesVal = 0
	}

	linkChecker := NewLinkChecker(*userAgent, *timeout, *delay, maxRetriesVal, *retryDelay, *retryBackoff)
	linkChecker.AuthUser = *authUser
	linkChecker.AuthPass = password
	linkChecker.CustomHeaders = headerMap
	linkChecker.Cookies = cookieMap

	// Collect unique URLs to check
	urlSet := make(map[string]bool)
	for _, link := range uniqueLinks {
		urlSet[link.LinkURL] = true
	}
	urlsToCheck := make([]string, 0, len(urlSet))
	for u := range urlSet {
		urlsToCheck = append(urlsToCheck, u)
	}

	// Concurrent checking with worker pool
	statuses := checkLinksConcurrent(linkChecker, urlsToCheck, 10, *verbose)

	// Baseline sitemap
	var baselineURLs []string
	if *baselineSitemap != "" {
		sp := NewSitemapParser(*userAgent, *timeout)
		urls, err := sp.ParseSitemap(*baselineSitemap, nil)
		if err == nil {
			baselineURLs = urls
		}
	}

	// Build output
	output := buildOutput(baseURL, sitemapMode, pageURLs, uniqueLinks, pageHTML, statuses, robotsChecker, linkChecker, baselineURLs, *collectHTML)

	// Write JSON to stdout
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(output); err != nil {
		emitError(fmt.Sprintf("failed to write JSON output: %v", err), 2)
		return
	}
}

func checkLinksConcurrent(lc *LinkChecker, urls []string, workers int, verbose bool) map[string]LinkStatus {
	var mu sync.Mutex
	results := make(map[string]LinkStatus)
	var wg sync.WaitGroup

	urlCh := make(chan string, len(urls))
	for _, u := range urls {
		urlCh <- u
	}
	close(urlCh)

	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for u := range urlCh {
				status := lc.CheckLink(u)
				mu.Lock()
				results[u] = status
				mu.Unlock()
				if verbose {
					fmt.Fprintf(os.Stderr, "Checked %s: %d\n", u, status.StatusCode)
				}
			}
		}()
	}
	wg.Wait()
	return results
}

func buildOutput(baseURL string, sitemapMode bool, pageURLs []string, links []ExtractedLink, pageHTML map[string]string, statuses map[string]LinkStatus, rc *RobotsChecker, lc *LinkChecker, baselineURLs []string, collectHTML bool) CrawlOutput {
	jsonLinks := make([]JSONExtractedLink, len(links))
	for i, l := range links {
		jsonLinks[i] = JSONExtractedLink{
			SourceURL:      l.SourceURL,
			LinkURL:        l.LinkURL,
			LinkText:       l.LinkText,
			IsInternal:     l.IsInternal,
			ElementType:    l.ElementType,
			IsMixedContent: l.IsMixedContent,
		}
	}

	jsonStatuses := make([]JSONLinkStatus, 0, len(statuses))
	for _, s := range statuses {
		jsonStatuses = append(jsonStatuses, s.ToJSONStatus())
	}

	urlsWithRetries, totalRetries := lc.GetRetryStats()

	// Don't include page HTML if not requested
	var htmlOut map[string]string
	if collectHTML {
		htmlOut = pageHTML
	}

	return CrawlOutput{
		Metadata: Metadata{
			BaseURL:      baseURL,
			SitemapMode:  sitemapMode,
			PageCount:    len(pageURLs),
			TotalLinks:   len(links),
			UniqueLinks:  len(statuses),
			CheckedLinks: len(statuses),
		},
		SitemapURLs:  pageURLs,
		PageURLs:     pageURLs,
		Links:        jsonLinks,
		PageHTML:     htmlOut,
		LinkStatuses: jsonStatuses,
		RobotsStats:  rc.GetStats(),
		RetryStats: JSONRetryStats{
			URLsWithRetries: urlsWithRetries,
			TotalRetries:    totalRetries,
		},
		BaselineURLs: baselineURLs,
	}
}

func deduplicateAndFilter(links []ExtractedLink, pm *PatternMatcher, internalOnly, externalOnly bool) []ExtractedLink {
	seen := make(map[string]bool)
	var result []ExtractedLink
	for _, l := range links {
		key := l.SourceURL + "|" + l.LinkURL
		if seen[key] {
			continue
		}
		seen[key] = true

		// Apply internal/external filter
		if internalOnly && !l.IsInternal {
			continue
		}
		if externalOnly && l.IsInternal {
			continue
		}

		// Apply pattern filter
		if !pm.ShouldCheck(l.LinkURL) {
			continue
		}

		result = append(result, l)
	}
	return result
}

func emitError(msg string, code int) {
	out := ErrorOutput{Error: msg, ExitCode: code}
	data, _ := json.Marshal(out)
	fmt.Fprintln(os.Stderr, string(data))
	os.Exit(code)
}

// multiFlag implements flag.Value for repeatable string flags.
type multiFlag []string

func (m *multiFlag) String() string {
	return strings.Join(*m, ", ")
}

func (m *multiFlag) Set(value string) error {
	*m = append(*m, value)
	return nil
}
